// SPDX-License-Identifier: GPL-2.0
// Rust translation of complete() in kernel/sched/completion.c, Linux 6.18.58.

//! Opt-in implementation of the C `complete()` entry point.
//!
//! Completion storage, wait queues and scheduler wakeups retain their existing
//! C implementation. No allocation, initialization or layout change occurs here.

use core::{ffi::c_ulong, ptr::addr_of_mut};
use kernel::{
    bindings,
    sync::atomic::{Atomic, Relaxed},
    types::NotThreadSafe,
};

/// Owns one raw lock acquisition and the caller's saved interrupt state.
///
/// Only `complete` constructs this private, non-Send guard. The caller keeps the
/// lock's storage alive; the guard cannot escape that call or cross an await.
/// Restoring the saved flags (rather than enabling IRQs) preserves IRQ callers.
struct IrqRestore {
    lock: *mut bindings::raw_spinlock_t,
    flags: c_ulong,
    _task: NotThreadSafe,
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
    // SAFETY: The caller supplies valid, initialized and pinned completion
    // storage. Raw field projection neither reads it nor creates a reference.
    let wait = unsafe { addr_of_mut!((*completion).wait) };
    // SAFETY: `wait` is the in-bounds initialized queue within that storage.
    let lock = unsafe { addr_of_mut!((*wait).lock) };
    // SAFETY: The lock is initialized/live, and the caller is not its owner.
    // The primitive saves IRQ state and acquires the embedded raw spinlock.
    let flags = unsafe { bindings::raw_spin_lock_irqsave(lock) };
    let _restore = IrqRestore {
        lock,
        flags,
        _task: NotThreadSafe,
    };

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
    // C queue primitive removes/wakes its first waiter with wake_flags=0, as in
    // complete_with_flags. It preserves scheduler task-state ordering and does
    // not retain the queue pointer or release our lock. It does not sleep.
    unsafe { bindings::swake_up_locked(wait, 0) };
    // _restore unlocks before restoring the exact incoming IRQ flags.
}
