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
        assert_eq!(unsafe { owned.done.get().read() }, 0);
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        unsafe { bindings::complete(raw) };
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert_eq!(unsafe { owned.done.get().read() }, 1);
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { bindings::try_wait_for_completion(raw) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert_eq!(unsafe { owned.done.get().read() }, 0);
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { !bindings::try_wait_for_completion(raw) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        unsafe { bindings::complete_all(raw) };
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert_eq!(unsafe { owned.done.get().read() }, u32::MAX);
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { bindings::try_wait_for_completion(raw) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert_eq!(unsafe { owned.done.get().read() }, u32::MAX);
        // SAFETY: Exactly the quiescent counter update performed by C's inline
        // reinit_completion; the pinned queue is neither moved nor reset.
        // The initialized storage remains exclusively accessed by this task.
        unsafe { owned.done.get().write(0) };
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { !bindings::try_wait_for_completion(raw) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        unsafe { bindings::complete(raw) };
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { bindings::try_wait_for_completion(raw) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert_eq!(unsafe { owned.done.get().read() }, 0);
        // No producer or queued waiter exists when the allocation is freed.
        Ok(())
    }

    #[test]
    fn current_cpu_signal_counts_and_saturates() -> Result {
        let owned = KBox::pin_init(Layout::new(), GFP_KERNEL)?;
        let raw = (&*owned as *const Layout)
            .cast_mut()
            .cast::<bindings::completion>();
        // SAFETY: The initialized completion has pinned, interior-mutable
        // storage. Only this task accesses it, and these operations retain no
        // pointer. No producer, waiter or callback can race counter inspection.
        unsafe {
            bindings::complete_on_current_cpu(raw);
            bindings::complete_on_current_cpu(raw);
        }
        // SAFETY: The same exclusive-access and initialized-storage invariants hold.
        let count = unsafe { owned.done.get().read() };
        assert_eq!(count, 2);
        // SAFETY: These nonblocking calls borrow the same live pinned storage.
        let first = unsafe { bindings::try_wait_for_completion(raw) };
        // SAFETY: The same storage/access conditions still hold.
        let second = unsafe { bindings::try_wait_for_completion(raw) };
        // SAFETY: The same storage/access conditions still hold.
        let third = unsafe { bindings::try_wait_for_completion(raw) };
        assert!(first);
        assert!(second);
        assert!(!third);
        // SAFETY: The queue is empty and no other task can access this object.
        // Seed the boundary without billions of calls; this quiescent write
        // neither moves nor reinitializes the pinned queue.
        unsafe { owned.done.get().write(u32::MAX - 1) };
        // SAFETY: The completion remains initialized, pinned and exclusively
        // accessed. Neither call retains its pointer or releases its storage.
        unsafe {
            bindings::complete_on_current_cpu(raw);
            bindings::complete_on_current_cpu(raw);
        }
        // SAFETY: Quiescent observation of this task's own initialized counter.
        let saturated = unsafe { owned.done.get().read() };
        assert_eq!(saturated, u32::MAX);
        // SAFETY: Live initialized pinned storage; the call retains no pointer.
        let consumed = unsafe { bindings::try_wait_for_completion(raw) };
        assert!(consumed);
        // SAFETY: No concurrent accesses or retained pointers exist.
        let after_wait = unsafe { owned.done.get().read() };
        assert_eq!(after_wait, u32::MAX);
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
        // SAFETY: The initialized event is pinned in state, whose Arc remains
        // live through both worker and producer access. complete retains no pointer.
        unsafe { bindings::complete(state.event.as_raw()) };
        let finished = wait_bounded(&state.finished, 10000);
        assert!(ready);
        assert!(finished);
        assert_eq!(state.value.load(Relaxed), 0x1235);
        Ok(())
    }

    #[test]
    fn current_cpu_signal_wakes_enrolled_worker() -> Result {
        use crate::sync::{atomic::Relaxed, Arc};

        let state = Arc::pin_init(Handoff::new(), GFP_KERNEL)?;
        let started = crate::time::Instant::<crate::time::Monotonic>::now();
        let worker = state.clone();
        crate::workqueue::system_unbound().try_spawn(GFP_KERNEL, move || {
            let value = if wait_bounded(&worker.event, 10000) {
                worker.value.load(Relaxed)
            } else {
                0
            };
            worker.value.store(value.wrapping_add(1), Relaxed);
            worker.finished.complete_all();
            // The callback retains its own Arc through return, even if the
            // observer times out. No KUnit context or test stack is borrowed.
        })?;
        let mut enrolled = false;
        for _ in 0..100 {
            // SAFETY: Our Arc pins the initialized event through this call.
            // The read-only helper serializes queue inspection with waiters
            // using the event's raw lock, and never retains a pointer.
            let count = unsafe { bindings::completion_waiter_count(state.event.as_raw()) };
            if count == 1 {
                enrolled = true;
                break;
            }
            crate::time::delay::fsleep(crate::time::Delta::from_millis(10));
        }
        // Publish after observing actual enrollment. Signal even when enrollment
        // failed so any delayed worker can leave without waiting for its timeout.
        state.value.store(0x1234, Relaxed);
        // SAFETY: Initialized event storage stays pinned and alive in the
        // producer/worker Arcs; this IRQ-safe operation retains no pointer.
        unsafe { bindings::complete_on_current_cpu(state.event.as_raw()) };
        // Expire well before the worker's timeout: noticing the token only when
        // that timeout expires cannot substitute for a missing scheduler wakeup.
        let finished = wait_bounded(&state.finished, 1000);
        // Bound elapsed time from before any worker could start its ten-second
        // wait. Iteration counts and short observer waits alone would allow a
        // delayed producer to mistake timeout-driven progress for a wakeup.
        let elapsed = started.elapsed().as_millis();
        assert!(elapsed < 5000);
        assert!(enrolled);
        assert!(finished);
        assert_eq!(state.value.load(Relaxed), 0x1235);
        // SAFETY: Our Arc retains initialized pinned storage. The worker no
        // longer accesses event after signaling finished; this call is nonblocking.
        let leftover = unsafe { bindings::try_wait_for_completion(state.event.as_raw()) };
        assert!(!leftover);
        // WF_CURRENT_CPU is a scheduler hint, not a guaranteed CPU placement;
        // this case verifies queued wakeup, publication and single consumption.
        Ok(())
    }

    #[test]
    fn two_workers_consume_exactly_two_tokens() -> Result {
        use crate::sync::{atomic::Relaxed, Arc};

        // Each worker has independently owned result/finished storage. Only the
        // event is shared; no closure borrows this task's stack or KUnit context.
        let event = Arc::pin_init(super::super::Completion::new(), GFP_KERNEL)?;
        let first = Arc::pin_init(Handoff::new(), GFP_KERNEL)?;
        let second = Arc::pin_init(Handoff::new(), GFP_KERNEL)?;
        for state in [&first, &second] {
            let worker = state.clone();
            let worker_event = event.clone();
            crate::workqueue::system_unbound().try_spawn(GFP_KERNEL, move || {
                worker.ready.complete_all();
                let consumed = wait_bounded(&worker_event, 5000);
                worker.value.store(if consumed { 1 } else { 2 }, Relaxed);
                worker.finished.complete_all();
                // On timeout or partial spawn failure these Arcs still own all
                // accessed storage until the bounded callback has returned.
            })?;
        }
        let ready_first = wait_bounded(&first.ready, 10000);
        let ready_second = wait_bounded(&second.ready, 10000);
        // SAFETY: The initialized event stays pinned in an Arc held by this
        // task and each worker. These calls retain no pointer. Enrollment may
        // race the signals; both queued and pre-signaled paths must conserve
        // two tokens, with one consumed by each worker. No FIFO order is claimed.
        unsafe {
            bindings::complete(event.as_raw());
            bindings::complete(event.as_raw());
        }
        let finished_first = wait_bounded(&first.finished, 10000);
        let finished_second = wait_bounded(&second.finished, 10000);
        assert!(ready_first);
        assert!(ready_second);
        assert!(finished_first);
        assert!(finished_second);
        assert_eq!(first.value.load(Relaxed), 1);
        assert_eq!(second.value.load(Relaxed), 1);
        // SAFETY: The Arc pins initialized state; this nonblocking operation
        // retains no pointer. Workers no longer access event after finished.
        assert!(!unsafe { bindings::try_wait_for_completion(event.as_raw()) });
        Ok(())
    }

    #[test]
    fn competing_try_waiters_consume_one_token() -> Result {
        use crate::sync::{atomic::Relaxed, Arc};

        let token = Arc::pin_init(super::super::Completion::new(), GFP_KERNEL)?;
        let start = Arc::pin_init(super::super::Completion::new(), GFP_KERNEL)?;
        let first = Arc::pin_init(Handoff::new(), GFP_KERNEL)?;
        let second = Arc::pin_init(Handoff::new(), GFP_KERNEL)?;
        let started = crate::time::Instant::<crate::time::Monotonic>::now();
        for state in [&first, &second] {
            let worker = state.clone();
            let worker_token = token.clone();
            let worker_start = start.clone();
            let spawned = crate::workqueue::system_unbound().try_spawn(GFP_KERNEL, move || {
                let result = if wait_bounded(&worker_start, 10000) {
                    // SAFETY: The callback's Arc keeps initialized token storage
                    // pinned and alive. Only these two consumers race this
                    // nonblocking call; no reset occurs and no pointer is retained.
                    u32::from(unsafe { bindings::try_wait_for_completion(worker_token.as_raw()) })
                } else {
                    2 // A gate timeout must never count as a legitimate loss.
                };
                worker.value.store(result, Relaxed);
                worker.finished.complete_all();
                // Each callback retains its own Arcs through return. Observer
                // timeout or partial spawn failure cannot invalidate its storage.
            });
            if let Err(error) = spawned {
                // Release any already-created worker before returning. Its own
                // Arcs protect any callback that continues after this test exits.
                start.complete_all();
                return Err(error);
            }
        }
        let mut enrolled = false;
        for _ in 0..100 {
            // SAFETY: Our Arc pins the initialized gate. The read-only helper
            // locks its queue and retains no pointer or waiter reference.
            if unsafe { bindings::completion_waiter_count(start.as_raw()) } == 2 {
                enrolled = true;
                break;
            }
            crate::time::delay::fsleep(crate::time::Delta::from_millis(10));
        }
        // SAFETY: The Arc pins initialized token storage; there is no reset.
        // Exactly one counting token is supplied before releasing the consumers.
        unsafe { bindings::complete(token.as_raw()) };
        // Always release the gate before assertions, even on enrollment failure.
        // Both workers become eligible to consume; simultaneous execution or
        // scheduler order is not required or claimed by this conservation test.
        start.complete_all();
        let first_finished = wait_bounded(&first.finished, 1000);
        let second_finished = wait_bounded(&second.finished, 1000);
        let elapsed = started.elapsed().as_millis();
        let first_result = first.value.load(Relaxed);
        let second_result = second.value.load(Relaxed);
        // SAFETY: The controller's Arc keeps initialized storage alive even if
        // a worker is delayed. These nonblocking observations use the ordinary
        // completion synchronization contract and never reinitialize storage.
        let leftover = unsafe { bindings::try_wait_for_completion(token.as_raw()) };
        // SAFETY: The same initialized, pinned storage/access conditions hold.
        let still_done = unsafe { bindings::completion_done(token.as_raw()) };
        assert!(enrolled);
        assert!(first_finished);
        assert!(second_finished);
        // Gate expiry after ten seconds cannot masquerade as a prompt wakeup.
        assert!(elapsed < 5000);
        assert!(first_result <= 1);
        assert!(second_result <= 1);
        assert_eq!(first_result + second_result, 1);
        assert!(!leftover);
        assert!(!still_done);
        Ok(())
    }

    #[test]
    fn broadcast_serves_two_workers_and_late_waiters() -> Result {
        use crate::sync::{atomic::Relaxed, Arc};

        let event = Arc::pin_init(super::super::Completion::new(), GFP_KERNEL)?;
        let first = Arc::pin_init(Handoff::new(), GFP_KERNEL)?;
        let second = Arc::pin_init(Handoff::new(), GFP_KERNEL)?;
        let started = crate::time::Instant::<crate::time::Monotonic>::now();
        for state in [&first, &second] {
            let worker = state.clone();
            let worker_event = event.clone();
            crate::workqueue::system_unbound().try_spawn(GFP_KERNEL, move || {
                worker.ready.complete_all();
                let completed = wait_bounded(&worker_event, 10000);
                worker.value.store(if completed { 1 } else { 2 }, Relaxed);
                worker.finished.complete_all();
                // Independent Arc ownership keeps all state alive through return,
                // including partial spawn failure or timeout in the KUnit task.
                // No worker borrows test-stack storage or performs assertions.
            })?;
        }
        // Observe actual enrollment, not just a worker's pre-wait handshake.
        // The helper holds the same IRQ-safe raw lock as completion operations,
        // reads only the queue, and caps traversal at three entries. No assertion
        // or sleep occurs while it holds the lock.
        let mut enrolled = false;
        for _ in 0..100 {
            // SAFETY: Our Arc pins initialized storage; the helper borrows it
            // only during this call and serializes traversal against all waiters.
            let count = unsafe { bindings::completion_waiter_count(event.as_raw()) };
            if count == 2 {
                enrolled = true;
                break;
            }
            crate::time::delay::fsleep(crate::time::Delta::from_millis(10));
        }
        // Signal even if enrollment failed, allowing any extant worker to leave.
        // One broadcast must promptly release both queued workers. Observers
        // expire well before the workers' ten-second timeout, so noticing MAX
        // only at their timeout cannot substitute for a missing wakeup.
        event.complete_all();
        let finished_first = wait_bounded(&first.finished, 1000);
        let finished_second = wait_bounded(&second.finished, 1000);
        // Bound elapsed time from before any worker could start its ten-second
        // wait. Iteration counts and short observer waits alone would allow a
        // delayed producer to mistake timeout-driven progress for a wakeup.
        let elapsed = started.elapsed().as_millis();
        assert!(elapsed < 5000);
        assert!(enrolled);
        assert!(finished_first);
        assert!(finished_second);
        assert_eq!(first.value.load(Relaxed), 1);
        assert_eq!(second.value.load(Relaxed), 1);
        // SAFETY: This Arc pins initialized completion storage. The completed
        // workers no longer access event; these nonblocking calls retain no
        // pointer. Neither late successful wait may consume the broadcast state.
        let late_first = unsafe { bindings::try_wait_for_completion(event.as_raw()) };
        // SAFETY: The same pinned allocation and non-retaining call invariant hold.
        let late_second = unsafe { bindings::try_wait_for_completion(event.as_raw()) };
        assert!(late_first);
        assert!(late_second);
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
        unsafe { bindings::complete(state.event.as_raw()) };
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { bindings::try_wait_for_completion(state.event.as_raw()) });
        // SAFETY: The initialized pinned storage and access conditions above still hold.
        assert!(unsafe { !bindings::try_wait_for_completion(state.event.as_raw()) });
        Ok(())
    }
}
