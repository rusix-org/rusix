// SPDX-License-Identifier: GPL-2.0-only
//! Locked wait consumers with process-context watchdogs and retained callbacks.
//! Production iterations have no timeout; the watchdog does not bound a broken lock.
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
        // SAFETY: Sole owning wrapper drops after the last callback/controller
        // Arc. Worker synchronously cancels embedded work before acknowledgment;
        // never-started fixtures have no armed work.
        unsafe { bindings::locked_test_free(self.0) };
    }
}
// SAFETY: C queue lock owns condition, payload, links and watchdog state. Callback
// alone writes result array, which controller reads only after completion. No
// Rust references overlay mutable fields; per-callback Arc protects work lifetime.
unsafe impl Send for Context {}
// SAFETY: Same synchronization and publication rules apply to shared references.
unsafe impl Sync for Context {}

#[pin_data]
struct Case {
    context: Context,
    #[pin]
    finished: Completion,
}
impl Case {
    fn new(mode: u32, scenario: u32, irq: bool) -> Result<Arc<Self>> {
        // SAFETY: Sleepable allocation; private finite mode/scenario inputs.
        let raw = unsafe { bindings::locked_test_alloc(mode, scenario, irq) };
        if raw.is_null() {
            return Err(ENOMEM);
        }
        let context = Context(raw);
        Arc::pin_init(
            pin_init!(Self { context, finished <- Completion::new() }),
            GFP_KERNEL,
        )
    }
    fn wait(&self, ms: u32) -> bool {
        // SAFETY: Sleepable controller retains pinned completion; finite wait.
        unsafe {
            bindings::wait_for_completion_timeout(
                self.finished.as_raw(),
                crate::time::msecs_to_jiffies(ms),
            ) != 0
        }
    }
    fn members(&self, task: &TaskRef) -> u32 {
        // SAFETY: Retained task/queue. C observes live generic entries under lock;
        // it never retains the original macro's stack-waiter pointer.
        unsafe { bindings::locked_test_members(self.context.0, task.0.cast()) }
    }
    fn blocked(&self, task: &TaskRef, min_checks: u32) -> bool {
        let start = Instant::<Monotonic>::now();
        while start.elapsed().as_millis() < 2000 {
            // SAFETY: C serializes condition counter with its queue lock.
            let checks = unsafe { bindings::locked_test_checks(self.context.0) };
            if checks >= min_checks && self.members(task) == 1 {
                // SAFETY: Retained task, IRQs enabled and no queue lock held.
                // Single rq/pi-lock observation; ordinary lock retry semantics.
                let state = unsafe { bindings::wait_lifecycle_blocked(task.0.cast()) };
                if state == 7 && self.members(task) == 1 {
                    return true;
                }
            }
            crate::time::delay::fsleep(Delta::from_millis(10));
        }
        false
    }
    fn wake(&self, publish: bool) -> u32 {
        // SAFETY: C holds queue lock for optional condition/payload publication
        // and actual locked wake. False is an intentional spurious notification.
        unsafe { bindings::locked_test_wake(self.context.0, publish) }
    }
    unsafe fn result(&self) -> [i64; 8] {
        let mut out = [0; 8];
        // SAFETY: Caller observed this callback's completion AFTER synchronous
        // watchdog cancellation; no C result writer or work callback remains.
        unsafe { bindings::locked_test_result(self.context.0, out.as_mut_ptr()) };
        out
    }
    fn cleanup(&self, task: &TaskRef) -> bool {
        let start = Instant::<Monotonic>::now();
        // SAFETY: C sets abort under queue lock and wakes all waiters. A broken
        // permanently held lock is contained by external VM timeout, not this wait.
        unsafe { bindings::locked_test_abort(self.context.0) };
        // SAFETY: Retained standalone task allows SIGUSR1 before entering wait.
        unsafe { bindings::completion_test_send_signal(task.0, bindings::SIGUSR1 as c_int) };
        // SAFETY: Referenced task; direct wake additionally covers failed enrollment.
        unsafe { bindings::wake_up_process(task.0) };
        let ms = 1000i64.saturating_sub(start.elapsed().as_millis()).max(0);
        self.wait(ms as u32)
    }
}

struct TaskRef(*mut bindings::task_struct);
impl Drop for TaskRef {
    fn drop(&mut self) {
        // SAFETY: Independent reference supplied by successful creation.
        unsafe { bindings::put_task_struct(self.0) };
    }
}
unsafe extern "C" fn callback(data: *mut c_void) -> c_int {
    // SAFETY: Exactly one transferred Arc consumed by this sole callback;
    // no stop-before-entry mechanism bypasses its reclamation.
    let case = unsafe { Arc::<Case>::from_raw(data.cast()) };
    // SAFETY: Dedicated sleepable callback owns this fixture's only worker and
    // retains context through all queue use and synchronous work cancellation.
    unsafe { bindings::locked_test_run(case.context.0) };
    case.finished.complete_all();
    // No C context access follows ack; retained Arc covers return gap.
    0
}
fn spawn(case: &Arc<Case>) -> Result<TaskRef> {
    let data = Arc::into_raw(case.clone()).cast_mut().cast();
    // SAFETY: Callback ABI matches; one Arc transfers if creation succeeds.
    let raw = unsafe { bindings::completion_test_kthread_create(Some(callback), data) };
    let raw = match crate::error::from_err_ptr(raw) {
        Ok(raw) => raw,
        Err(error) => {
            // SAFETY: Failed create never executes callback; reclaim its Arc.
            unsafe { drop(Arc::<Case>::from_raw(data.cast())) };
            return Err(error);
        }
    };
    let task = TaskRef(raw);
    // SAFETY: Referenced stopped task; no fallible step before initial wake.
    unsafe { bindings::wake_up_process(task.0) };
    Ok(task)
}

fn immediate(mode: u32, scenario: u32, irq: bool) -> Result<[i64; 8]> {
    let case = Case::new(mode, scenario, irq)?;
    let start = Instant::<Monotonic>::now();
    let task = spawn(&case)?;
    let done = case.wait(1000);
    let members = case.members(&task);
    let elapsed = start.elapsed().as_millis();
    let cleaned = case.cleanup(&task);
    // SAFETY: Never read results without exact callback acknowledgment.
    let result = if done {
        unsafe { case.result() }
    } else {
        [-1; 8]
    };
    drop(task);
    assert!(done && cleaned && elapsed < 5000);
    assert_eq!(members, 0);
    Ok(result)
}

#[macros::kunit_tests(rusix_completion_wait_locked)]
mod tests {
    use super::*;

    #[test]
    fn pending_iteration_preserves_lock_state_irq_and_enrollment() -> Result {
        for irq in [false, true] {
            // Both first and repeated calls leave TASK_INTERRUPTIBLE and one
            // linked entry; flags preserved, then original caller poisons links.
            assert_eq!(immediate(0, 0, irq)?, [-512, 1, 1, 1, 1, 31, 0, 0]);
        }
        Ok(())
    }

    #[test]
    fn original_macro_distinguishes_initial_condition_from_pending_error() -> Result {
        for irq in [false, true] {
            // Initially true skips iteration even with pending signal. Entered
            // wait errors before its inner condition could become true: one eval.
            assert_eq!(immediate(1, 0, irq)?, [0, 1, 1, 1, 1, 1, 1, 0]);
            assert_eq!(immediate(1, 1, irq)?, [-512, 1, 1, 1, 1, 1, 1, 0]);
        }
        Ok(())
    }

    #[test]
    fn blocked_spurious_wake_rechecks_before_locked_publication() -> Result {
        for irq in [false, true] {
            let case = Case::new(2, 0, irq)?;
            let start = Instant::<Monotonic>::now();
            let task = spawn(&case)?;
            let blocked = case.blocked(&task, 1);
            let before = case.wake(false);
            // Increased condition evaluations plus a fresh scheduler observation
            // show the worker processed the spurious notification and waited again.
            let reblocked = case.blocked(&task, before + 1);
            case.wake(true);
            let done = case.wait(1000);
            let members = case.members(&task);
            let elapsed = start.elapsed().as_millis();
            let cleaned = case.cleanup(&task);
            // SAFETY: Callback acknowledgment follows all C and watchdog accesses.
            let result = if done {
                unsafe { case.result() }
            } else {
                [-1; 8]
            };
            drop(task);
            assert!(blocked && reblocked && done && cleaned && elapsed < 5000);
            assert_eq!(members, 0);
            assert_eq!(&result[..5], &[0, 1, 1, 1, 1]);
            assert!(result[5] >= i64::from(before) + 2);
            assert_eq!(&result[6..], &[0x1234, 0]);
        }
        Ok(())
    }

    #[test]
    fn blocked_signal_returns_error_with_caller_cleanup() -> Result {
        for irq in [false, true] {
            let case = Case::new(3, 0, irq)?;
            let start = Instant::<Monotonic>::now();
            let task = spawn(&case)?;
            let blocked = case.blocked(&task, 1);
            // SAFETY: Retained standalone task allows SIGUSR1 before enrollment.
            let sent = unsafe {
                bindings::completion_test_send_signal(task.0, bindings::SIGUSR1 as c_int)
            };
            let done = case.wait(1000);
            let members = case.members(&task);
            let elapsed = start.elapsed().as_millis();
            let cleaned = case.cleanup(&task);
            // SAFETY: Result publication observed for this exact worker.
            let result = if done {
                unsafe { case.result() }
            } else {
                [-1; 8]
            };
            drop(task);
            assert!(blocked && done && cleaned && elapsed < 5000);
            assert_eq!((sent, members), (0, 0));
            assert_eq!(&result[..5], &[-512, 1, 1, 1, 1]);
            assert!(result[5] >= 2);
            assert_eq!(&result[6..], &[0, 0]);
        }
        Ok(())
    }
}
