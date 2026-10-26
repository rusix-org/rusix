// SPDX-License-Identifier: GPL-2.0-only
// Rust translation of Linux 6.18.58 generic wait lifecycle and wake policy.

//! Initialization, enrollment, prepare/finish and wake policy over C-visible queues.
//!
//! Entry initialization, locked wait iterations, scheduler wakes and spinlocks
//! remain C. WOKEN ordering primitives also retain their exact C operations.
//! Flag updates/snapshots retain the baseline C mixed-access boundary;
//! this module does not expose a safe Rust API for generic wait entry ownership.

use core::ptr::{addr_of, addr_of_mut, null_mut};
use kernel::{
    bindings,
    ffi::{c_char, c_int, c_long, c_uint, c_ulong, c_void},
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
        let current = unsafe { kernel::container_of!(node, bindings::wait_queue_entry, entry) };
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

/// Inserts after the contiguous priority prefix, before any ordinary waiter.
/// # Safety
/// Queue lock is held. Existing membership/flags obey the C wait protocols.
/// Entry is live, initialized except its links may be uninitialized, and not
/// currently enrolled. It remains pinned/live through removal.
unsafe fn add_after_priority(
    q: *mut bindings::wait_queue_head,
    entry: *mut bindings::wait_queue_entry,
) {
    // SAFETY: initialized queue under its held lock.
    let head = unsafe { addr_of_mut!((*q).head) };
    let mut insertion = head;
    // SAFETY: list links stable while lock held; sentinel is not an entry.
    let mut node = unsafe { addr_of!((*head).next).read() };
    while node != head {
        // SAFETY: non-sentinel node belongs to a live wait entry.
        let current = unsafe { kernel::container_of!(node, bindings::wait_queue_entry, entry) };
        // SAFETY: preserve C flag observation; no Rust field reference/read.
        if unsafe { bindings::wait_entry_flags(current) } & bindings::WQ_FLAG_PRIORITY == 0 {
            break;
        }
        insertion = node;
        // SAFETY: structural links remain protected by the queue lock.
        node = unsafe { addr_of!((*node).next).read() };
    }
    // SAFETY: entry is detached; insertion belongs to this locked valid list.
    unsafe { bindings::wait_list_add(addr_of_mut!((*entry).entry), insertion) };
}

/// # Safety
/// Queue initialized/live; caller may acquire its spinlock. Entry not enrolled,
/// flags/func/private initialized; pin/lifetime and C mixed-flags protocol apply.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its export. Generated types preserve the C pointer/integer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn add_wait_queue(
    q: *mut bindings::wait_queue_head,
    entry: *mut bindings::wait_queue_entry,
) {
    // SAFETY: caller permits the original pre-lock C flag update. Do not claim
    // queue.lock protects it; it has not been acquired yet.
    unsafe { bindings::wait_entry_update_flags(entry, bindings::WQ_FLAG_EXCLUSIVE, 0) };
    // SAFETY: initialized queue and valid nonrecursive acquisition context.
    let _guard = unsafe { IrqRestore::acquire(addr_of_mut!((*q).lock)) };
    // SAFETY: guard protects list; caller supplies detached live entry.
    unsafe { add_after_priority(q, entry) };
}

/// # Safety
/// Same storage, nonmembership and context requirements as add_wait_queue.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its export. Generated types preserve the C pointer/integer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn add_wait_queue_exclusive(
    q: *mut bindings::wait_queue_head,
    entry: *mut bindings::wait_queue_entry,
) {
    // SAFETY: original C pre-lock update, with caller's C flags protocol.
    unsafe { bindings::wait_entry_update_flags(entry, 0, bindings::WQ_FLAG_EXCLUSIVE) };
    // SAFETY: initialized queue and valid nonrecursive acquisition context.
    let _guard = unsafe { IrqRestore::acquire(addr_of_mut!((*q).lock)) };
    // SAFETY: append detached entry to locked queue; adapter preserves marked
    // link stores/debug checks. Its swait name does not change list_head ABI.
    unsafe { bindings::swait_list_add_tail(addr_of_mut!((*entry).entry), addr_of_mut!((*q).head)) };
}

/// # Safety
/// Same storage, nonmembership and context requirements as add_wait_queue.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its GPL export. Generated types preserve the C pointer/integer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn add_wait_queue_priority(
    q: *mut bindings::wait_queue_head,
    entry: *mut bindings::wait_queue_entry,
) {
    // SAFETY: original pre-lock flag update; EXCLUSIVE remains unchanged.
    unsafe { bindings::wait_entry_update_flags(entry, 0, bindings::WQ_FLAG_PRIORITY) };
    // SAFETY: initialized queue and valid nonrecursive acquisition context.
    let _guard = unsafe { IrqRestore::acquire(addr_of_mut!((*q).lock)) };
    // SAFETY: guard protects list; caller supplies detached live entry.
    unsafe { add_after_priority(q, entry) };
}

/// # Safety
/// Same storage, nonmembership and context requirements as add_wait_queue.
/// Failure leaves PRIORITY|EXCLUSIVE set; entry links remain untouched.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its GPL export. Generated types preserve the C pointer/integer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn add_wait_queue_priority_exclusive(
    q: *mut bindings::wait_queue_head,
    entry: *mut bindings::wait_queue_entry,
) -> c_int {
    // SAFETY: original pre-lock C flag update, even on subsequent rejection.
    unsafe {
        bindings::wait_entry_update_flags(
            entry,
            0,
            bindings::WQ_FLAG_EXCLUSIVE | bindings::WQ_FLAG_PRIORITY,
        )
    };
    // SAFETY: initialized queue and valid nonrecursive acquisition context.
    let _guard = unsafe { IrqRestore::acquire(addr_of_mut!((*q).lock)) };
    // SAFETY: stable initialized queue under lock.
    let head = unsafe { addr_of_mut!((*q).head) };
    // SAFETY: preserve list_empty's marked read via existing list adapter.
    if unsafe { bindings::swait_list_empty(head) } == 0 {
        // SAFETY: nonempty locked list has a real first entry.
        let node = unsafe { addr_of!((*head).next).read() };
        // SAFETY: node is not the sentinel and is embedded in a live wait entry.
        let first = unsafe { kernel::container_of!(node, bindings::wait_queue_entry, entry) };
        // SAFETY: baseline C flag load on a live entry; no Rust flag ownership.
        if unsafe { bindings::wait_entry_flags(first) } & bindings::WQ_FLAG_PRIORITY != 0 {
            return -(bindings::EBUSY as c_int);
        }
    }
    // SAFETY: no leading priority waiter; insert at head under lock.
    unsafe { bindings::wait_list_add(addr_of_mut!((*entry).entry), head) };
    0
}

/// # Safety
/// Queue/entry live, queue lock may be acquired; entry is linked on this queue
/// or already self-linked under its removal protocol. Poisoned links are invalid.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its export. Generated types preserve the C pointer/integer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn remove_wait_queue(
    q: *mut bindings::wait_queue_head,
    entry: *mut bindings::wait_queue_entry,
) {
    // SAFETY: caller retains live queue and supplies acquisition context.
    let _guard = unsafe { IrqRestore::acquire(addr_of_mut!((*q).lock)) };
    // SAFETY: valid links protected by guard. Preserve list_del poisoning,
    // not list_del_init; caller owns entry lifetime through this operation.
    unsafe { bindings::wait_list_del(addr_of_mut!((*entry).entry)) };
}

/// # Safety
/// Queue is aligned writable, exclusively accessible storage at final address;
/// no live waiter/held lock/observer from previous initialization remains.
/// Publish only after return. Under LOCKDEP, name/key obey C class lifetimes
/// and registration rules (which can outlive this queue); otherwise unused.
// SAFETY: matching C body is excluded and export retained. Opaque key pointer avoids
// exposing configuration-empty C lock_class_key through the Rust extern ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn __init_waitqueue_head(
    q: *mut bindings::wait_queue_head,
    name: *const c_char,
    key: *mut c_void,
) {
    // SAFETY: exclusive storage; exact C spinlock macro initializes lock first.
    unsafe { bindings::wait_spin_init(q) };
    // SAFETY: initialized lock map; caller-provided original name/key contract.
    unsafe { bindings::wait_lock_class(q, name, key.cast()) };
    // SAFETY: raw projection/writes initialize both links without referencing
    // uninitialized data. No observer exists until external publication.
    unsafe {
        let head = addr_of_mut!((*q).head);
        addr_of_mut!((*head).next).write(head);
        addr_of_mut!((*head).prev).write(head);
    }
}

/// # Safety
/// Caller is the waiting task. Queue is initialized/pinned/live, lock may be
/// acquired; entry has initialized flags/private/func and self-links or belongs
/// to this queue. Caller retains it until removal and finish. Other contexts may
/// remove but never concurrently re-enroll it. Existing C flags protocol applies.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its export. Generated types preserve its C pointer/integer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn prepare_to_wait(
    q: *mut bindings::wait_queue_head,
    entry: *mut bindings::wait_queue_entry,
    state: c_int,
) {
    // SAFETY: preserve caller-permitted prelock C flags update, not Rust RMW.
    unsafe { bindings::wait_entry_update_flags(entry, bindings::WQ_FLAG_EXCLUSIVE, 0) };
    // SAFETY: caller provides initialized queue/nonrecursive acquisition context.
    let _guard = unsafe { IrqRestore::acquire(addr_of_mut!((*q).lock)) };
    // SAFETY: entry links initialized; list test stable under held queue lock.
    if unsafe { bindings::swait_list_empty(addr_of!((*entry).entry)) } != 0 {
        // SAFETY: self-linked entry is detached; guard holds its queue lock.
        unsafe { add_after_priority(q, entry) };
    }
    // SAFETY: state is the original C int bit pattern. Full barrier must follow
    // enrollment and precede returning to the waiter's condition recheck.
    unsafe { bindings::swait_set_current_state(state as c_uint) };
}

/// # Safety
/// Same current-waiter, storage and synchronization contract as prepare_to_wait.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its export. Rust bool matches the C _Bool return ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn prepare_to_wait_exclusive(
    q: *mut bindings::wait_queue_head,
    entry: *mut bindings::wait_queue_entry,
    state: c_int,
) -> bool {
    // SAFETY: original C flags update occurs before queue lock acquisition.
    unsafe { bindings::wait_entry_update_flags(entry, 0, bindings::WQ_FLAG_EXCLUSIVE) };
    // SAFETY: caller provides live queue and valid nonrecursive context.
    let _guard = unsafe { IrqRestore::acquire(addr_of_mut!((*q).lock)) };
    let mut was_empty = false;
    // SAFETY: initialized entry links stable under the guard.
    if unsafe { bindings::swait_list_empty(addr_of!((*entry).entry)) } != 0 {
        // SAFETY: initialized queue links stable under the guard.
        was_empty = unsafe { bindings::swait_list_empty(addr_of!((*q).head)) } != 0;
        // SAFETY: detached entry and initialized list under its lock; preserve
        // debug checks and marked writes. This is tail, not priority insertion.
        unsafe {
            bindings::swait_list_add_tail(addr_of_mut!((*entry).entry), addr_of_mut!((*q).head))
        };
    }
    // SAFETY: full condition-publication barrier for current waiting task.
    unsafe { bindings::swait_set_current_state(state as c_uint) };
    was_empty
}

/// # Safety
/// Same current-waiter/storage contract as prepare_to_wait; current's signals
/// are valid to inspect. On signal failure the enclosing wait macro must recheck
/// condition and restore task state according to its existing lifecycle rules.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its export. c_long preserves the target C long return ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn prepare_to_wait_event(
    q: *mut bindings::wait_queue_head,
    entry: *mut bindings::wait_queue_entry,
    state: c_int,
) -> c_long {
    // SAFETY: caller provides live queue and valid nonrecursive context.
    let _guard = unsafe { IrqRestore::acquire(addr_of_mut!((*q).lock)) };
    // SAFETY: current is live; C helper preserves signal-state bit interpretation.
    if unsafe { bindings::signal_pending_state(state as c_uint, bindings::get_current()) } != 0 {
        // SAFETY: entry links initialized, either queued or self-linked; lock
        // protects unlink. Unconditional deletion matches signal-first C path.
        unsafe { bindings::swait_list_del_init(addr_of_mut!((*entry).entry)) };
        return -(bindings::ERESTARTSYS as c_long);
    }
    // SAFETY: initialized entry links stable under lock.
    if unsafe { bindings::swait_list_empty(addr_of!((*entry).entry)) } != 0 {
        // SAFETY: baseline C flag load; no claim lock owns all flag accesses.
        if unsafe { bindings::wait_entry_flags(entry) } & bindings::WQ_FLAG_EXCLUSIVE != 0 {
            // SAFETY: entry detached and queue protected; original tail policy.
            unsafe {
                bindings::swait_list_add_tail(addr_of_mut!((*entry).entry), addr_of_mut!((*q).head))
            };
        } else {
            // SAFETY: detached entry under the queue guard.
            unsafe { add_after_priority(q, entry) };
        }
    }
    // SAFETY: full barrier after insertion; signal failure intentionally skips it.
    unsafe { bindings::swait_set_current_state(state as c_uint) };
    0
}

/// # Safety
/// Current task owns pinned entry until return; links initialized and either on
/// q or self-linked after removal. Other contexts can only remove, never re-add.
/// Queue remains live for lock acquisition/release when the nonempty path runs.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its export. Generated queue/entry pointers preserve the C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn finish_wait(
    q: *mut bindings::wait_queue_head,
    entry: *mut bindings::wait_queue_entry,
) {
    // SAFETY: restores this task's state; baseline uses no full barrier here.
    unsafe { bindings::__set_current_state(bindings::TASK_RUNNING) };
    // SAFETY: C acquire/marked careful test supports concurrent removal only.
    if unsafe { bindings::swait_list_empty_careful(addr_of!((*entry).entry)) } == 0 {
        // SAFETY: caller retains queue and provides valid acquisition context.
        let _guard = unsafe { IrqRestore::acquire(addr_of_mut!((*q).lock)) };
        // SAFETY: entry now protected; it may have become self-linked before
        // acquisition. Delete without a second check, matching the C baseline.
        unsafe { bindings::swait_list_del_init(addr_of_mut!((*entry).entry)) };
    }
}

/// # Safety
/// Called with entry's queue lock held in legal wake context; entry and private
/// task are live and satisfy default_wake_function's contract. Successful final
/// careful deletion can let the waiter free entry before this function returns.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its export. The signature matches the generated wait_queue_func_t C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn autoremove_wake_function(
    entry: *mut bindings::wait_queue_entry,
    mode: c_uint,
    sync: c_int,
    key: *mut c_void,
) -> c_int {
    // SAFETY: caller retains task/entry through scheduler wake and supplies
    // supported scheduler flags. C preserves WARN_ON_ONCE and scheduler policy.
    let ret = unsafe { bindings::default_wake_function(entry, mode, sync, key) };
    if ret != 0 {
        // SAFETY: live entry remains lock-protected through removal. Release
        // self-link is final entry access; acquire finish may now retire it.
        unsafe { bindings::wait_list_del_init_careful(addr_of_mut!((*entry).entry)) };
    }
    ret
}

/// # Safety
/// Current task owns this initialized/pinned wait entry and retains it across
/// sleep and final flag clear. Existing C add/remove and callback protocol owns
/// concurrent flag accesses; no Rust reference overlays that shared field.
/// Caller is in sleepable context with no queue/raw lock held and provides the
/// original schedule_timeout mode/timeout contract. Queue lifetime is external.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its export. c_long preserves the target C timeout/return ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn wait_woken(
    entry: *mut bindings::wait_queue_entry,
    mode: c_uint,
    mut timeout: c_long,
) -> c_long {
    // SAFETY: current task is live; full barrier A precedes flag observation.
    unsafe { bindings::swait_set_current_state(mode) };
    // SAFETY: entry remains live, C owns mixed-access flags. Preserve C short
    // circuit: a latched wake skips both stop/park query and scheduler call.
    if unsafe { bindings::wait_entry_flags(entry) } & bindings::WQ_FLAG_WOKEN == 0
        && !unsafe { bindings::kthread_should_stop_or_park() }
    {
        // SAFETY: caller supplies sleepable context, valid mode/timeout and
        // retains entry while asleep. Scheduler returns remaining timeout.
        timeout = unsafe { bindings::schedule_timeout(timeout) };
    }
    // SAFETY: restores this task's state without a new full barrier.
    unsafe { bindings::__set_current_state(bindings::TASK_RUNNING) };
    // SAFETY: caller retains entry; C owns exact mixed-access RMW/store-barrier B
    // paired with wake callback barrier C, preserving unrelated flag bits.
    unsafe { bindings::wait_clear_woken_mb(entry) };
    timeout
}

/// # Safety
/// Entry is live under caller's queue/wake protocol; private identifies a live
/// task accepted by default_wake_function. Waiter retains entry through callback
/// exclusion/removal. Concurrent WOKEN accesses follow the existing C protocol.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its export. The signature matches the generated wait_queue_func_t C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn woken_wake_function(
    entry: *mut bindings::wait_queue_entry,
    mode: c_uint,
    sync: c_int,
    key: *mut c_void,
) -> c_int {
    // SAFETY: entry retained; helper preserves full barrier C BEFORE C flags RMW.
    unsafe { bindings::wait_set_woken_after_mb(entry) };
    // SAFETY: caller provides original task/mode/flags/key contract. No entry
    // access follows scheduler callback. This callback does not unlink entry.
    unsafe { bindings::default_wake_function(entry, mode, sync, key) }
}

/// # Safety
/// Same wake contract as woken_wake_function; entry MUST be the wq_entry member
/// of a live wait_bit_queue_entry. arg points to a live wait_bit_key, not null;
/// key fields remain valid through matching and scheduler callback.
// SAFETY: the same Kconfig selection excludes the matching C body and retains
// its export. The signature matches the generated wait_queue_func_t C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn woken_wake_bit_function(
    entry: *mut bindings::wait_queue_entry,
    mode: c_uint,
    sync: c_int,
    arg: *mut c_void,
) -> c_int {
    // SAFETY: caller supplies containing bit-wait object and valid input key;
    // existing C matcher compares flags address plus bit_nr, not timeout.
    let key = unsafe { bindings::__var_wake_key(entry, arg) };
    if key.is_null() {
        return 0;
    }
    // SAFETY: matched key remains live; shared implementation preserves barrier
    // C before WOKEN update and forwards the matcher-returned key unchanged.
    unsafe { woken_wake_function(entry, mode, sync, key.cast()) }
}
