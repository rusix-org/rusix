// SPDX-License-Identifier: GPL-2.0
// Rust translation of completion signaling from Linux 6.18.58 completion.c.

//! Opt-in completion signaling and blocking wait entry points.
//!
//! C-visible completion storage, wait queues and scheduler primitives remain.
//! No allocation, initialization or layout change occurs here.

#[path = "completion_rust/wait.rs"]
mod wait;

use core::ptr::addr_of_mut;
use kernel::{
    bindings,
    ffi::{c_int, c_ulong},
    sync::atomic::{Atomic, Relaxed},
    types::NotThreadSafe,
};

// Private scheduler ABI from Linux 6.18.58 kernel/sched/sched.h:
// void swake_up_all_locked(struct swait_queue_head *q).
// swait.c restricts this primitive to completions. Keep the C declaration
// private and call its existing implementation without a public Rust API or
// extra shim. The generated queue type supplies the target-specific layout.
unsafe extern "C" {
    fn swake_up_all_locked(queue: *mut bindings::swait_queue_head);

    // Defined as const int = WF_CURRENT_CPU in completion.c. This keeps the
    // private scheduler macro authoritative without widening a public header.
    static rusix_completion_wf_current_cpu: c_int;
}

/// Owns one raw lock acquisition and the caller's saved interrupt state.
///
/// Only the completion entry points construct this private, non-Send guard.
/// The caller keeps the lock's storage alive; the guard cannot escape that call or cross an await.
/// Restoring the saved flags (rather than enabling IRQs) preserves IRQ callers.
struct IrqRestore {
    lock: *mut bindings::raw_spinlock_t,
    flags: c_ulong,
    _task: NotThreadSafe,
}

impl IrqRestore {
    /// Acquires an initialized raw lock without changing the caller's IRQ policy.
    ///
    /// # Safety
    ///
    /// `lock` must remain initialized, immovable and alive until this guard is
    /// dropped. The current context must not already own it. The guard must be
    /// dropped synchronously in this context, without unlocking by another path.
    unsafe fn acquire(lock: *mut bindings::raw_spinlock_t) -> Self {
        // SAFETY: The caller supplies live initialized storage and excludes
        // recursive acquisition. This primitive saves IRQ state before locking.
        let flags = unsafe { bindings::raw_spin_lock_irqsave(lock) };
        Self {
            lock,
            flags,
            _task: NotThreadSafe,
        }
    }
}

impl Drop for IrqRestore {
    fn drop(&mut self) {
        // SAFETY: Construction immediately follows acquisition of this exact
        // initialized raw lock. It has not been unlocked; no operation moves
        // execution to another task/CPU while the raw lock is held. `flags` is
        // the saved IRQ state from that acquisition. The C caller keeps the
        // containing completion alive through the final lock release. No access
        // to that storage occurs after unlock.
        unsafe { bindings::raw_spin_unlock_irqrestore(self.lock, self.flags) };
    }
}

/// Signals one waiter, or retains a counting token if there is no waiter.
///
/// # Safety
///
/// `completion` must point to initialized, immovable C completion storage which
/// remains alive through the final lock release. Concurrent operations must follow the existing
/// C completion contract: `done` updates and queue mutation hold `wait.lock`,
/// and initialization/reinitialization requires external quiescence. This call
/// must not recursively acquire the same raw lock. These are the C API's existing
/// requirements; no Rust reference to the containing C object is constructed.
// SAFETY: Kbuild selects this symbol only when the corresponding C definition
// is excluded. The pointer/void ABI matches include/linux/completion.h; the
// original C EXPORT_SYMBOL metadata is retained exactly once.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn complete(completion: *mut bindings::completion) {
    // SAFETY: The caller supplies the shared signaling helper's completion
    // lifetime and lock requirements. Zero is the C entry point's wake flag.
    unsafe { complete_with_flags(completion, 0) };
}

/// Signals one waiter with the scheduler's preference for the current CPU.
///
/// # Safety
///
/// The storage, synchronization and nonrecursive-lock requirements of [`complete`]
/// apply. CPU selection remains a scheduler preference, subject to its affinity
/// and placement rules; this operation adds no independent migration guarantee.
// SAFETY: The matching C definition is excluded by the same Kconfig selection.
// This matches completion.h's pointer/void ABI; the C entry point is not exported
// to modules, so no new EXPORT_SYMBOL metadata is introduced.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn complete_on_current_cpu(completion: *mut bindings::completion) {
    // SAFETY: This immutable C int is initialized from the private scheduler
    // macro at link time and is never written. Its lifetime is the kernel's.
    let wake_flags = unsafe { rusix_completion_wf_current_cpu };
    // SAFETY: The caller supplies the same completion lifetime and locking
    // requirements as complete(). The flag is the C scheduler's exact value.
    unsafe { complete_with_flags(completion, wake_flags) };
}

/// Shared translation of the C counting signal operation.
///
/// # Safety
///
/// The completion requirements of [`complete`] apply. `wake_flags` must be zero
/// or the private scheduler's `WF_CURRENT_CPU` value. Only the two entry points
/// above call this helper, with precisely those values.
unsafe fn complete_with_flags(completion: *mut bindings::completion, wake_flags: c_int) {
    // SAFETY: The caller supplies valid, initialized and pinned completion
    // storage. Raw field projection neither reads it nor creates a reference.
    let wait = unsafe { addr_of_mut!((*completion).wait) };
    // SAFETY: `wait` is the in-bounds initialized queue within that storage.
    let lock = unsafe { addr_of_mut!((*wait).lock) };
    // SAFETY: The lock is initialized/live, and the caller is not its owner.
    // The primitive saves IRQ state and acquires the embedded raw spinlock.
    let _restore = unsafe { IrqRestore::acquire(lock) };

    {
        // SAFETY: `done` is an aligned live C unsigned-int field, represented
        // by u32 on the selected x86_64 target. This atomic reference exists
        // only while wait.lock is held. C's plain writers take that same lock;
        // concurrent lockless C observations use READ_ONCE. Quiescent init/reset
        // cannot overlap this call. Thus no concurrent unmarked access races
        // with these LKMM atomic operations. No &mut or Rust payload reference
        // is created, and the reference is not retained across unlock.
        let done = unsafe { Atomic::<u32>::from_ptr(addr_of_mut!((*completion).done)) };
        let count = done.load(Relaxed);
        if count != u32::MAX {
            done.store(count.wrapping_add(1), Relaxed);
        }
    }

    // SAFETY: The same queue's raw lock is still held with IRQs disabled. The
    // C queue primitive removes/wakes its first waiter with the same wake flags
    // as the corresponding C entry point. It preserves task-state ordering and does
    // not retain the queue pointer or release our lock. It does not sleep.
    unsafe { bindings::swake_up_locked(wait, wake_flags) };
    // _restore unlocks before restoring the exact incoming IRQ flags.
}

/// Signals all current and future waiters until a quiescent reinitialization.
///
/// # Safety
///
/// The storage, synchronization and nonrecursive-lock requirements of [`complete`]
/// apply. The caller must also satisfy the C API's threaded-context requirement
/// on PREEMPT_RT. Reinitialization must wait for all prior waiters to finish;
/// observing the permanent done sentinel does not establish that quiescence.
// SAFETY: The matching C definition is excluded by Kbuild selection. This has
// the pointer/void ABI in completion.h and retains its original C export record.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn complete_all(completion: *mut bindings::completion) {
    // SAFETY: This assertion reads current execution context and takes no
    // pointers. It must precede lock acquisition, matching the C entry point.
    unsafe { bindings::lockdep_assert_RT_in_threaded_ctx() };

    // SAFETY: The caller provides initialized immovable completion storage,
    // live through final lock release. Projections create only raw pointers.
    let wait = unsafe { addr_of_mut!((*completion).wait) };
    // SAFETY: The lock is an initialized in-bounds field of that queue.
    let lock = unsafe { addr_of_mut!((*wait).lock) };
    // SAFETY: The caller excludes recursive locking and keeps storage alive.
    // This guard remains local and restores the exact incoming IRQ flags.
    let _restore = unsafe { IrqRestore::acquire(lock) };
    {
        // SAFETY: The initialized u32 field is properly aligned. The atomic
        // reference exists only while wait.lock excludes C's plain writers;
        // concurrent lockless observations use READ_ONCE. Init/reset cannot
        // overlap this operation. LKMM Atomic preserves marked shared accesses
        // without exposing an exclusive reference or retaining one past unlock.
        let done = unsafe { Atomic::<u32>::from_ptr(addr_of_mut!((*completion).done)) };
        done.store(u32::MAX, Relaxed);
    }
    // SAFETY: The queue's raw lock is held with IRQs disabled. The existing
    // completion-specific wake-all primitive removes and wakes every queued
    // waiter without dropping this lock or sleeping. It preserves scheduler
    // ordering, retains no queue pointer, and leaves the sentinel unchanged.
    unsafe { swake_up_all_locked(wait) };
    // Waiters may release the last owner after unlock. Do not access completion
    // storage after _restore releases the lock; its saved fields are stack-local.
}
