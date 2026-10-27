// SPDX-License-Identifier: GPL-2.0-only
//! Real generic wait consumers on private kthreads, plus lifecycle boundaries.
//! Scheduler samples establish descheduling at observation, not atomic causation.
use super::Completion;
use crate::{
    bindings,
    ffi::{c_int, c_void},
    prelude::*,
    sync::Arc,
    time::{Delta, Instant, Monotonic},
};

struct Context(*mut c_void);
impl Drop for Context {
    fn drop(&mut self) {
        // SAFETY: Sole owning wrapper, destroyed only after the last Case Arc.
        // Each running callback retains that Arc until after its final access.
        unsafe { bindings::wait_lifecycle_free(self.0) };
    }
}
// SAFETY: C owns opaque fields. Queue links use its spinlock, token/payload and
// abort operations use LKMM primitives. Distinct callbacks own distinct slots;
// controller reads slot results only after completion publication.
unsafe impl Send for Context {}
// SAFETY: Same synchronization; no Rust references to mutable C fields exist.
unsafe impl Sync for Context {}

#[pin_data]
struct Case {
    context: Context,
    #[pin]
    first: Completion,
    #[pin]
    second: Completion,
    timeout_ms: u32,
}
impl Case {
    fn new(mode: u32, timeout_ms: u32) -> Result<Arc<Self>> {
        // SAFETY: Private fixed mode, sleepable allocation context. C returns
        // a new exclusively owned initialized allocation or NULL.
        let raw = unsafe { bindings::wait_lifecycle_alloc(mode) };
        if raw.is_null() {
            return Err(Error::from_errno(-12));
        }
        let context = Context(raw);
        Arc::pin_init(
            pin_init!(Self {
                context,
                first <- Completion::new(),
                second <- Completion::new(),
                timeout_ms,
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
        // SAFETY: Controller is sleepable and retains pinned completion. Finite
        // wait; complete_all makes subsequent cleanup observations repeatable.
        unsafe {
            bindings::wait_for_completion_timeout(
                self.completion(slot).as_raw(),
                crate::time::msecs_to_jiffies(ms),
            ) != 0
        }
    }

    fn members(&self) -> u32 {
        // SAFETY: Arc retains initialized queue; C acquires its spinlock and
        // compares addresses only. Uninitialized worker links aren't read.
        unsafe { bindings::wait_lifecycle_members(self.context.0) }
    }

    fn blocked(&self, task: &TaskRef, expected_members: u32) -> bool {
        let start = Instant::<Monotonic>::now();
        while start.elapsed().as_millis() < 2000 {
            if self.members() == expected_members {
                // SAFETY: Independent task reference retained; controller holds
                // no queue lock and has IRQs enabled. Single rq/pi-lock sample,
                // no wait_task_inactive loop or forced scheduler mutation.
                let sample = unsafe { bindings::wait_lifecycle_blocked(task.0.cast()) };
                if sample == 7 && self.members() == expected_members {
                    return true;
                }
            }
            crate::time::delay::fsleep(Delta::from_millis(10));
        }
        false
    }

    fn publish(&self, payload: u32) -> c_int {
        // SAFETY: Initialized retained fixture. C orders payload/token publication
        // and invokes actual wake-one; no callback pointer outlives its Arc.
        unsafe { bindings::wait_lifecycle_publish(self.context.0, payload) }
    }

    // Call only with a successful completion observation for this exact slot.
    unsafe fn result(&self, slot: usize) -> [i64; 5] {
        let mut out = [0; 5];
        // SAFETY: Caller observed slot's acknowledgment after all C writes;
        // callback makes no further C-context access. Output is exclusive local.
        unsafe { bindings::wait_lifecycle_result(self.context.0, slot as u32, out.as_mut_ptr()) };
        out
    }

    fn cleanup(&self, tasks: &[(usize, &TaskRef)]) -> bool {
        // SAFETY: Retained fixture; marked abort stores then synchronized wake-all.
        unsafe { bindings::wait_lifecycle_abort(self.context.0) };
        for (_, task) in tasks {
            // SAFETY: Retained task reference; direct wake also releases a task
            // whose queue membership was broken by a failing implementation.
            unsafe { bindings::wake_up_process(task.0) };
        }
        let start = Instant::<Monotonic>::now();
        let mut all = true;
        for (slot, _) in tasks {
            let elapsed = start.elapsed().as_millis();
            let remaining = 1000i64.saturating_sub(elapsed).max(0);
            all &= self.wait(*slot, remaining as u32);
        }
        all
    }
}

struct TaskRef(*mut bindings::task_struct);
impl Drop for TaskRef {
    fn drop(&mut self) {
        // SAFETY: Successful creation supplied this independent task reference.
        unsafe { bindings::put_task_struct(self.0) };
    }
}

unsafe fn callback(data: *mut c_void, slot: usize) -> c_int {
    // SAFETY: Creator transfers exactly one Arc to the selected sole callback;
    // no stop-before-entry mechanism can bypass its reclamation.
    let case = unsafe { Arc::<Case>::from_raw(data.cast()) };
    // SAFETY: Callback owns its slot exclusively, queue/context retained by Arc;
    // C wait loops have one finite absolute deadline and clean state/membership.
    unsafe { bindings::wait_lifecycle_run(case.context.0, slot as u32, case.timeout_ms) };
    case.completion(slot).complete_all();
    // No C context access after acknowledgment; Arc still protects return gap.
    0
}
unsafe extern "C" fn first_callback(data: *mut c_void) -> c_int {
    // SAFETY: Creator transfers one Arc and selects unique slot zero.
    unsafe { callback(data, 0) }
}
unsafe extern "C" fn second_callback(data: *mut c_void) -> c_int {
    // SAFETY: Creator transfers one Arc and selects unique slot one.
    unsafe { callback(data, 1) }
}
fn spawn(case: &Arc<Case>, slot: usize) -> Result<TaskRef> {
    let data = Arc::into_raw(case.clone()).cast_mut().cast();
    // SAFETY: Matching callback ABI, one transferred Arc, private standalone
    // kthread. Each test creates at most one task per slot.
    let raw = unsafe {
        bindings::completion_test_kthread_create(
            Some(if slot == 0 {
                first_callback
            } else {
                second_callback
            }),
            data,
        )
    };
    let raw = match crate::error::from_err_ptr(raw) {
        Ok(raw) => raw,
        Err(error) => {
            // SAFETY: Failed create never invokes callback; reclaim transferred Arc.
            unsafe { drop(Arc::<Case>::from_raw(data.cast())) };
            return Err(error);
        }
    };
    let task = TaskRef(raw);
    // SAFETY: Referenced stopped task; no failure/return gap before wake.
    unsafe { bindings::wake_up_process(task.0) };
    Ok(task)
}

#[macros::kunit_tests(rusix_completion_wait_lifecycle)]
mod tests {
    use super::*;

    #[test]
    fn blocked_priority_exclusive_handoff_consumes_one_token() -> Result {
        let case = Case::new(0, 10000)?;
        let start = Instant::<Monotonic>::now();
        let first = spawn(&case, 0)?;
        let first_blocked = case.blocked(&first, 1);
        let second = match spawn(&case, 1) {
            Ok(task) => task,
            Err(error) => {
                case.cleanup(&[(0, &first)]);
                return Err(error);
            }
        };
        let second_blocked = case.blocked(&second, 3);
        let both_blocked = case.blocked(&first, 3);
        let first_wake = case.publish(0x1234);
        let first_done = case.wait(0, 1000);
        let remaining_blocked = case.blocked(&second, 2);
        let second_wake = case.publish(0x5678);
        let second_done = case.wait(1, 1000);
        let elapsed = start.elapsed().as_millis();
        let members = case.members();
        let cleaned = case.cleanup(&[(0, &first), (1, &second)]);
        // SAFETY: Read each immutable result only if its acknowledgment passed.
        let a = if first_done {
            unsafe { case.result(0) }
        } else {
            [-1; 5]
        };
        // SAFETY: Same per-slot acknowledgment requirement.
        let b = if second_done {
            unsafe { case.result(1) }
        } else {
            [-1; 5]
        };
        drop((first, second));
        assert!(first_blocked && second_blocked && both_blocked && remaining_blocked);
        assert!(first_done && second_done && cleaned);
        assert!(elapsed < 5000);
        assert_eq!((first_wake, second_wake), (1, 1));
        assert_eq!(members, 0);
        assert_eq!(a, [1, 0x1234, 0, 1, 1]);
        assert_eq!(b, [1, 0x5678, 0, 1, 1]);
        Ok(())
    }

    #[test]
    fn blocked_signal_and_nonmatching_wake_preserve_lifecycle() -> Result {
        let case = Case::new(1, 10000)?;
        let start = Instant::<Monotonic>::now();
        let task = spawn(&case, 0)?;
        let blocked = case.blocked(&task, 1);
        // SAFETY: Retained initialized queue; mismatched mode must not remove.
        let rejected = unsafe { bindings::wait_lifecycle_mismatch(case.context.0) };
        let still_blocked = case.blocked(&task, 1);
        // SAFETY: Referenced standalone task that allows SIGUSR1 before enrolling.
        let sent =
            unsafe { bindings::completion_test_send_signal(task.0, bindings::SIGUSR1 as c_int) };
        let done = case.wait(0, 1000);
        let elapsed = start.elapsed().as_millis();
        let members = case.members();
        let cleaned = case.cleanup(&[(0, &task)]);
        // SAFETY: Successful per-slot completion precedes all result reads.
        let result = if done {
            unsafe { case.result(0) }
        } else {
            [-1; 5]
        };
        drop(task);
        assert!(blocked && still_blocked && done && cleaned);
        assert!(elapsed < 5000);
        assert_eq!((rejected, sent, members), (0, 0, 0));
        assert_eq!(result, [-(bindings::ERESTARTSYS as i64), 0, 0, 1, 1]);
        Ok(())
    }

    #[test]
    fn pending_condition_wins_after_prepare_signal_error() -> Result {
        for slot in 0..2 {
            let case = Case::new(3, 10000)?;
            let start = Instant::<Monotonic>::now();
            let task = spawn(&case, slot)?;
            let done = case.wait(slot, 1000);
            let members = case.members();
            let elapsed = start.elapsed().as_millis();
            let cleaned = case.cleanup(&[(slot, &task)]);
            // SAFETY: No read unless this slot's completion was observed.
            let result = if done {
                unsafe { case.result(slot) }
            } else {
                [-1; 5]
            };
            drop(task);
            assert!(done && cleaned);
            assert!(elapsed < 5000);
            assert_eq!(members, 0);
            let expected = if slot == 0 {
                -(bindings::ERESTARTSYS as i64)
            } else {
                crate::time::msecs_to_jiffies(10000) as i64
            };
            assert_eq!(result, [expected, 0, if slot == 0 { 1 } else { 5 }, 1, 1]);
        }
        Ok(())
    }

    #[test]
    fn timeout_finishes_before_late_wake() -> Result {
        let case = Case::new(2, 200)?;
        let start = Instant::<Monotonic>::now();
        let task = spawn(&case, 0)?;
        let blocked = case.blocked(&task, 1);
        let done = case.wait(0, 1000);
        let elapsed = start.elapsed().as_millis();
        let members = case.members();
        let late = case.publish(0x9999);
        let cleaned = case.cleanup(&[(0, &task)]);
        // SAFETY: Read immutable slot only after successful acknowledgment.
        let result = if done {
            unsafe { case.result(0) }
        } else {
            [-1; 5]
        };
        drop(task);
        assert!(blocked && done && cleaned);
        assert!(elapsed < 5000);
        assert_eq!((members, late), (0, 0));
        assert_eq!(result, [0, 0, 0, 1, 1]);
        Ok(())
    }

    #[test]
    fn repeated_prepare_preserves_membership_state_and_empty_return() -> Result {
        let case = Case::new(4, 10000)?;
        let start = Instant::<Monotonic>::now();
        let task = spawn(&case, 0)?;
        let done = case.wait(0, 1000);
        let members = case.members();
        let elapsed = start.elapsed().as_millis();
        let cleaned = case.cleanup(&[(0, &task)]);
        // SAFETY: C synthetic callback finished before its results are inspected.
        let result = if done {
            unsafe { case.result(0) }
        } else {
            [-1; 5]
        };
        drop(task);
        assert!(done && cleaned);
        assert!(elapsed < 5000);
        assert_eq!(members, 0);
        assert_eq!(result, [1, 0, 127, 1, 1]);
        Ok(())
    }
}
