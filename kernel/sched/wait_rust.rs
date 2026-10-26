// SPDX-License-Identifier: GPL-2.0-only
// Rust translation of Linux 6.18.58 generic wait wake policy.

//! Callback traversal and exclusive wake accounting over C-visible wait queues.
//!
//! Initialization, enrollment, callbacks, scheduler wakes and spinlock primitives
//! remain C. The flag snapshot retains the baseline C mixed-access boundary;
//! this module does not expose a safe Rust API for generic wait entry ownership.

use core::ptr::{addr_of, addr_of_mut, null_mut};
use kernel::{
    bindings,
    ffi::{c_int, c_uint, c_ulong, c_void},
    types::NotThreadSafe,
};

unsafe extern "C" {
    // Immutable definitions in wait.c retain the private sched.h constants.
    static rusix_wait_wf_sync: c_int;
    static rusix_wait_wf_current_cpu: c_int;
}

struct IrqRestore {
    lock: *mut bindings::spinlock_t,
    flags: c_ulong,
    _task: NotThreadSafe,
}
impl IrqRestore {
    /// # Safety
    /// Live initialized nonrecursively acquired spinlock; enclosing queue must
    /// survive until this guard drops synchronously in the current context.
    unsafe fn acquire(lock: *mut bindings::spinlock_t) -> Self {
        // SAFETY: caller supplies live lock and correct acquisition context.
        let flags = unsafe { bindings::wait_spin_lock_irqsave(lock) };
        Self {
            lock,
            flags,
            _task: NotThreadSafe,
        }
    }
}
impl Drop for IrqRestore {
    fn drop(&mut self) {
        // SAFETY: this guard owns this acquisition; callbacks cannot release it.
        unsafe { bindings::wait_spin_unlock_irqrestore(self.lock, self.flags) };
    }
}

/// Runs callbacks in baseline list order and returns the remaining wake budget.
///
/// # Safety
/// Queue is initialized, pinned and live; caller holds its spinlock in a context
/// allowed by its callbacks. Each reachable entry has a nonnull callback and
/// initialized links/flags. Callback code and its private state remain live when
/// invoked. Callbacks must return with the incoming lock held, preserve traversal
/// of the cached successor when continuation occurs, and obey existing wake
/// context rules. They may unlink and free the current entry before returning. No
/// Rust reference to queue/entry is created. Key is opaque and forwarded unchanged.
unsafe fn wake_common(
    queue: *mut bindings::wait_queue_head,
    mode: c_uint,
    mut remaining: c_int,
    wake_flags: c_int,
    key: *mut c_void,
) -> c_int {
    // SAFETY: initialized queue protected by caller-held spinlock.
    unsafe { bindings::spin_assert_is_held(addr_of_mut!((*queue).lock)) };
    // SAFETY: initialized, live queue; projection does not create a reference.
    let head = unsafe { addr_of_mut!((*queue).head) };
    // SAFETY: incoming lock excludes list mutations outside callbacks.
    let mut node = unsafe { addr_of!((*head).next).read() };
    while node != head {
        // SAFETY: a non-head member is embedded in a live wait_queue_entry.
        let current =
            unsafe { kernel::container_of!(node, bindings::wait_queue_entry, entry) }.cast_mut();
        // SAFETY: cache successor before callback, which can retire current.
        let next = unsafe { addr_of!((*node).next).read() };
        // SAFETY: preserves baseline flag load in C, including existing C-side
        // mixed-access conventions. This is a temporary unaudited flags boundary.
        let flags = unsafe { bindings::wait_entry_flags(current) };
        // SAFETY: func is initialized/non-null and stable while enrolled under
        // the held lock. Copy the function pointer before current can be freed.
        let callback = unsafe { addr_of!((*current).func).read().unwrap_unchecked() };
        // SAFETY: callback contract above; mode/flags/key passed without changes.
        // No access to current, its task/private or node follows this invocation.
        let ret = unsafe { callback(current, mode, wake_flags, key) };
        if ret < 0 {
            break;
        }
        if ret != 0 && flags & bindings::WQ_FLAG_EXCLUSIVE != 0 {
            // Kernel C uses -fno-strict-overflow; zero means unlimited, and
            // becomes negative after successful exclusive callbacks, not zero.
            remaining = remaining.wrapping_sub(1);
            if remaining == 0 {
                break;
            }
        }
        node = next;
    }
    remaining
}

/// # Safety
/// Same callback/storage contract as wake_common, but this acquires the lock.
unsafe fn wake_common_lock(
    queue: *mut bindings::wait_queue_head,
    mode: c_uint,
    nr: c_int,
    flags: c_int,
    key: *mut c_void,
) -> c_int {
    // SAFETY: caller supplies live initialized queue and nonrecursive lock use.
    let _guard = unsafe { IrqRestore::acquire(addr_of_mut!((*queue).lock)) };
    // SAFETY: guard holds queue lock through traversal and all callback returns.
    let remaining = unsafe { wake_common(queue, mode, nr, flags, key) };
    nr.wrapping_sub(remaining)
}

/// # Safety
/// wake_common_lock's queue, callback and context contract applies.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its EXPORT_SYMBOL. Generated types preserve the C pointer/integer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn __wake_up(
    q: *mut bindings::wait_queue_head,
    mode: c_uint,
    nr: c_int,
    key: *mut c_void,
) -> c_int {
    // SAFETY: caller provides wake_common_lock's contract.
    unsafe { wake_common_lock(q, mode, nr, 0, key) }
}

/// # Safety
/// wake_common_lock's contract applies; queue is nonnull.
// SAFETY: the same Kconfig selection excludes the matching C body. Generated
// types preserve its C ABI; the existing function has no module export.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn __wake_up_on_current_cpu(
    q: *mut bindings::wait_queue_head,
    mode: c_uint,
    key: *mut c_void,
) {
    // SAFETY: immutable C flag constant and caller-provided queue contract.
    unsafe {
        wake_common_lock(q, mode, 1, rusix_wait_wf_current_cpu, key);
    }
}

/// # Safety
/// wake_common's caller-held lock and callback contract applies.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its GPL export. Generated types preserve the C pointer/integer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn __wake_up_locked(
    q: *mut bindings::wait_queue_head,
    mode: c_uint,
    nr: c_int,
) {
    // SAFETY: caller supplies held lock and callback requirements.
    unsafe {
        wake_common(q, mode, nr, 0, null_mut());
    }
}

/// # Safety
/// wake_common's caller-held lock and callback contract applies.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its GPL export. Generated types preserve the C pointer/integer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn __wake_up_locked_key(
    q: *mut bindings::wait_queue_head,
    mode: c_uint,
    key: *mut c_void,
) {
    // SAFETY: caller supplies held lock and callback requirements.
    unsafe {
        wake_common(q, mode, 1, 0, key);
    }
}

/// # Safety
/// Null queue is permitted; otherwise wake_common_lock's contract applies.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its GPL export. Generated types preserve the C pointer/integer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn __wake_up_sync_key(
    q: *mut bindings::wait_queue_head,
    mode: c_uint,
    key: *mut c_void,
) {
    if q.is_null() {
        return;
    }
    // SAFETY: immutable flag constant; checked queue and caller contract.
    unsafe {
        wake_common_lock(q, mode, 1, rusix_wait_wf_sync, key);
    }
}

/// # Safety
/// wake_common's caller-held lock and callback contract applies; q is nonnull.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its GPL export. Generated types preserve the C pointer/integer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn __wake_up_locked_sync_key(
    q: *mut bindings::wait_queue_head,
    mode: c_uint,
    key: *mut c_void,
) {
    // SAFETY: immutable flag constant and caller supplies held-lock contract.
    unsafe {
        wake_common(q, mode, 1, rusix_wait_wf_sync, key);
    }
}

/// # Safety
/// Null queue is permitted; otherwise wake_common_lock's contract applies.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its GPL export. Generated types preserve the C pointer/integer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn __wake_up_sync(q: *mut bindings::wait_queue_head, mode: c_uint) {
    // SAFETY: inherits null handling and caller requirements from sync_key.
    unsafe { __wake_up_sync_key(q, mode, null_mut()) };
}
