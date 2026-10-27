// SPDX-License-Identifier: GPL-2.0-only
//! Bit-loop boundary oracles and real finite consumers on private kthreads.
use super::Completion;
use crate::{
    bindings,
    ffi::{c_int, c_void},
    prelude::*,
    sync::Arc,
    time::{Delta, Instant, Monotonic},
};

// This is the arithmetic module called by the selected production implementation,
// not a second Rust expression that merely resembles the implementation.
#[path = "../../../../kernel/sched/wait_bit_rust/time.rs"]
mod production_time;

struct Context(*mut c_void);
impl Drop for Context {
    fn drop(&mut self) {
        // SAFETY: Sole owning wrapper; all callbacks retain their Case Arc until
        // after final C access, so destruction cannot race a live waiter.
        unsafe { bindings::bit_case_free(self.0) };
    }
}
// SAFETY: C owns opaque storage. Queue locks protect lists, bit operations own
// bitmap synchronization, acquire/release atomics publish ownership, and marked
// flags publish abort/release. Each callback owns its slot; result reads need ack.
unsafe impl Send for Context {}
// SAFETY: Same C synchronization; no Rust reference aliases mutable C fields.
unsafe impl Sync for Context {}
#[pin_data]
struct Case {
    context: Context,
    #[pin]
    first: Completion,
    #[pin]
    second: Completion,
    mode: u32,
    timeout_ms: u32,
}
impl Case {
    fn new(mode: u32, scenario: u32, timeout_ms: u32) -> Result<Arc<Self>> {
        // SAFETY: Sleepable allocation with private mode/scenario inputs.
        let raw = unsafe { bindings::bit_case_alloc(mode, scenario) };
        if raw.is_null() {
            return Err(ENOMEM);
        }
        let context = Context(raw);
        Arc::pin_init(
            pin_init!(Self {
                context, first <- Completion::new(), second <- Completion::new(), mode, timeout_ms,
            }),
            GFP_KERNEL,
        )
    }
    fn completion(&self, slot: usize) -> &Completion {
        if slot == 0 {
            &self.first
        } else {
            &self.second
        }
    }
    fn wait(&self, slot: usize, ms: u32) -> bool {
        // SAFETY: Sleepable controller, retained pinned completion, finite wait.
        unsafe {
            bindings::wait_for_completion_timeout(
                self.completion(slot).as_raw(),
                crate::time::msecs_to_jiffies(ms),
            ) != 0
        }
    }
    fn members(&self, task: &TaskRef) -> u32 {
        // SAFETY: Task and fixture retained. C locks private/hash queue and only
        // examines generic entries live under that lock; hash buckets are shared.
        unsafe { bindings::bit_case_members(self.context.0, task.0.cast()) }
    }
    fn blocked(&self, task: &TaskRef, members: u32) -> bool {
        let start = Instant::<Monotonic>::now();
        while start.elapsed().as_millis() < 2000 {
            if self.members(task) == members {
                // SAFETY: Referenced task, IRQ-enabled caller, no queue lock held.
                // Single rq sample, not an unbounded wait_task_inactive call.
                let sample = unsafe { bindings::wait_lifecycle_blocked(task.0.cast()) };
                if sample == 7 && self.members(task) == members {
                    return true;
                }
            }
            crate::time::delay::fsleep(Delta::from_millis(10));
        }
        false
    }
    fn acquired(&self) -> u32 {
        // SAFETY: C acquire-loads per-slot ownership handshakes; plain results
        // remain unread until callback completion.
        unsafe { bindings::bit_case_acquired(self.context.0) }
    }
    fn wait_acquired(&self, both: bool) -> u32 {
        let start = Instant::<Monotonic>::now();
        while start.elapsed().as_millis() < 1000 {
            let mask = self.acquired();
            if (both && mask == 3) || (!both && mask != 0) {
                return mask;
            }
            crate::time::delay::fsleep(Delta::from_millis(10));
        }
        self.acquired()
    }
    fn release_initial(&self) {
        // SAFETY: Called once while initial busy bit is controller-owned. C
        // release-bit plus full barrier publishes payload before actual wake.
        unsafe { bindings::bit_case_release(self.context.0) };
    }
    fn release_owner(&self, slot: usize) {
        // SAFETY: Marks request only; successful callback owner clears its own bit.
        unsafe { bindings::bit_case_release_owner(self.context.0, slot as u32) };
    }
    fn value(&self) -> u32 {
        // SAFETY: C bit operation observes live retained bitmap.
        unsafe { bindings::bit_case_value(self.context.0) }
    }
    fn probe(&self, command: u32) -> i64 {
        let mut out = 0;
        // SAFETY: Private command and exclusive output. C verifies enrollment
        // under same lock before touching callback, even on observer failure.
        unsafe { bindings::bit_case_probe(self.context.0, command, &mut out) };
        out
    }
    unsafe fn result(&self, slot: usize) -> [i64; 8] {
        let mut out = [0; 8];
        // SAFETY: Caller observed this slot's completion; C result fields are
        // immutable afterward. Output is eight exclusive local words.
        unsafe { bindings::bit_case_result(self.context.0, slot as u32, out.as_mut_ptr()) };
        out
    }
    fn cleanup(&self, tasks: &[(usize, &TaskRef)]) -> bool {
        let start = Instant::<Monotonic>::now();
        // SAFETY: Mark abort/release only, never clear another worker's bit lock.
        unsafe { bindings::bit_case_abort(self.context.0) };
        for (_, task) in tasks {
            if self.mode >= 3 {
                // SAFETY: Referenced private task; real consumers allow SIGUSR1
                // before entering waits. No signal touches the KUnit controller.
                unsafe {
                    bindings::completion_test_send_signal(task.0, bindings::SIGUSR1 as c_int)
                };
            }
            // SAFETY: Referenced task; additional wake covers blocked cleanup.
            unsafe { bindings::wake_up_process(task.0) };
        }
        let mut all = true;
        for (slot, _) in tasks {
            let ms = 1000i64.saturating_sub(start.elapsed().as_millis()).max(0);
            all &= self.wait(*slot, ms as u32);
        }
        all
    }
}
struct TaskRef(*mut bindings::task_struct);
impl Drop for TaskRef {
    fn drop(&mut self) {
        // SAFETY: Independent reference obtained by successful create.
        unsafe { bindings::put_task_struct(self.0) };
    }
}
unsafe fn run(data: *mut c_void, slot: usize) -> c_int {
    // SAFETY: Successful creator transfers one Arc to this sole callback.
    let case = unsafe { Arc::<Case>::from_raw(data.cast()) };
    // SAFETY: Dedicated task exclusively owns its slot; Arc retains fixture.
    // State-mutating deterministic helpers run here, never on KUnit controller.
    unsafe { bindings::bit_case_run(case.context.0, slot as u32, case.timeout_ms) };
    case.completion(slot).complete_all();
    // No C context access after acknowledgment; Arc protects return gap.
    0
}
unsafe extern "C" fn first(data: *mut c_void) -> c_int {
    // SAFETY: Creator selects exclusive slot zero for this transferred Arc.
    unsafe { run(data, 0) }
}
unsafe extern "C" fn second(data: *mut c_void) -> c_int {
    // SAFETY: Creator selects exclusive slot one for this transferred Arc.
    unsafe { run(data, 1) }
}
fn spawn(case: &Arc<Case>, slot: usize) -> Result<TaskRef> {
    let data = Arc::into_raw(case.clone()).cast_mut().cast();
    // SAFETY: Callback ABI and one-Arc transfer; one task per slot per case.
    let raw = unsafe {
        bindings::completion_test_kthread_create(Some(if slot == 0 { first } else { second }), data)
    };
    let raw = match crate::error::from_err_ptr(raw) {
        Ok(raw) => raw,
        Err(error) => {
            // SAFETY: Failed creation invokes no callback; reclaim its Arc.
            unsafe { drop(Arc::<Case>::from_raw(data.cast())) };
            return Err(error);
        }
    };
    let task = TaskRef(raw);
    // SAFETY: Retained stopped task, no fallible gap before wake.
    unsafe { bindings::wake_up_process(task.0) };
    Ok(task)
}
fn deterministic(mode: u32, scenario: u32) -> Result<[i64; 8]> {
    let case = Case::new(mode, scenario, 10000)?;
    let start = Instant::<Monotonic>::now();
    let task = spawn(&case, 0)?;
    let done = case.wait(0, 1000);
    let elapsed = start.elapsed().as_millis();
    let cleaned = case.cleanup(&[(0, &task)]);
    // SAFETY: Only completed slot data is read.
    let out = if done {
        unsafe { case.result(0) }
    } else {
        [-1; 8]
    };
    drop(task);
    assert!(done && cleaned && elapsed < 5000);
    assert_eq!(out[0], 0);
    Ok(out)
}

#[macros::kunit_tests(rusix_completion_wait_bit)]
mod tests {
    use super::*;
    #[test]
    fn ordinary_loop_preserves_action_errors_even_when_bit_clears() -> Result {
        for (scenario, expected) in [
            (0, [0, 0, 0, 4, 0, 15]),
            (1, [0, 1, 0, 4, 0, 15]),
            (2, [-5, 1, 0, 4, 0, 15]),
            (3, [-5, 1, 0, 4, 1, 15]),
            (4, [0, 2, 0, 4, 0, 15]),
        ] {
            assert_eq!(&deterministic(0, scenario)?[1..7], &expected);
        }
        // Actual ordinary stack wrapper, initially clear bit and unused NULL
        // action: return, bit, RUNNING, own hash membership, IRQ enabled, reserved.
        assert_eq!(&deterministic(0, 10)?[1..7], &[0, 0, 1, 0, 1, 0]);
        Ok(())
    }
    #[test]
    fn lock_loop_acquisition_overrides_action_error() -> Result {
        for (scenario, expected) in [
            (5, [0, 0, 0, 5, 1, 15]),
            (6, [0, 1, 0, 5, 1, 15]),
            (7, [-5, 1, 0, 5, 1, 15]),
            (8, [0, 1, 0, 5, 1, 15]),
            (9, [0, 2, 0, 5, 1, 15]),
        ] {
            assert_eq!(&deterministic(0, scenario)?[1..7], &expected);
        }
        // Actual lock stack wrapper claims the precleared bit without action.
        assert_eq!(&deterministic(0, 11)?[1..7], &[0, 1, 1, 0, 1, 0]);
        Ok(())
    }
    #[test]
    fn key_match_and_clear_bit_gate_autoremove() -> Result {
        for (scenario, expected) in [
            (0, [0, 0, 0, 0, 0, 4]),
            (1, [0, 0, 0, 0, 0, 4]),
            (2, [1, 0, 0, 0, 0, 4]),
            (3, [1, 1, 1, 1, 1, 4]),
            (4, [1, 1, 1, 1, 1, 4]),
            (5, [1, 0, 0, 0, 1, 4]),
        ] {
            assert_eq!(&deterministic(1, scenario)?[1..7], &expected);
        }
        Ok(())
    }
    #[test]
    fn already_expired_action_returns_without_scheduling() -> Result {
        assert_eq!(&deterministic(2, 0)?[1..4], &[-11, 1, 1]);
        Ok(())
    }
    #[test]
    fn production_deadline_arithmetic_matches_c_across_wrap() {
        use crate::ffi::c_ulong;
        let max = c_ulong::MAX;
        let half = (1 as c_ulong) << (c_ulong::BITS - 1);
        for (now, deadline) in [
            (0, 0),
            (5, 6),
            (6, 5),
            (max, 0),
            (0, max),
            (max - 1, 1),
            (0, half),
            (half, 0),
        ] {
            let mut out = [0i64; 3];
            // SAFETY: Pure scalar C reference macros and three exclusive words;
            // no task-state or global-clock mutation on the KUnit controller.
            unsafe { bindings::wait_bit_test_time(now, deadline, out.as_mut_ptr()) };
            assert_eq!(
                i64::from(production_time::deadline_expired(now, deadline)),
                out[0]
            );
            assert_eq!(
                production_time::remaining_interval(deadline, now) as i64,
                out[1]
            );
            assert_eq!(
                production_time::deadline_after(now, deadline) as i64,
                out[2]
            );
        }
    }
    #[test]
    fn blocked_bit_clear_publishes_payload() -> Result {
        let case = Case::new(3, 0, 10000)?;
        let start = Instant::<Monotonic>::now();
        let task = spawn(&case, 0)?;
        let initial = case.blocked(&task, 1);
        let address = case.probe(0);
        let after_address = case.blocked(&task, 1);
        let bit = case.probe(1);
        let after_bit = case.blocked(&task, 1);
        let set = case.probe(2);
        let after_set = case.blocked(&task, 1);
        case.release_initial();
        let done = case.wait(0, 1000);
        let members = case.members(&task);
        let elapsed = start.elapsed().as_millis();
        let cleaned = case.cleanup(&[(0, &task)]);
        // SAFETY: Read only after callback completion.
        let out = if done {
            unsafe { case.result(0) }
        } else {
            [-1; 8]
        };
        drop(task);
        assert!(initial && after_address && after_bit && after_set && done && cleaned);
        assert!(elapsed < 5000);
        assert_eq!((address, bit, set, members), (0, 0, 0, 0));
        assert_eq!(&out[..5], &[0, 0x1234, 1, 1, 0]);
        assert_eq!(case.value(), 0);
        Ok(())
    }
    #[test]
    fn blocked_bit_lock_serializes_two_owners() -> Result {
        let case = Case::new(4, 0, 10000)?;
        let start = Instant::<Monotonic>::now();
        let a = spawn(&case, 0)?;
        let first_blocked = case.blocked(&a, 1);
        let b = match spawn(&case, 1) {
            Ok(task) => task,
            Err(error) => {
                case.cleanup(&[(0, &a)]);
                return Err(error);
            }
        };
        let second_blocked = case.blocked(&b, 3);
        let both_blocked = case.blocked(&a, 3);
        case.release_initial();
        let winner = case.wait_acquired(false);
        let loser_blocked = match winner {
            1 => case.blocked(&b, 2),
            2 => case.blocked(&a, 1),
            _ => false,
        };
        let held = case.value();
        if winner == 1 {
            case.release_owner(0);
        }
        if winner == 2 {
            case.release_owner(1);
        }
        let both = case.wait_acquired(true);
        case.release_owner(0);
        case.release_owner(1);
        let done_a = case.wait(0, 1000);
        let done_b = case.wait(1, 1000);
        let members = case.members(&a);
        let elapsed = start.elapsed().as_millis();
        let cleaned = case.cleanup(&[(0, &a), (1, &b)]);
        // SAFETY: Each immutable result requires its own observed acknowledgment.
        let ra = if done_a {
            unsafe { case.result(0) }
        } else {
            [-1; 8]
        };
        // SAFETY: Corresponding second callback acknowledgment observed.
        let rb = if done_b {
            unsafe { case.result(1) }
        } else {
            [-1; 8]
        };
        drop((a, b));
        assert!(first_blocked && second_blocked && both_blocked && loser_blocked);
        assert!(done_a && done_b && cleaned && elapsed < 5000);
        assert!(winner == 1 || winner == 2);
        assert_eq!((held, both, members, case.value()), (1, 3, 0, 0));
        assert_eq!(
            &ra[..5],
            &[0, if winner == 1 { 0x1234 } else { 0x5678 }, 1, 1, 0]
        );
        assert_eq!(
            &rb[..5],
            &[0, if winner == 2 { 0x1234 } else { 0x5678 }, 1, 1, 0]
        );
        Ok(())
    }
    #[test]
    fn blocked_bit_signal_and_expiry_unlink() -> Result {
        for signal in [false, true] {
            let case = Case::new(5, 0, if signal { 10000 } else { 200 })?;
            let start = Instant::<Monotonic>::now();
            let task = spawn(&case, 0)?;
            let blocked = case.blocked(&task, 1);
            let sent = if signal {
                // SAFETY: Referenced private task allows SIGUSR1 before enrollment.
                unsafe { bindings::completion_test_send_signal(task.0, bindings::SIGUSR1 as c_int) }
            } else {
                0
            };
            let done = case.wait(0, 1000);
            let members = case.members(&task);
            let still_set = case.value();
            let elapsed = start.elapsed().as_millis();
            let cleaned = case.cleanup(&[(0, &task)]);
            // SAFETY: Read only after successful completion publication.
            let out = if done {
                unsafe { case.result(0) }
            } else {
                [-1; 8]
            };
            case.release_initial(); // No lock ownership in this ordinary wait.
            let after_late = case.members(&task);
            drop(task);
            assert!(blocked && done && cleaned && elapsed < 5000);
            assert_eq!((sent, members, still_set, after_late), (0, 0, 1, 0));
            assert_eq!(&out[..5], &[if signal { -4 } else { -11 }, 0, 1, 1, 0]);
        }
        Ok(())
    }
    #[test]
    fn stack_timeout_wrapper_blocks_and_cleans() -> Result {
        let case = Case::new(6, 0, 10000)?;
        let start = Instant::<Monotonic>::now();
        let task = spawn(&case, 0)?;
        let blocked = case.blocked(&task, 1);
        case.release_initial();
        let done = case.wait(0, 1000);
        let members = case.members(&task);
        let elapsed = start.elapsed().as_millis();
        let cleaned = case.cleanup(&[(0, &task)]);
        // SAFETY: Wrapper's stack waiter is gone before completion/result reads.
        let out = if done {
            unsafe { case.result(0) }
        } else {
            [-1; 8]
        };
        drop(task);
        assert!(blocked && done && cleaned && elapsed < 5000);
        assert_eq!(members, 0);
        assert_eq!(&out[..5], &[0, 0x1234, 1, 1, 0]);
        Ok(())
    }
}
