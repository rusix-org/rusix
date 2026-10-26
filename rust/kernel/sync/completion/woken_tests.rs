// SPDX-License-Identifier: GPL-2.0-only
//! Dedicated WOKEN consumers. A latch is separate from the fixture condition.
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
        // SAFETY: Sole owning wrapper drops only after controller and callback
        // Arcs. Callback has removed its entry before its final context access.
        unsafe { bindings::wait_woken_test_free(self.0) };
    }
}
// SAFETY: Opaque C storage; queue links use the queue lock, condition publication
// uses release/acquire, abort/payload/flags follow marked C protocols. The sole
// callback writes result fields, read only after completion acknowledgment.
unsafe impl Send for Context {}
// SAFETY: Same synchronization; no Rust references overlay mutable C fields.
unsafe impl Sync for Context {}

#[pin_data]
struct Case {
    context: Context,
    #[pin]
    finished: Completion,
    timeout_ms: u32,
}
impl Case {
    fn new(mode: u32, timeout_ms: u32) -> Result<Arc<Self>> {
        // SAFETY: Private mode, sleepable context; newly owned allocation or NULL.
        let raw = unsafe { bindings::wait_woken_test_alloc(mode) };
        if raw.is_null() {
            return Err(ENOMEM);
        }
        let context = Context(raw);
        Arc::pin_init(
            pin_init!(Self {
                context,
                finished <- Completion::new(),
                timeout_ms,
            }),
            GFP_KERNEL,
        )
    }

    fn wait(&self, ms: u32) -> bool {
        // SAFETY: Controller is sleepable; Arc retains initialized completion.
        // complete_all allows later bounded cleanup to observe the same event.
        unsafe {
            bindings::wait_for_completion_timeout(
                self.finished.as_raw(),
                crate::time::msecs_to_jiffies(ms),
            ) != 0
        }
    }

    fn members(&self) -> u32 {
        // SAFETY: Initialized retained queue, C observes membership under lock.
        unsafe { bindings::wait_woken_test_members(self.context.0) }
    }

    fn blocked(&self, task: &TaskRef) -> bool {
        let start = Instant::<Monotonic>::now();
        while start.elapsed().as_millis() < 2000 {
            if self.members() == 1 {
                // SAFETY: TaskRef retained; IRQ-enabled controller holds no queue
                // lock. Existing single rq/pi-lock sample, no inactivity loop.
                let sample = unsafe { bindings::wait_lifecycle_blocked(task.0.cast()) };
                if sample == 7 && self.members() == 1 {
                    return true;
                }
            }
            crate::time::delay::fsleep(Delta::from_millis(10));
        }
        false
    }

    fn publish(&self) {
        // SAFETY: Private ordinary-mode callsite and retained initialized queue;
        // release/acquire publishes fixture payload independently of WOKEN.
        unsafe { bindings::wait_woken_test_publish(self.context.0) };
    }

    fn bit_probe(&self, command: u32) -> [i64; 2] {
        let mut out = [0; 2];
        // SAFETY: Private commands 0..2, exclusive two-word output. C supplies
        // live key storage and confirms exact membership under queue.lock before
        // touching entry/callback, including failed startup/expiry observations.
        unsafe { bindings::wait_woken_test_probe(self.context.0, command, out.as_mut_ptr()) };
        out
    }

    // Caller must have observed this callback's completion.
    unsafe fn result(&self) -> [i64; 8] {
        let mut out = [0; 8];
        // SAFETY: Completion publishes all result writes and no further C access
        // follows acknowledgment. Output is exclusive local storage.
        unsafe { bindings::wait_woken_test_result(self.context.0, out.as_mut_ptr()) };
        out
    }

    fn cleanup(&self, task: &TaskRef) -> bool {
        let start = Instant::<Monotonic>::now();
        // SAFETY: Retained initialized fixture; C publishes abort and calls wake
        // with a real matching bit key, even for failure paths. Never NULL.
        unsafe { bindings::wait_woken_test_abort(self.context.0) };
        // SAFETY: Independent task reference; direct wake is additional fallback,
        // while callback's WOKEN latch closes abort-before-sleep races.
        unsafe { bindings::wake_up_process(task.0) };
        let remaining = 1000i64.saturating_sub(start.elapsed().as_millis()).max(0);
        self.wait(remaining as u32)
    }
}

struct TaskRef(*mut bindings::task_struct);
impl Drop for TaskRef {
    fn drop(&mut self) {
        // SAFETY: Successful create supplied this independent retained reference.
        unsafe { bindings::put_task_struct(self.0) };
    }
}

unsafe extern "C" fn callback(data: *mut c_void) -> c_int {
    // SAFETY: Creator transfers exactly one Arc to the sole callback. No stop
    // before entry can bypass callback reclamation of that reference.
    let case = unsafe { Arc::<Case>::from_raw(data.cast()) };
    // SAFETY: Private standalone sleepable task, sole worker for this fixture;
    // callback Arc retains queue/entry through the finite wait and explicit remove.
    unsafe { bindings::wait_woken_test_run(case.context.0, case.timeout_ms) };
    case.finished.complete_all();
    // No C context access follows acknowledgment; Arc protects the return gap.
    0
}
fn spawn(case: &Arc<Case>) -> Result<TaskRef> {
    let data = Arc::into_raw(case.clone()).cast_mut().cast();
    // SAFETY: Matching ABI, one transferred Arc; create failure invokes no callback.
    let raw = unsafe { bindings::completion_test_kthread_create(Some(callback), data) };
    let raw = match crate::error::from_err_ptr(raw) {
        Ok(raw) => raw,
        Err(error) => {
            // SAFETY: No callback exists; reclaim precisely the transferred Arc.
            unsafe { drop(Arc::<Case>::from_raw(data.cast())) };
            return Err(error);
        }
    };
    let task = TaskRef(raw);
    // SAFETY: Retained stopped task; no failure/return gap before starting it.
    unsafe { bindings::wake_up_process(task.0) };
    Ok(task)
}

#[macros::kunit_tests(rusix_completion_wait_woken)]
mod tests {
    use super::*;

    #[test]
    fn prelatched_running_callback_skips_schedule_and_preserves_membership() -> Result {
        let case = Case::new(0, 10000)?;
        let start = Instant::<Monotonic>::now();
        let task = spawn(&case)?;
        let done = case.wait(1000);
        let elapsed = start.elapsed().as_millis();
        let members = case.members();
        let cleaned = case.cleanup(&task);
        // SAFETY: Result reads only after this exact callback acknowledgment.
        let result = if done {
            unsafe { case.result() }
        } else {
            [-1; 8]
        };
        drop(task);
        assert!(done && cleaned);
        assert!(elapsed < 5000);
        assert_eq!(members, 0);
        assert_eq!(
            result,
            [
                crate::time::msecs_to_jiffies(10000) as i64,
                0,
                0x100,
                1,
                1,
                1,
                0,
                0
            ]
        );
        Ok(())
    }

    #[test]
    fn zero_and_positive_timeout_restore_state_without_autoremove() -> Result {
        for (mode, timeout) in [(1, 10000), (3, 200)] {
            let case = Case::new(mode, timeout)?;
            let start = Instant::<Monotonic>::now();
            let task = spawn(&case)?;
            let blocked = mode == 1 || case.blocked(&task);
            let done = case.wait(1000);
            let elapsed = start.elapsed().as_millis();
            let members = case.members();
            let cleaned = case.cleanup(&task);
            // SAFETY: No C result read unless worker publication was observed.
            let result = if done {
                unsafe { case.result() }
            } else {
                [-1; 8]
            };
            drop(task);
            assert!(blocked && done && cleaned);
            assert!(elapsed < 5000);
            assert_eq!(members, 0);
            assert_eq!(result, [0, 0, 0x100, 1, 1, 1, 0, 0]);
        }
        Ok(())
    }

    #[test]
    fn blocked_woken_consumer_observes_published_condition() -> Result {
        let case = Case::new(2, 10000)?;
        let start = Instant::<Monotonic>::now();
        let task = spawn(&case)?;
        let blocked = case.blocked(&task);
        case.publish();
        let done = case.wait(1000);
        let elapsed = start.elapsed().as_millis();
        let members = case.members();
        let cleaned = case.cleanup(&task);
        // SAFETY: Slot results become immutable before completion acknowledgment.
        let result = if done {
            unsafe { case.result() }
        } else {
            [-1; 8]
        };
        drop(task);
        assert!(blocked && done && cleaned);
        assert!(elapsed < 5000);
        assert_eq!(members, 0);
        assert!(result[0] > 0 && result[0] <= crate::time::msecs_to_jiffies(10000) as i64);
        // A callback can relatch after wait_woken clears; unrelated bits persist.
        assert_eq!(result[2] & !(bindings::WQ_FLAG_WOKEN as i64), 0x100);
        assert_eq!(&result[3..7], &[1, 1, 1, 0x1234]);
        Ok(())
    }

    #[test]
    fn bit_keys_filter_address_and_bit_but_not_timeout() -> Result {
        let case = Case::new(4, 10000)?;
        let start = Instant::<Monotonic>::now();
        let task = spawn(&case)?;
        let blocked = case.blocked(&task);
        let wrong_address = case.bit_probe(0);
        let after_address = case.blocked(&task);
        let wrong_bit = case.bit_probe(1);
        let after_bit = case.blocked(&task);
        let matched = case.bit_probe(2);
        let done = case.wait(1000);
        let elapsed = start.elapsed().as_millis();
        let members = case.members();
        let cleaned = case.cleanup(&task);
        // SAFETY: No read without exact completion acknowledgment.
        let result = if done {
            unsafe { case.result() }
        } else {
            [-1; 8]
        };
        drop(task);
        assert!(blocked && after_address && after_bit && done && cleaned);
        assert!(elapsed < 5000);
        assert_eq!(members, 0);
        assert_eq!(wrong_address, [0, 0x100]);
        assert_eq!(wrong_bit, [0, 0x100]);
        assert_eq!(matched[0], 1);
        assert!(result[0] > 0 && result[0] <= crate::time::msecs_to_jiffies(10000) as i64);
        assert_eq!(result[2] & !(bindings::WQ_FLAG_WOKEN as i64), 0x100);
        assert_eq!(&result[3..7], &[1, 1, 1, 0x5678]);
        Ok(())
    }
}
