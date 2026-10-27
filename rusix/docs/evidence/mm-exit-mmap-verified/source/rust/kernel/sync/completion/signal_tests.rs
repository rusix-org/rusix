// SPDX-License-Identifier: GPL-2.0
//! Dedicated-thread tests for completion signal handling.
//! Built-in KUnit only; unfinished callback ownership is not module-unload proof.

use super::Completion;
use crate::{
    bindings,
    ffi::{c_int, c_void},
    prelude::*,
    sync::{
        atomic::{Atomic, Relaxed},
        Arc,
    },
    task::Task,
    time::{Delta, Instant, Monotonic},
};

#[derive(Clone, Copy)]
enum Kind {
    Interruptible,
    Killable,
}

#[derive(Clone, Copy)]
enum Injection {
    Pending,
    Enrolled,
}

#[pin_data]
struct Case {
    #[pin]
    event: Completion,
    #[pin]
    finished: Completion,
    result: Atomic<i64>,
    elapsed_jiffies: Atomic<u64>,
    sent: Atomic<i32>,
    pending_before: Atomic<u32>,
    kind: Kind,
    injection: Injection,
    signal: c_int,
    presignaled: bool,
    timeout_ms: u32,
}

impl Case {
    fn new(
        kind: Kind,
        injection: Injection,
        signal: c_int,
        presignaled: bool,
        timeout_ms: u32,
    ) -> impl PinInit<Self> {
        pin_init!(Self {
            event <- Completion::new(),
            finished <- Completion::new(),
            result: Atomic::new(i64::MIN),
            elapsed_jiffies: Atomic::new(0),
            sent: Atomic::new(i32::MIN),
            pending_before: Atomic::new(0),
            kind,
            injection,
            signal,
            presignaled,
            timeout_ms,
        })
    }
}

// Owns one extra task reference, never the task's callback or its Arc. This
// private handle is used only by the KUnit controller and never escapes a case.
struct TaskRef(*mut bindings::task_struct);

impl Drop for TaskRef {
    fn drop(&mut self) {
        // SAFETY: Successful create acquired this exact independent reference.
        // Dropping it cannot invalidate the running task's own lifetime or the
        // callback's separately retained Arc; no pointer is used after this drop.
        unsafe { bindings::put_task_struct(self.0) };
    }
}

unsafe extern "C" fn run_case(data: *mut c_void) -> c_int {
    // SAFETY: The successful creator transfers one into_raw reference to this
    // sole callback. C passes data unchanged and invokes the callback once.
    // No stop-before-start path exists. This Arc owns all callback storage
    // through return, including when its controller reports a bounded failure.
    let case = unsafe { Arc::<Case>::from_raw(data.cast()) };
    // SAFETY: This is a fresh standalone kthread with private sighand, never a
    // shared kworker/KUnit task. Its immutable configuration is SIGUSR1/SIGKILL.
    unsafe { bindings::completion_test_allow_signal(case.signal) };
    if matches!(case.injection, Injection::Pending) {
        // SAFETY: current_raw is this live callback task. Signal is allowed
        // above and is handled by the wait predicate, never a userspace return.
        let sent =
            unsafe { bindings::completion_test_send_signal(Task::current_raw(), case.signal) };
        case.sent.store(sent, Relaxed);
        // SAFETY: This observes pending state of the live current callback task.
        let pending = unsafe { bindings::signal_pending(Task::current_raw()) } != 0;
        case.pending_before.store(u32::from(pending), Relaxed);
    }
    if case.presignaled {
        // SAFETY: The Arc pins initialized storage; this call retains no pointer.
        unsafe { bindings::complete(case.event.as_raw()) };
    }
    let timeout = crate::time::msecs_to_jiffies(case.timeout_ms);
    // SAFETY: The callback is a sleepable dedicated task with IRQs enabled and
    // no held locks. Its Arc pins the initialized completion until return. Both
    // waits unlink stack storage on all exits, and timeout is finite/nonzero.
    // SAFETY: This helper performs a marked read of the global jiffy counter;
    // no Rust reference to concurrently written C storage is created.
    let before = unsafe { bindings::completion_test_jiffies() };
    // SAFETY: This dedicated task satisfies the sleepable-context and pinned
    // storage requirements described above; each finite wait unlinks on return.
    let result = unsafe {
        match case.kind {
            Kind::Interruptible => {
                bindings::wait_for_completion_interruptible_timeout(case.event.as_raw(), timeout)
            }
            Kind::Killable => {
                bindings::wait_for_completion_killable_timeout(case.event.as_raw(), timeout)
            }
        }
    };
    // SAFETY: Same marked global read as above. Wrapping subtraction handles
    // jiffy rollover; the tested interval is far below half the counter range.
    let after = unsafe { bindings::completion_test_jiffies() };
    case.elapsed_jiffies
        .store(after.wrapping_sub(before) as u64, Relaxed);
    case.result.store(result as i64, Relaxed);
    case.finished.complete_all();
    // Pending signals belong solely to this standalone thread, which exits
    // after dropping the Arc. It never rejoins a shared worker pool.
    0
}

fn start(case: &Arc<Case>) -> Result<TaskRef> {
    let data = Arc::into_raw(case.clone()).cast_mut().cast();
    // SAFETY: Callback ABI matches; data owns one Arc reference. The helper
    // either returns an error without executing the callback, or a stopped
    // task plus an independent task reference. No borrowed stack data is passed.
    let raw = unsafe { bindings::completion_test_kthread_create(Some(run_case), data) };
    let raw = match crate::error::from_err_ptr(raw) {
        Ok(task) => task,
        Err(error) => {
            // SAFETY: Creation failed, so the callback cannot execute. Reclaim
            // exactly the into_raw reference above; the controller's Arc remains.
            unsafe { drop(Arc::<Case>::from_raw(data.cast())) };
            return Err(error);
        }
    };
    let task = TaskRef(raw);
    // SAFETY: The helper returns a live stopped task protected by our extra
    // reference. No failure/early return is allowed between success and this
    // wakeup; the callback alone now owns/reclaims the transferred Arc.
    unsafe { bindings::wake_up_process(task.0) };
    Ok(task)
}

fn wait_finished(case: &Case) -> bool {
    // SAFETY: Called by the sleepable test task, with no held locks or disabled
    // IRQs. Its Arc pins initialized storage; the finite wait retains no waiter.
    unsafe {
        bindings::wait_for_completion_timeout(
            case.finished.as_raw(),
            crate::time::msecs_to_jiffies(1000),
        ) != 0
    }
}

fn check(
    kind: Kind,
    injection: Injection,
    signal: c_int,
    presignaled: bool,
    ignored: bool,
) -> Result {
    let timeout_ms = if ignored { 20 } else { 10000 };
    let case = Arc::pin_init(
        Case::new(kind, injection, signal, presignaled, timeout_ms),
        GFP_KERNEL,
    )?;
    let started = Instant::<Monotonic>::now();
    let task = start(&case)?;
    let mut enrolled = !matches!(injection, Injection::Enrolled);
    let sent = if matches!(injection, Injection::Enrolled) {
        for _ in 0..100 {
            // SAFETY: Our Arc pins initialized storage; the helper observes the
            // queue under its raw lock and retains neither pointer nor waiter.
            if unsafe { bindings::completion_waiter_count(case.event.as_raw()) } == 1 {
                enrolled = true;
                break;
            }
            crate::time::delay::fsleep(Delta::from_millis(10));
        }
        // SAFETY: TaskRef keeps the dedicated task alive even if its callback
        // finished early. Enrollment implies allow_signal already executed.
        // If enrollment failed, signaling is cleanup only and the case fails.
        unsafe { bindings::completion_test_send_signal(task.0, signal) }
    } else {
        0
    };
    let finished_before_cleanup = wait_finished(&case);
    let elapsed = started.elapsed().as_millis();
    let result = case.result.load(Relaxed);
    let callback_sent = case.sent.load(Relaxed);
    let pending_before = case.pending_before.load(Relaxed);
    // SAFETY: The initialized event is pinned by our Arc; both helpers serialize
    // with any remaining waiter and retain no pointer. Inspect before cleanup
    // changes the counter to its permanent broadcast state.
    let queued_before_cleanup = unsafe { bindings::completion_waiter_count(case.event.as_raw()) };
    // SAFETY: The same initialized pinned storage and non-retaining call rules apply.
    let leftover = unsafe { bindings::try_wait_for_completion(case.event.as_raw()) };
    // Always release any blocked waiter before assertions, including enrollment
    // failure or early return-value mismatch. A broken callback may outlive this
    // task's case, but owns its Arc. This is not a proof that it has exited.
    case.event.complete_all();
    // Drop the extra task reference before assertions; the task and callback
    // own their independent lifetime. No task pointer is accessed afterward.
    drop(task);
    assert!(enrolled);
    assert!(finished_before_cleanup);
    assert!(elapsed < 5000);
    assert_eq!(sent, 0);
    assert_eq!(queued_before_cleanup, 0);
    assert!(!leftover);
    if matches!(injection, Injection::Pending) {
        assert_eq!(callback_sent, 0);
        assert_eq!(pending_before, 1);
    }
    if presignaled {
        assert_eq!(result, crate::time::msecs_to_jiffies(timeout_ms) as i64);
    } else if ignored {
        assert_eq!(result, 0);
        assert!(
            case.elapsed_jiffies.load(Relaxed) >= crate::time::msecs_to_jiffies(timeout_ms) as u64
        );
    } else {
        assert_eq!(result, -(bindings::ERESTARTSYS as i64));
    }
    Ok(())
}

#[macros::kunit_tests(rusix_completion_signal)]
mod tests {
    use super::*;

    #[test]
    fn pending_signals_interrupt_timed_waits() -> Result {
        check(
            Kind::Interruptible,
            Injection::Pending,
            bindings::SIGUSR1 as c_int,
            false,
            false,
        )?;
        check(
            Kind::Killable,
            Injection::Pending,
            bindings::SIGKILL as c_int,
            false,
            false,
        )
    }

    #[test]
    fn enrolled_waits_wake_for_signals() -> Result {
        check(
            Kind::Interruptible,
            Injection::Enrolled,
            bindings::SIGUSR1 as c_int,
            false,
            false,
        )?;
        check(
            Kind::Killable,
            Injection::Enrolled,
            bindings::SIGKILL as c_int,
            false,
            false,
        )
    }

    #[test]
    fn presignaled_token_wins_over_pending_signal() -> Result {
        check(
            Kind::Interruptible,
            Injection::Pending,
            bindings::SIGUSR1 as c_int,
            true,
            false,
        )?;
        check(
            Kind::Killable,
            Injection::Pending,
            bindings::SIGKILL as c_int,
            true,
            false,
        )
    }

    #[test]
    fn killable_wait_ignores_nonfatal_pending_signal() -> Result {
        check(
            Kind::Killable,
            Injection::Pending,
            bindings::SIGUSR1 as c_int,
            false,
            true,
        )
    }
}
