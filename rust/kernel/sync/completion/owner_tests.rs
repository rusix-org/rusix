// SPDX-License-Identifier: GPL-2.0-only
//! Global wait-table oracles and retained variable-collision consumers.
//! Scheduler samples establish descheduling at observation, not atomic causation.
use super::Completion;
use crate::{
    bindings,
    ffi::{c_int, c_ulong, c_void},
    prelude::*,
    sync::Arc,
    time::{Delta, Instant, Monotonic},
};

struct Context(*mut c_void);
impl Drop for Context {
    fn drop(&mut self) {
        // SAFETY: Sole owning wrapper, destroyed only after the last Case Arc.
        // Each running callback retains that Arc until after its final access.
        // C retains the allocation if a failed cleanup left own nodes reachable.
        unsafe { bindings::owner_free(self.0) };
    }
}
// SAFETY: C owns opaque fields. Queue links use its spinlock, token/payload and
// abort operations use LKMM primitives. Global bucket is borrowed permanently,
// never initialized/freed by the fixture. Distinct callbacks own distinct slots;
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
    fn new(mode: u32, flags_a: u32, flags_b: u32) -> Result<Arc<Self>> {
        // SAFETY: Private fixed mode, sleepable allocation context. C returns
        // a new exclusively owned initialized allocation or ERR_PTR.
        let raw = unsafe { bindings::owner_alloc(mode, flags_a, flags_b) };
        let context = Context(crate::error::from_err_ptr(raw)?);
        Arc::pin_init(
            pin_init!(Self {
                context,
                first <- Completion::new(),
                second <- Completion::new(),
                timeout_ms: 10000,
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
        unsafe { bindings::owner_members(self.context.0) }
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

    fn publish(&self, slot: usize, payload: u32) {
        // SAFETY: Retained fixture; C release-publishes this slot's condition,
        // then full barrier and actual wake_up_var on its valid word identity.
        unsafe { bindings::owner_publish(self.context.0, slot as u32, payload) };
    }

    // Call only with a successful completion observation for this exact slot.
    unsafe fn result(&self, slot: usize) -> [i64; 4] {
        let mut out = [0; 4];
        // SAFETY: Caller observed slot's acknowledgment after all C writes;
        // callback makes no further C-context access. Output is exclusive local.
        unsafe { bindings::owner_result(self.context.0, slot as u32, out.as_mut_ptr()) };
        out
    }

    fn cleanup(&self, tasks: &[(usize, &TaskRef)]) -> bool {
        // SAFETY: Retained fixture; marked abort stores then matching variable wakes.
        unsafe { bindings::owner_abort(self.context.0) };
        for (_, task) in tasks {
            // SAFETY: Retained task reference; direct wake also releases a task
            // whose queue membership was broken by a failing implementation.
            unsafe {
                bindings::wake_up_process(task.0);
            };
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
    unsafe { bindings::owner_run(case.context.0, slot as u32, case.timeout_ms) };
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

#[macros::kunit_tests(rusix_completion_wait_owner)]
mod tests {
    use super::*;

    fn observe(address: c_ulong, bit: c_int, variable: bool) -> Result<[c_ulong; 6]> {
        let mut out = [0; 6];
        // SAFETY: Identity-only hash API; fabricated addresses are never dereferenced
        // or passed to wake. Output is exclusive local memory; table initialized at boot.
        unsafe { bindings::owner_hash_observe(address, bit, variable, out.as_mut_ptr()) };
        assert!(out[0] < 256);
        // Propagate malformed observations before arithmetic or caller indexing;
        // failed oracles must fail the test, never panic the kernel.
        if out[0] >= 256 {
            return Err(EINVAL);
        }
        let offset = out[0].checked_mul(out[3]).ok_or(EINVAL)?;
        assert_eq!(out[1], out[2].checked_add(offset).ok_or(EINVAL)?);
        assert_eq!(out[3], core::mem::size_of::<bindings::wait_queue_head>());
        assert_eq!(out[4], core::mem::align_of::<bindings::wait_queue_head>());
        assert_eq!(out[1].checked_rem(out[4]).ok_or(EINVAL)?, 0);
        assert_eq!(out[2].checked_rem(out[5]).ok_or(EINVAL)?, 0);
        Ok(out)
    }

    fn collision_case(flags_a: u32, flags_b: u32, cancel: bool) -> Result {
        let case = Case::new(0, flags_a, flags_b)?;
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
        if cancel {
            // SAFETY: Both words remain valid, abort is marked before matching wakes.
            unsafe { bindings::owner_abort(case.context.0) };
        } else {
            case.publish(0, 0x1234);
        }
        let first_done = case.wait(0, 1000);
        // A fresh blocked/member sample establishes a distinct remaining predicate,
        // not absence of a spurious wake/re-enrollment. The synchronous callback
        // probe independently tests key filtering while retaining the queue lock.
        let remaining_blocked = cancel || case.blocked(&second, 2);
        if !cancel {
            case.publish(1, 0x5678);
        }
        let second_done = case.wait(1, 1000);
        let members = case.members();
        let elapsed = start.elapsed().as_millis();
        let cleaned = case.cleanup(&[(0, &first), (1, &second)]);
        // SAFETY: Read each result only after its own acknowledgment; callbacks make
        // no C-field accesses afterwards. Their Arcs still protect the return gap.
        let a = if first_done {
            unsafe { case.result(0) }
        } else {
            [-1; 4]
        };
        // SAFETY: Same per-slot acknowledgment/lifetime requirement for second result.
        let b = if second_done {
            unsafe { case.result(1) }
        } else {
            [-1; 4]
        };
        drop((first, second));
        assert!(first_blocked && second_blocked && both_blocked && remaining_blocked);
        assert!(first_done && second_done && cleaned && elapsed < 5000);
        assert_eq!(members, 0); // Only own nodes: says nothing about foreign users.
        if cancel {
            assert_eq!(a, [-(bindings::ECANCELED as i64), 0, 1, 1]);
            assert_eq!(b, [-(bindings::ECANCELED as i64), 0, 1, 1]);
        } else {
            assert_eq!(a, [1, 0x1234, 1, 1]);
            assert_eq!(b, [1, 0x5678, 1, 1]);
        }
        Ok(())
    }

    #[test]
    fn original_hash_oracle_covers_all_heads_and_shared_class() -> Result {
        let max = c_ulong::MAX;
        let high = (1 as c_ulong) << (c_ulong::BITS - 1);
        let shift = if c_ulong::BITS == 32 { 5 } else { 6 };
        let wraps = (1 as c_ulong) << (c_ulong::BITS - shift);
        for address in [0, 1, max, high, wraps - 1, wraps, wraps + 1] {
            observe(address, 0, true)?;
            for bit in [c_int::MIN, -65, -1, 0, 1, 31, 32, 63, 64, 65, c_int::MAX] {
                observe(address, bit, false)?;
            }
        }
        for variable in [false, true] {
            let mut first = KVec::with_capacity(256, GFP_KERNEL)?;
            for _ in 0..256 {
                first.push(None, GFP_KERNEL)?;
            }
            let mut covered = 0;
            for address in 0..65536 as c_ulong {
                let out = observe(address, 3, variable)?;
                let index = out[0] as usize;
                let entry = first.get_mut(index).ok_or(EINVAL)?;
                if entry.is_none() {
                    *entry = Some(address);
                    covered += 1;
                }
                if covered == 256 {
                    break;
                }
            }
            assert_eq!(covered, 256);
            for (index, address) in first.iter().enumerate() {
                let address = address.ok_or(EINVAL)?;
                let out = observe(address, 3, variable)?;
                assert_eq!(out[0] as usize, index);
                assert_eq!(observe(address, 3, variable)?[1], out[1]);
                if variable {
                    // SAFETY: Independently checked lookup names this valid head;
                    // helper takes one lock at a time, without list emptiness claims.
                    let metadata = unsafe { bindings::owner_head_observe(address, index as u32) };
                    assert_eq!(metadata, if cfg!(CONFIG_LOCKDEP) { 0x100 } else { 0 });
                }
            }
        }
        Ok(())
    }

    #[test]
    fn variable_constructor_and_callback_preserve_identity_and_flags() -> Result {
        let case = Case::new(1, 0, 0)?;
        let task = spawn(&case, 0)?;
        let done = case.wait(0, 1000);
        let cleaned = case.cleanup(&[(0, &task)]);
        // SAFETY: Constructor callback completed its plain snapshots before ack.
        let result = if done {
            unsafe { case.result(0) }
        } else {
            [-1; 4]
        };
        drop(task);
        assert!(done && cleaned);
        assert_eq!(result, [0, 5, 1, 1]);
        Ok(())
    }

    #[test]
    fn normal_collision_preserves_distinct_predicates() -> Result {
        collision_case(0, 0, false)
    }
    #[test]
    fn exclusive_collision_preserves_unmatched_waiter() -> Result {
        collision_case(
            bindings::WQ_FLAG_EXCLUSIVE,
            bindings::WQ_FLAG_EXCLUSIVE,
            false,
        )
    }
    #[test]
    fn mixed_collision_orders_preserve_key_filtering() -> Result {
        collision_case(0, bindings::WQ_FLAG_EXCLUSIVE, false)?;
        collision_case(bindings::WQ_FLAG_EXCLUSIVE, 0, false)
    }
    #[test]
    fn blocked_collision_abort_detaches_both_owned_entries() -> Result {
        collision_case(0, bindings::WQ_FLAG_EXCLUSIVE, true)
    }
}
