// SPDX-License-Identifier: GPL-2.0

//! Completion support.
//!
//! Reference: <https://docs.kernel.org/scheduler/completion.html>
//!
//! C header: [`include/linux/completion.h`](srctree/include/linux/completion.h)

use crate::{bindings, prelude::*, types::Opaque};

/// Synchronization primitive to signal when a certain task has been completed.
///
/// The [`Completion`] synchronization primitive signals when a certain task has been completed by
/// waking up other tasks that have been queued up to wait for the [`Completion`] to be completed.
///
/// # Examples
///
/// ```
/// use kernel::sync::{Arc, Completion};
/// use kernel::workqueue::{self, impl_has_work, new_work, Work, WorkItem};
///
/// #[pin_data]
/// struct MyTask {
///     #[pin]
///     work: Work<MyTask>,
///     #[pin]
///     done: Completion,
/// }
///
/// impl_has_work! {
///     impl HasWork<Self> for MyTask { self.work }
/// }
///
/// impl MyTask {
///     fn new() -> Result<Arc<Self>> {
///         let this = Arc::pin_init(pin_init!(MyTask {
///             work <- new_work!("MyTask::work"),
///             done <- Completion::new(),
///         }), GFP_KERNEL)?;
///
///         let _ = workqueue::system().enqueue(this.clone());
///
///         Ok(this)
///     }
///
///     fn wait_for_completion(&self) {
///         self.done.wait_for_completion();
///
///         pr_info!("Completion: task complete\n");
///     }
/// }
///
/// impl WorkItem for MyTask {
///     type Pointer = Arc<MyTask>;
///
///     fn run(this: Arc<MyTask>) {
///         // process this task
///         this.done.complete_all();
///     }
/// }
///
/// let task = MyTask::new()?;
/// task.wait_for_completion();
/// # Ok::<(), Error>(())
/// ```
#[pin_data]
pub struct Completion {
    #[pin]
    inner: Opaque<bindings::completion>,
}

// SAFETY: `Completion` is safe to be send to any task.
unsafe impl Send for Completion {}

// SAFETY: `Completion` is safe to be accessed concurrently.
unsafe impl Sync for Completion {}

impl Completion {
    /// Create an initializer for a new [`Completion`].
    pub fn new() -> impl PinInit<Self> {
        pin_init!(Self {
            inner <- Opaque::ffi_init(|slot: *mut bindings::completion| {
                // SAFETY: `slot` is a valid pointer to an uninitialized `struct completion`.
                unsafe { bindings::init_completion(slot) };
            }),
        })
    }

    fn as_raw(&self) -> *mut bindings::completion {
        self.inner.get()
    }

    /// Signal all tasks waiting on this completion.
    ///
    /// This method wakes up all tasks waiting on this completion; after this operation the
    /// completion is permanently done, i.e. signals all current and future waiters.
    pub fn complete_all(&self) {
        // SAFETY: `self.as_raw()` is a pointer to a valid `struct completion`.
        unsafe { bindings::complete_all(self.as_raw()) };
    }

    /// Wait for completion of a task.
    ///
    /// This method waits for the completion of a task; it is not interruptible and there is no
    /// timeout.
    ///
    /// See also [`Completion::complete_all`].
    pub fn wait_for_completion(&self) {
        // SAFETY: `self.as_raw()` is a pointer to a valid `struct completion`.
        unsafe { bindings::wait_for_completion(self.as_raw()) };
    }
}

// These contract tests run against the selected C or Rust completion entry points.
// The separate layout suite covers bounded worker handoff and queue cleanup.
#[macros::kunit_tests(rusix_completion_contract)]
mod contract_tests {
    use super::*;

    #[test]
    fn initial_state_has_no_token() -> Result {
        let completion = KBox::pin_init(Completion::new(), GFP_KERNEL)?;
        // SAFETY: Initialization pins valid C completion storage. This test is
        // its only user; both C calls are nonblocking and retain no pointer.
        assert!(unsafe { !bindings::completion_done(completion.as_raw()) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { !bindings::try_wait_for_completion(completion.as_raw()) });
        Ok(())
    }

    #[test]
    fn presignals_are_consumed_once_each() -> Result {
        let completion = KBox::pin_init(Completion::new(), GFP_KERNEL)?;
        // SAFETY: The initialized, pinned completion outlives these synchronous
        // C calls; no other task accesses it and no waiter is enrolled.
        unsafe { bindings::complete(completion.as_raw()) };
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        unsafe { bindings::complete(completion.as_raw()) };
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { bindings::completion_done(completion.as_raw()) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { bindings::try_wait_for_completion(completion.as_raw()) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { bindings::completion_done(completion.as_raw()) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { bindings::try_wait_for_completion(completion.as_raw()) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { !bindings::try_wait_for_completion(completion.as_raw()) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { !bindings::completion_done(completion.as_raw()) });
        Ok(())
    }

    #[test]
    fn broadcast_persists_until_quiescent_reset() -> Result {
        let completion = KBox::pin_init(Completion::new(), GFP_KERNEL)?;
        completion.complete_all();
        // SAFETY: Only this test uses the pinned initialized storage. Every
        // operation returns before the next starts; no producer or waiter can
        // overlap reset. Writing just `done` matches inline reinit_completion,
        // without moving/reinitializing the self-referential wait queue.
        assert!(unsafe { bindings::try_wait_for_completion(completion.as_raw()) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { bindings::try_wait_for_completion(completion.as_raw()) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert_eq!(
            unsafe { bindings::wait_for_completion_timeout(completion.as_raw(), 0) },
            1
        );
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { bindings::completion_done(completion.as_raw()) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        unsafe { core::ptr::addr_of_mut!((*completion.as_raw()).done).write(0) };
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { !bindings::completion_done(completion.as_raw()) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { !bindings::try_wait_for_completion(completion.as_raw()) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        unsafe { bindings::complete(completion.as_raw()) };
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { bindings::try_wait_for_completion(completion.as_raw()) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { !bindings::try_wait_for_completion(completion.as_raw()) });
        Ok(())
    }

    #[test]
    fn zero_timeout_reports_completion_and_consumes_token() -> Result {
        let completion = KBox::pin_init(Completion::new(), GFP_KERNEL)?;
        // SAFETY: KUnit runs in sleepable task context with IRQs enabled. The
        // initialized pinned completion lives through each C call. Zero timeout
        // cannot leave a pending wait; C unlinks its stack waiter before return.
        // No worker or asynchronous callback can access this storage afterward.
        assert_eq!(
            unsafe { bindings::wait_for_completion_timeout(completion.as_raw(), 0) },
            0
        );
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        unsafe { bindings::complete(completion.as_raw()) };
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert_eq!(
            unsafe { bindings::wait_for_completion_timeout(completion.as_raw(), 0) },
            1
        );
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert_eq!(
            unsafe { bindings::wait_for_completion_timeout(completion.as_raw(), 0) },
            0
        );
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { !bindings::try_wait_for_completion(completion.as_raw()) });
        Ok(())
    }

    #[test]
    fn signal_saturates_instead_of_wrapping() -> Result {
        let completion = KBox::pin_init(Completion::new(), GFP_KERNEL)?;
        // SAFETY: Storage is initialized and pinned, and never shared. Seed a
        // valid counter state directly to avoid billions of calls. There is no
        // concurrent access to `done`; the wait queue remains initialized and
        // empty. C calls return before the raw read or storage destruction.
        unsafe { core::ptr::addr_of_mut!((*completion.as_raw()).done).write(u32::MAX - 1) };
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        unsafe { bindings::complete(completion.as_raw()) };
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        unsafe { bindings::complete(completion.as_raw()) };
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { bindings::try_wait_for_completion(completion.as_raw()) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { bindings::try_wait_for_completion(completion.as_raw()) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert_eq!(
            unsafe { core::ptr::addr_of!((*completion.as_raw()).done).read() },
            u32::MAX
        );
        Ok(())
    }
}

#[cfg(CONFIG_KUNIT = "y")]
mod layout_tests;

#[cfg(CONFIG_KUNIT = "y")]
mod wait_tests;

#[cfg(CONFIG_KUNIT = "y")]
mod signal_tests;

#[cfg(CONFIG_KUNIT = "y")]
mod swait_tests;

#[cfg(CONFIG_KUNIT = "y")]
mod wake_tests;

#[cfg(CONFIG_KUNIT = "y")]
mod lifecycle_tests;

#[cfg(CONFIG_KUNIT = "y")]
mod woken_tests;

#[cfg(CONFIG_KUNIT = "y")]
mod bit_tests;

#[cfg(CONFIG_KUNIT = "y")]
mod locked_tests;
