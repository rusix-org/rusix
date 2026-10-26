// SPDX-License-Identifier: GPL-2.0-only
// Rust translation of Linux 6.18.58 wait-bit loops, actions and stack wrappers.

//! Bit/variable key matching and wait policy over C-visible pinned waiters.
//!
//! Hash queues, variable-wait initialization, bit operations, jiffies reads and
//! scheduler primitives remain C. No Rust reference overlays a shared C bitmap.

use core::ptr::{addr_of, addr_of_mut, null_mut};
use kernel::{
    bindings,
    ffi::{c_int, c_uint, c_ulong, c_void},
    types::Opaque,
};
use pin_init::stack_pin_init;

#[path = "wait_bit_rust/time.rs"]
mod time;

/// # Safety
/// entry is the wq_entry member of a live wait_bit_queue_entry; arg points to a
/// live wait_bit_key. Their flags/bit_nr are initialized/stable while compared.
/// timeout is not inspected. Neither arg nor entry is nullable here.
// SAFETY: matching C definition is excluded; existing non-exported ABI retained.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn __var_wake_key(
    entry: *mut bindings::wait_queue_entry,
    arg: *mut c_void,
) -> *mut bindings::wait_bit_key {
    let key = arg.cast::<bindings::wait_bit_key>();
    // SAFETY: caller guarantees containing bit-wait object, not a generic entry.
    let waiter = unsafe { kernel::container_of!(entry, bindings::wait_bit_queue_entry, wq_entry) };
    // SAFETY: initialized stable identity fields; only raw scalar reads, no
    // reference overlay on the concurrently mutable bitmap or whole waiter.
    if unsafe {
        addr_of!((*waiter).key.flags).read() != addr_of!((*key).flags).read()
            || addr_of!((*waiter).key.bit_nr).read() != addr_of!((*key).bit_nr).read()
    } {
        return null_mut();
    }
    key
}

/// # Safety
/// __var_wake_key requirements and generic autoremove callback contract apply.
/// A matching key names valid bit storage for the original C bitops; caller
/// holds the wait queue lock and retains task/entry until final removal.
// SAFETY: matching C body is excluded; its export and exact callback ABI remain.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn wake_bit_function(
    entry: *mut bindings::wait_queue_entry,
    mode: c_uint,
    sync: c_int,
    arg: *mut c_void,
) -> c_int {
    // SAFETY: live containing bit waiter and stable valid identity key.
    let key = unsafe { __var_wake_key(entry, arg) };
    if key.is_null() {
        return 0;
    }
    // SAFETY: matched initialized key points to valid bitmap; C owns marked bit
    // access. Mismatches above deliberately avoid touching bitmap storage.
    if unsafe { bindings::wait_bit_test(key) } != 0 {
        return 0;
    }
    // SAFETY: queue lock and retained task satisfy callback. Entry may be freed
    // after final careful removal; never access it after this invocation.
    unsafe { bindings::autoremove_wake_function(entry, mode, sync, key.cast()) }
}

/// # Safety
/// Current task owns initialized pinned waiter/queue/bitmap through finish.
/// Action is nonnull when invoked, may sleep, returns in this task and preserves
/// waiter/key lifetime. Caller is sleepable and not holding queue lock; mode is
/// accepted by the existing wait/action protocol. No concurrent key mutation.
// SAFETY: __sched requires scheduler text placement; matching C body is excluded
// and its pointer/action/integer ABI and export are retained.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
pub unsafe extern "C" fn __wait_on_bit(
    q: *mut bindings::wait_queue_head,
    waiter: *mut bindings::wait_bit_queue_entry,
    action: bindings::wait_bit_action_f,
    mode: c_uint,
) -> c_int {
    // SAFETY: raw projections of caller-retained initialized waiter.
    let entry = unsafe { addr_of_mut!((*waiter).wq_entry) };
    let key = unsafe { addr_of_mut!((*waiter).key) };
    let mut ret = 0;
    loop {
        // SAFETY: current task's waiter initialized; function owns lock/state.
        unsafe { bindings::prepare_to_wait(q, entry, mode as c_int) };
        // SAFETY: initialized key points to bitmap valid for C bitops.
        if unsafe { bindings::wait_bit_test(key) } != 0 {
            // SAFETY: action valid when invoked; preserve unsigned->C int bits.
            ret = unsafe { action.unwrap_unchecked()(key, mode as c_int) };
        }
        // SAFETY: acquire bit test must execute even if action returned error.
        if unsafe { bindings::wait_bit_test_acquire(key) } == 0 || ret != 0 {
            break;
        }
    }
    // SAFETY: live current waiter; performs final removal/state restoration.
    unsafe { bindings::finish_wait(q, entry) };
    ret
}

/// # Safety
/// Same requirements as __wait_on_bit, with writable bitmap for fully ordered
/// test-and-set and caller ownership of the bit after successful return.
// SAFETY: exact C ABI/export and original __sched text section preserved.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
pub unsafe extern "C" fn __wait_on_bit_lock(
    q: *mut bindings::wait_queue_head,
    waiter: *mut bindings::wait_bit_queue_entry,
    action: bindings::wait_bit_action_f,
    mode: c_uint,
) -> c_int {
    // SAFETY: initialized caller-retained waiter, raw field projections.
    let entry = unsafe { addr_of_mut!((*waiter).wq_entry) };
    let key = unsafe { addr_of_mut!((*waiter).key) };
    let mut ret = 0;
    loop {
        // SAFETY: current waiter/queue stable; return boolean is ignored by C.
        unsafe { bindings::prepare_to_wait_exclusive(q, entry, mode as c_int) };
        // SAFETY: bitmap/key valid for baseline C bit operation.
        if unsafe { bindings::wait_bit_test(key) } != 0 {
            // SAFETY: valid action callback, mode bit pattern and sleep context.
            ret = unsafe { action.unwrap_unchecked()(key, mode as c_int) };
            if ret != 0 {
                // SAFETY: remove before atomic attempt on action error, as C.
                unsafe { bindings::finish_wait(q, entry) };
            }
        }
        // SAFETY: full ordering and atomic claim retained in C; execute even
        // after action failure. Successful acquisition OVERRIDES that error.
        if unsafe { bindings::wait_bit_test_and_set(key) } == 0 {
            if ret == 0 {
                // SAFETY: error path already finished; normal path finishes now.
                unsafe { bindings::finish_wait(q, entry) };
            }
            return 0;
        } else if ret != 0 {
            return ret;
        }
    }
}

/// # Safety
/// Current prepared waiter may schedule; mode satisfies signal-state protocol.
/// key is unused and need not be dereferenced by this action.
// SAFETY: exact original action ABI/export and scheduler section preserved.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
pub unsafe extern "C" fn bit_wait(_key: *mut bindings::wait_bit_key, mode: c_int) -> c_int {
    // SAFETY: caller prepared task state and provides sleepable context.
    unsafe { bindings::schedule() };
    // SAFETY: current task live; signal check intentionally happens after sleep.
    if unsafe { bindings::signal_pending_state(mode as c_uint, bindings::get_current()) } != 0 {
        -(bindings::EINTR as c_int)
    } else {
        0
    }
}

/// # Safety
/// Same as bit_wait, with I/O scheduling accounting permitted by caller.
// SAFETY: exact original action ABI/export and scheduler section preserved.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
pub unsafe extern "C" fn bit_wait_io(_key: *mut bindings::wait_bit_key, mode: c_int) -> c_int {
    // SAFETY: prepared current task, sleepable I/O wait context.
    unsafe { bindings::io_schedule() };
    // SAFETY: original signal-state test after I/O scheduler returns.
    if unsafe { bindings::signal_pending_state(mode as c_uint, bindings::get_current()) } != 0 {
        -(bindings::EINTR as c_int)
    } else {
        0
    }
}

/// # Safety
/// Initialized stable deadline key retained across sleep; caller provides
/// prepared task state and bounded modular-jiffies timeout contract.
// SAFETY: exact original C action ABI/GPL export and __sched section preserved.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
pub unsafe extern "C" fn bit_wait_timeout(key: *mut bindings::wait_bit_key, mode: c_int) -> c_int {
    // SAFETY: C READ_ONCE of shared jiffies; no Rust reference to its storage.
    let now = unsafe { bindings::wait_bit_jiffies() };
    // SAFETY: caller retains initialized key with no concurrent deadline writer.
    let deadline = unsafe { addr_of!((*key).timeout).read() };
    // Exact time_after_eq: cast modular unsigned difference to signed long.
    if time::deadline_expired(now, deadline) {
        return -(bindings::EAGAIN as c_int);
    }
    // SAFETY: same valid key, reload matches original second timeout access.
    let remaining = time::remaining_interval(unsafe { addr_of!((*key).timeout).read() }, now);
    // SAFETY: deadline contract yields valid scheduler timeout; return ignored,
    // because the outer wait loop owns bit/expiry/error reevaluation.
    unsafe { bindings::schedule_timeout(remaining) };
    // SAFETY: signal check follows scheduler; expiry path above skips it.
    if unsafe { bindings::signal_pending_state(mode as c_uint, bindings::get_current()) } != 0 {
        -(bindings::EINTR as c_int)
    } else {
        0
    }
}

/// # Safety
/// word/bit/action/mode satisfy the chosen wait loop; underlying bitmap and hash
/// queue stay valid. Timeout follows modular-jiffies API limits. May sleep.
// SAFETY: helper is in the scheduler call chain, matching original wrapper text.
#[unsafe(link_section = ".sched.text")]
unsafe fn with_bit_waiter(
    word: *mut c_ulong,
    bit: c_int,
    action: bindings::wait_bit_action_f,
    mode: c_uint,
    timeout: Option<c_ulong>,
    lock: bool,
) -> c_int {
    // SAFETY: original hash lookup, caller supplies valid word/bit identity.
    let q = unsafe { bindings::bit_waitqueue(word, bit) };
    // Self-links are formed ONLY at the final pinned stack address. Moving a
    // preinitialized local into Opaque would leave dangling self-pointers.
    stack_pin_init!(let storage = Opaque::ffi_init(|waiter: *mut bindings::wait_bit_queue_entry| {
        // SAFETY: exclusively owned uninitialized final storage; initialize all
        // semantic fields before any waiter publication. No struct reference.
        unsafe {
            addr_of_mut!((*waiter).key.flags).write(word);
            addr_of_mut!((*waiter).key.bit_nr).write(bit);
            addr_of_mut!((*waiter).key.timeout).write(0);
            addr_of_mut!((*waiter).wq_entry.flags).write(0);
            addr_of_mut!((*waiter).wq_entry.private).write(bindings::get_current().cast());
            addr_of_mut!((*waiter).wq_entry.func).write(Some(wake_bit_function));
            let node = addr_of_mut!((*waiter).wq_entry.entry);
            addr_of_mut!((*node).next).write(node);
            addr_of_mut!((*node).prev).write(node);
        }
    }));
    let waiter = storage.get();
    if let Some(delta) = timeout {
        // SAFETY: C marked jiffies read and exclusive unpublished key write.
        unsafe {
            addr_of_mut!((*waiter).key.timeout)
                .write(time::deadline_after(bindings::wait_bit_jiffies(), delta));
        }
    }
    // SAFETY: fully initialized/pinned stack waiter survives through loop and
    // final finish_wait. All loop exits remove membership before storage drops.
    unsafe {
        if lock {
            __wait_on_bit_lock(q, waiter, action, mode)
        } else {
            __wait_on_bit(q, waiter, action, mode)
        }
    }
}

/// # Safety
/// with_bit_waiter's normal wait contract applies.
// SAFETY: same selection excludes C body and retains original ABI/export/text.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
pub unsafe extern "C" fn out_of_line_wait_on_bit(
    word: *mut c_ulong,
    bit: c_int,
    action: bindings::wait_bit_action_f,
    mode: c_uint,
) -> c_int {
    // SAFETY: caller supplies valid ordinary bit wait contract.
    unsafe { with_bit_waiter(word, bit, action, mode, None, false) }
}

/// # Safety
/// with_bit_waiter's normal wait and modular timeout contracts apply.
// SAFETY: same selection excludes C body and retains original GPL export/text.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
pub unsafe extern "C" fn out_of_line_wait_on_bit_timeout(
    word: *mut c_ulong,
    bit: c_int,
    action: bindings::wait_bit_action_f,
    mode: c_uint,
    timeout: c_ulong,
) -> c_int {
    // SAFETY: caller supplies ordinary wait with valid modular-jiffies deadline.
    unsafe { with_bit_waiter(word, bit, action, mode, Some(timeout), false) }
}

/// # Safety
/// with_bit_waiter's bit-acquisition contract applies; success owns the bit.
// SAFETY: same selection excludes C body and retains original ABI/export/text.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".sched.text")]
pub unsafe extern "C" fn out_of_line_wait_on_bit_lock(
    word: *mut c_ulong,
    bit: c_int,
    action: bindings::wait_bit_action_f,
    mode: c_uint,
) -> c_int {
    // SAFETY: caller supplies writable bitmap and correct bit-lock protocol.
    unsafe { with_bit_waiter(word, bit, action, mode, None, true) }
}
