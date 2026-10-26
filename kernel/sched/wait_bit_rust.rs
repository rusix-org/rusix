// SPDX-License-Identifier: GPL-2.0-only
// Rust translation of Linux 6.18.58 bit/variable wait ownership and policy.

//! Bit/variable key matching and wait policy over C-visible pinned waiters.
//!
//! Rust owns the permanent hash table and its boot initialization as well as
//! wait/wake policy. Lock/lockdep, marked list access, bit operations, jiffies
//! reads and scheduler primitives remain C. Shared bitmaps are never borrowed.

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

#[cfg(not(all(target_arch = "x86_64", target_pointer_width = "64")))]
compile_error!("wait table hash translation currently requires x86_64");
#[cfg(CONFIG_HAVE_ARCH_HASH)]
compile_error!("wait table hash requires a new audit for architecture overrides");

#[repr(transparent)]
struct WaitTable(Opaque<bindings::rusix_wait_bit_table>);
// SAFETY: permanent storage; only boot's single wait_bit_init writes before
// publication. Afterwards each head is accessed under its original spinlock,
// except list_empty's original marked observation. No safe mutable access or
// reference to the heads is exposed. All entry points have unsafe C contracts.
unsafe impl Sync for WaitTable {}

// SAFETY: configured alignment comes from the bindgen type; keep baseline
// permanent writable cacheline section (not init data or ro_after_init).
#[unsafe(link_section = ".data..cacheline_aligned")]
static BIT_WAIT_TABLE: WaitTable = WaitTable(Opaque::zeroed());

#[repr(transparent)]
struct WaitTableClass(Opaque<bindings::lock_class_key>);
// SAFETY: permanent lockdep key storage; lockdep owns and synchronizes use.
// Never read through a Rust reference; not an initialized Rust lock object.
unsafe impl Sync for WaitTableClass {}
static BIT_WAIT_CLASS: WaitTableClass = WaitTableClass(Opaque::zeroed());
const BIT_WAIT_NAME: &[u8] = b"bit_wait_table + i\0";
const TABLE_SIZE: usize = 256;
const _: () = assert!(
    core::mem::align_of::<WaitTable>() == bindings::RUSIX_WAIT_BIT_TABLE_ALIGNMENT as usize
);
const _: () = assert!(
    core::mem::size_of::<WaitTable>()
        == TABLE_SIZE * core::mem::size_of::<bindings::wait_queue_head>()
);

// x86_64 has no HAVE_ARCH_HASH override. Keep exact modulo-2^64 multiply and
// unsigned high-eight-bit selection; do not mask signed bit into [0,63].
fn table_hash(value: c_ulong) -> usize {
    (value.wrapping_mul(0x61c8_8646_80b5_83eb) >> 56) as usize
}

/// # Safety
/// Only single boot initialization may use uninitialized storage. All other
/// callers require completed wait_bit_init. index must be below TABLE_SIZE.
unsafe fn table_head(index: usize) -> *mut bindings::wait_queue_head {
    // SAFETY: permanent Opaque storage is aligned for its bindgen shell; raw
    // projection never creates an array/head reference over C-visible memory.
    let first = unsafe { addr_of_mut!((*BIT_WAIT_TABLE.0.get()).heads) }
        .cast::<bindings::wait_queue_head>();
    // SAFETY: index contract keeps pointer within the 256-element array.
    unsafe { first.add(index) }
}

/// # Safety
/// Called once by sched_init before any wait table use or secondary users.
/// Must never reinitialize live queues; no allocation or sleep is permitted.
// SAFETY: original non-exported C definition is excluded, exact void ABI and
// __init section retained. Key/name deliberately outlive freed init text.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".init.text")]
#[cold]
pub unsafe extern "C" fn wait_bit_init() {
    for i in 0..TABLE_SIZE {
        // SAFETY: boot exclusively owns each still-unpublished head at final
        // address. One shared permanent key/name matches the single original
        // macro expansion; ordinary spinlock init stays in its existing adapter.
        unsafe {
            bindings::__init_waitqueue_head(
                table_head(i),
                BIT_WAIT_NAME.as_ptr().cast(),
                BIT_WAIT_CLASS.0.get(),
            );
        }
    }
}

/// # Safety
/// Initialization completed. Identity conversion does not dereference word;
/// use of the returned queue/waiters must obey their generic wait contracts.
// SAFETY: exclude matching C body, retain original C export unchanged.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn bit_waitqueue(
    word: *mut c_ulong,
    bit: c_int,
) -> *mut bindings::wait_queue_head {
    let value = (word as c_ulong).wrapping_shl(6) | (bit as c_ulong);
    // SAFETY: high-eight-bit hash is always in 0..256; table initialized.
    unsafe { table_head(table_hash(value)) }
}

/// # Safety
/// Same initialized-table/returned-queue contract as bit_waitqueue.
// SAFETY: exclude matching C definition; retain export and exact pointer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn __var_waitqueue(var: *mut c_void) -> *mut bindings::wait_queue_head {
    // SAFETY: hash is in bounds; no dereference of the identity address.
    unsafe { table_head(table_hash(var as c_ulong)) }
}

/// # Safety
/// Queue and word identity live for dispatch. Caller supplies original
/// condition-publication/full-barrier protocol, and valid bitmap when a matching
/// bit callback can inspect it. For bit=-1 variable callbacks do not read bitmap.
// SAFETY: matching C body excluded, original exported ABI unchanged.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn __wake_up_bit(
    q: *mut bindings::wait_queue_head,
    word: *mut c_ulong,
    bit: c_int,
) {
    let mut key = bindings::wait_bit_key {
        flags: word,
        bit_nr: bit,
        timeout: 0,
    };
    // SAFETY: baseline waitqueue_active is exactly !list_empty(&q->head).
    // Reuse marked C list read; Rust never reads links concurrently directly.
    if unsafe { bindings::swait_list_empty(addr_of!((*q).head)) } == 0 {
        // SAFETY: key remains live until synchronous callback traversal returns;
        // callbacks may not retain it. Queue lock is owned by __wake_up. Ignore
        // wake count, as original void API does. No post-callback entry access.
        unsafe {
            bindings::__wake_up(
                q,
                bindings::TASK_NORMAL,
                1,
                (&mut key as *mut bindings::wait_bit_key).cast(),
            )
        };
    }
}

/// # Safety
/// __wake_up_bit contract, including caller-provided ordering, applies.
// SAFETY: matching C body excluded; original export retained.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn wake_up_bit(word: *mut c_ulong, bit: c_int) {
    // SAFETY: hash lookup is initialized; caller owns bit publication protocol.
    unsafe { __wake_up_bit(bit_waitqueue(word, bit), word, bit) };
}

/// # Safety
/// __var_wake_key and autoremove callback contracts; entry belongs to a retained
/// variable waiter under its queue lock, arg is a synchronous live wake key.
unsafe extern "C" fn var_wake_function(
    entry: *mut bindings::wait_queue_entry,
    mode: c_uint,
    sync: c_int,
    arg: *mut c_void,
) -> c_int {
    // SAFETY: identity fields stable under callback contract; no bitmap load.
    let key = unsafe { __var_wake_key(entry, arg) };
    if key.is_null() {
        return 0;
    }
    // SAFETY: retained task and locked membership; do not touch entry after
    // autoremove, which may release its owner's final lifetime protection.
    unsafe { bindings::autoremove_wake_function(entry, mode, sync, key.cast()) }
}

/// # Safety
/// Caller owns writable final-address storage, no waiter/observer/old membership
/// remains. Initializing task is current; var identity outlives enrollment.
/// Publish only after return; never move storage while its self-links are live.
// SAFETY: matching C body/callback excluded; original exported ABI retained.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn init_wait_var_entry(
    waiter: *mut bindings::wait_bit_queue_entry,
    var: *mut c_void,
    flags: c_int,
) {
    // SAFETY: exclusive unpublished storage. Initialize all semantic fields,
    // including C omitted aggregate members, and self-links at final address.
    // Padding is not observable initialization evidence and is never read.
    unsafe {
        addr_of_mut!((*waiter).key.flags).write(var.cast());
        addr_of_mut!((*waiter).key.bit_nr).write(-1);
        addr_of_mut!((*waiter).key.timeout).write(0);
        addr_of_mut!((*waiter).wq_entry.flags).write(flags as c_uint);
        addr_of_mut!((*waiter).wq_entry.private).write(bindings::get_current().cast());
        addr_of_mut!((*waiter).wq_entry.func).write(Some(var_wake_function));
        let node = addr_of_mut!((*waiter).wq_entry.entry);
        addr_of_mut!((*node).next).write(node);
        addr_of_mut!((*node).prev).write(node);
    }
}

/// # Safety
/// Variable condition publication/barrier and live identity contracts of
/// wake_up_var apply; this function supplies no missing publication barrier.
// SAFETY: matching C body excluded; original export retained.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn wake_up_var(var: *mut c_void) {
    // SAFETY: initialized queue, variable key identity, no bitmap dereference.
    unsafe { __wake_up_bit(__var_waitqueue(var), var.cast(), -1) };
}
