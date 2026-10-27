// SPDX-License-Identifier: GPL-2.0
//! Initial wait-entry translation gates. Signal injection and I/O accounting
//! inspection require dedicated-thread coverage beyond these return-value cases.

use super::Completion;
use crate::{
    bindings,
    ffi::{c_long, c_ulong},
    prelude::*,
};

#[derive(Clone, Copy)]
enum Wait {
    Plain,
    Io,
    Interruptible,
    Killable,
    State(u32),
    Timeout,
    IoTimeout,
    InterruptibleTimeout,
    KillableTimeout,
}

// Nine distinct C entry points, with all three relevant explicit-state modes.
const ALL: [Wait; 11] = [
    Wait::Plain,
    Wait::Io,
    Wait::Interruptible,
    Wait::Killable,
    Wait::State(bindings::TASK_UNINTERRUPTIBLE),
    Wait::State(bindings::TASK_INTERRUPTIBLE),
    Wait::State(bindings::TASK_KILLABLE),
    Wait::Timeout,
    Wait::IoTimeout,
    Wait::InterruptibleTimeout,
    Wait::KillableTimeout,
];

const TIMED: [Wait; 4] = [
    Wait::Timeout,
    Wait::IoTimeout,
    Wait::InterruptibleTimeout,
    Wait::KillableTimeout,
];

impl Wait {
    fn is_timed(self) -> bool {
        matches!(
            self,
            Self::Timeout | Self::IoTimeout | Self::InterruptibleTimeout | Self::KillableTimeout
        )
    }

    // Private to these KUnit cases: all calls run in the test task with IRQs
    // enabled, no held locks and no injected signals. Non-timeout calls always
    // have a token or broadcast sentinel. The outer VM deadline bounds a
    // broken implementation that ignores pre-signaling and never returns.
    fn run(self, completion: &Completion, timeout: c_ulong) -> c_long {
        let raw = completion.as_raw();
        // SAFETY: Completion's owner pins initialized storage through return;
        // the test task satisfies the sleep-context requirements above. Every
        // wait removes its stack waiter before returning and retains no pointer.
        // Only small finite timeouts are supplied; converting their unsigned
        // return to signed long preserves every positive result and zero.
        unsafe {
            match self {
                Self::Plain => {
                    bindings::wait_for_completion(raw);
                    0
                }
                Self::Io => {
                    bindings::wait_for_completion_io(raw);
                    0
                }
                Self::Interruptible => bindings::wait_for_completion_interruptible(raw) as c_long,
                Self::Killable => bindings::wait_for_completion_killable(raw) as c_long,
                Self::State(state) => bindings::wait_for_completion_state(raw, state) as c_long,
                Self::Timeout => bindings::wait_for_completion_timeout(raw, timeout) as c_long,
                Self::IoTimeout => bindings::wait_for_completion_io_timeout(raw, timeout) as c_long,
                Self::InterruptibleTimeout => {
                    bindings::wait_for_completion_interruptible_timeout(raw, timeout)
                }
                Self::KillableTimeout => {
                    bindings::wait_for_completion_killable_timeout(raw, timeout)
                }
            }
        }
    }
}

fn signal(completion: &Completion) {
    // SAFETY: The owner pins initialized storage through this non-retaining
    // signal. No test here races reinitialization or frees queued storage.
    unsafe { bindings::complete(completion.as_raw()) };
}

fn try_consume(completion: &Completion) -> bool {
    // SAFETY: The owner's initialized pinned completion remains alive for this
    // nonblocking call, which retains neither a waiter nor a storage pointer.
    unsafe { bindings::try_wait_for_completion(completion.as_raw()) }
}

fn queued(completion: &Completion) -> u32 {
    // SAFETY: The owner pins initialized state. This KUnit-only read-only helper
    // serializes queue traversal with its raw lock and retains no pointer.
    unsafe { bindings::completion_waiter_count(completion.as_raw()) }
}

#[macros::kunit_tests(rusix_completion_wait)]
mod tests {
    use super::*;

    #[test]
    fn all_wait_entries_consume_presignaled_token() -> Result {
        for entry in ALL {
            let completion = KBox::pin_init(Completion::new(), GFP_KERNEL)?;
            signal(&completion);
            let result = entry.run(&completion, 7);
            assert_eq!(result, if entry.is_timed() { 7 } else { 0 });
            assert!(!try_consume(&completion));
            assert_eq!(queued(&completion), 0);
        }
        Ok(())
    }

    #[test]
    fn all_wait_entries_preserve_broadcast_sentinel() -> Result {
        let completion = KBox::pin_init(Completion::new(), GFP_KERNEL)?;
        completion.complete_all();
        for entry in ALL {
            let result = entry.run(&completion, 7);
            assert_eq!(result, if entry.is_timed() { 7 } else { 0 });
            assert!(try_consume(&completion));
            assert_eq!(queued(&completion), 0);
        }
        // SAFETY: This task exclusively owns initialized pinned storage; all
        // synchronous calls returned, and no callback/producer/observer exists.
        let count = unsafe { core::ptr::addr_of!((*completion.as_raw()).done).read() };
        assert_eq!(count, u32::MAX);
        Ok(())
    }

    #[test]
    fn all_timed_entries_distinguish_zero_timeout_states() -> Result {
        for entry in TIMED {
            let completion = KBox::pin_init(Completion::new(), GFP_KERNEL)?;
            assert_eq!(entry.run(&completion, 0), 0);
            assert_eq!(queued(&completion), 0);
            signal(&completion);
            assert_eq!(entry.run(&completion, 0), 1);
            assert!(!try_consume(&completion));
            completion.complete_all();
            assert_eq!(entry.run(&completion, 0), 1);
            assert_eq!(entry.run(&completion, 0), 1);
            assert!(try_consume(&completion));
            assert_eq!(queued(&completion), 0);
        }
        Ok(())
    }

    #[test]
    fn all_timed_entries_unlink_after_positive_timeout() -> Result {
        let timeout = crate::time::msecs_to_jiffies(20);
        assert!(timeout > 0);
        for entry in TIMED {
            let completion = KBox::pin_init(Completion::new(), GFP_KERNEL)?;
            // No producer exists until this finite wait returns. This executes
            // the scheduler path (including io_schedule_timeout for IoTimeout),
            // unlike pre-signaled calls which do not actually sleep.
            assert_eq!(entry.run(&completion, timeout), 0);
            assert_eq!(queued(&completion), 0);
            // A late signal must be available exactly once, proving timeout
            // neither leaves an enrolled waiter nor consumes a future token.
            signal(&completion);
            assert!(try_consume(&completion));
            assert!(!try_consume(&completion));
        }
        Ok(())
    }
}
