// SPDX-License-Identifier: GPL-2.0
//! Test-only C/Rust storage interoperability, not a completion implementation.

use core::{
    cell::UnsafeCell,
    convert::Infallible,
    mem::{align_of, offset_of, size_of},
};

use crate::{
    bindings,
    prelude::*,
    types::{NotThreadSafe, Opaque},
};

// All C-mutated fields permit interior mutation. The opaque queue contains a
// self-referential list after initialization and must never move. There is no
// exposed concurrent API: NotThreadSafe prohibits Send/Sync, and fields are private.
#[repr(C)]
#[pin_data]
struct Layout {
    done: UnsafeCell<u32>,
    #[pin]
    wait: Opaque<bindings::swait_queue_head>,
    _task: NotThreadSafe,
}

// These assertions are evaluated against bindings for the actual kernel target
// and configuration, including raw-spinlock/lockdep layout. They are not an ABI
// promise for other architectures or configurations that have not been built.
const _: () = {
    assert!(size_of::<Layout>() == size_of::<bindings::completion>());
    assert!(align_of::<Layout>() == align_of::<bindings::completion>());
    assert!(offset_of!(Layout, done) == offset_of!(bindings::completion, done));
    assert!(offset_of!(Layout, wait) == offset_of!(bindings::completion, wait));
    assert!(size_of::<UnsafeCell<u32>>() == size_of::<core::ffi::c_uint>());
    assert!(align_of::<UnsafeCell<u32>>() == align_of::<core::ffi::c_uint>());
};

impl Layout {
    fn new() -> impl PinInit<Self> {
        // SAFETY: PinInit supplies writable, correctly aligned final storage.
        // First initialize every Rust field, including the zero-sized marker;
        // Opaque permits its queue bytes to be uninitialized at this point.
        // repr(C), the assertions above, and Opaque's transparent representation
        // make the C pointer address the corresponding done and wait storage.
        // init_completion initializes done and the queue in place, without
        // reading uninitialized queue contents. No references to those fields
        // exist during the call. Nothing moves after queue self-links are set.
        unsafe {
            pin_init::pin_init_from_closure::<Self, Infallible>(|slot| {
                slot.write(Self {
                    done: UnsafeCell::new(0),
                    wait: Opaque::uninit(),
                    _task: NotThreadSafe,
                });
                bindings::init_completion(slot.cast());
                Ok(())
            })
        }
    }
}

#[macros::kunit_tests(rusix_completion_layout)]
mod tests {
    use super::*;

    #[test]
    fn c_operations_share_pinned_rust_owned_storage() -> Result {
        let owned = KBox::pin_init(Layout::new(), GFP_KERNEL)?;
        let raw = (&*owned as *const Layout)
            .cast_mut()
            .cast::<bindings::completion>();
        // SAFETY: Layout::new initialized valid C completion state in this
        // pinned allocation. C only mutates the UnsafeCell-backed done/queue
        // fields, never the Rust marker. The shared Layout reference therefore
        // does not forbid these mutations. No field references are manufactured
        // and the pointer is never retained by these nonblocking C operations.
        // This task is the only owner/user: raw Rust observations and reset do
        // not race with C, a producer, a waiter, or an interrupt callback.
        unsafe {
            assert_eq!(owned.done.get().read(), 0);
            bindings::complete(raw);
            assert_eq!(owned.done.get().read(), 1);
            assert!(bindings::try_wait_for_completion(raw));
            assert_eq!(owned.done.get().read(), 0);
            assert!(!bindings::try_wait_for_completion(raw));
            bindings::complete_all(raw);
            assert_eq!(owned.done.get().read(), u32::MAX);
            assert!(bindings::try_wait_for_completion(raw));
            assert_eq!(owned.done.get().read(), u32::MAX);
            // Exactly the quiescent counter update performed by C's inline
            // reinit_completion; the pinned queue is neither moved nor reset.
            owned.done.get().write(0);
            assert!(!bindings::try_wait_for_completion(raw));
            bindings::complete(raw);
            assert!(bindings::try_wait_for_completion(raw));
            assert_eq!(owned.done.get().read(), 0);
        }
        // No producer or queued waiter exists when the allocation is freed.
        Ok(())
    }

    // Use the existing upstream wrapper for concurrent tests. The exploratory
    // Layout deliberately remains !Send/!Sync and is never shared with workers.
    #[pin_data]
    struct Handoff {
        #[pin]
        ready: super::super::Completion,
        #[pin]
        event: super::super::Completion,
        #[pin]
        finished: super::super::Completion,
        value: crate::sync::atomic::Atomic<u32>,
    }

    impl Handoff {
        fn new() -> impl PinInit<Self> {
            pin_init!(Self {
                ready <- super::super::Completion::new(),
                event <- super::super::Completion::new(),
                finished <- super::super::Completion::new(),
                value: crate::sync::atomic::Atomic::new(0),
            })
        }
    }

    fn wait_bounded(completion: &super::super::Completion, milliseconds: u32) -> bool {
        // SAFETY: Only the KUnit task and an ordinary unbound workqueue worker
        // call this helper, with IRQs enabled and no held locks. The borrowed
        // Completion is initialized/pinned and its Arc owner lives until return.
        // C removes its stack waiter on every timeout/success exit. No pointer
        // escapes, and a nonzero finite timeout bounds scheduler waiting.
        unsafe {
            bindings::wait_for_completion_timeout(
                completion.as_raw(),
                crate::time::msecs_to_jiffies(milliseconds.into()),
            ) != 0
        }
    }

    #[test]
    fn worker_handoff_observes_published_value() -> Result {
        use crate::sync::{atomic::Relaxed, Arc};

        let state = Arc::pin_init(Handoff::new(), GFP_KERNEL)?;
        let worker = state.clone();
        crate::workqueue::system_unbound().try_spawn(GFP_KERNEL, move || {
            worker.ready.complete_all();
            // The producer may win the enqueue race. Both pre-signaled and
            // queued-wakeup outcomes must preserve the same publication rule.
            let value = if wait_bounded(&worker.event, 5000) {
                worker.value.load(Relaxed)
            } else {
                0
            };
            worker.value.store(value.wrapping_add(1), Relaxed);
            worker.finished.complete_all();
            // The closure retains its Arc through return, including if the
            // test timed out/dropped its own Arc. No borrowed stack state exists.
        })?;
        let ready = wait_bounded(&state.ready, 10000);
        state.value.store(0x1234, Relaxed);
        state.event.complete_all();
        let finished = wait_bounded(&state.finished, 10000);
        assert!(ready);
        assert!(finished);
        assert_eq!(state.value.load(Relaxed), 0x1235);
        Ok(())
    }

    #[test]
    fn timed_out_worker_unlinks_before_late_signal() -> Result {
        use crate::sync::{atomic::Relaxed, Arc};

        let state = Arc::pin_init(Handoff::new(), GFP_KERNEL)?;
        let worker = state.clone();
        crate::workqueue::system_unbound().try_spawn(GFP_KERNEL, move || {
            // No producer signals event until this bounded wait has returned.
            // Thus this case exercises actual positive-timeout queue enrollment,
            // unlike a handshake whose producer could signal before enrollment.
            let completed = wait_bounded(&worker.event, 20);
            worker.value.store(if completed { 2 } else { 1 }, Relaxed);
            worker.finished.complete_all();
        })?;
        assert!(wait_bounded(&state.finished, 10000));
        assert_eq!(state.value.load(Relaxed), 1);
        // SAFETY: The initialized completion remains pinned in our Arc. The
        // worker's wait has returned before it signals finished, so its stack
        // waiter is gone. These nonblocking calls retain no pointer. A lingering
        // callback epilogue owns a separate Arc and no longer accesses event.
        unsafe {
            bindings::complete(state.event.as_raw());
            assert!(bindings::try_wait_for_completion(state.event.as_raw()));
            assert!(!bindings::try_wait_for_completion(state.event.as_raw()));
        }
        Ok(())
    }
}
