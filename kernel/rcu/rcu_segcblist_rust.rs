// SPDX-License-Identifier: GPL-2.0-or-later
// Translation of Linux 6.18.58 kernel/rcu/rcu_segcblist.c.
// Copyright IBM Corporation, 2017. Original author: Paul E. McKenney.

//! Segmented callback-list policy over C-owned, address-stable storage.
//!
//! All foreign memory accesses retain their original plain/marked C operations.
//! The ordered length update remains a C LKMM primitive. Neither this module nor
//! raw pointers establish Rust ownership of the lists. Callers retain the pinned
//! C layout, serialization (local IRQ exclusion/owning lock), live callback nodes
//! and lockless observation protocol. NOCB configurations are not supported.
//! No Rust references to foreign fields or initialized whole-struct copies are
//! created: GP slots may be uninitialized when their segments are empty.

use bindings::{
    rcu_list_read_long as read_long, rcu_list_read_long_once as read_long_once,
    rcu_list_read_node as read_node, rcu_list_read_node_once as read_node_once,
    rcu_list_read_tail as read_tail, rcu_list_read_tail_once as read_tail_once,
    rcu_list_read_u8 as read_u8, rcu_list_read_u8_once as read_u8_once,
    rcu_list_read_ulong as read_ulong, rcu_list_write_long as write_long,
    rcu_list_write_long_once as write_long_once, rcu_list_write_node as write_node,
    rcu_list_write_node_once as write_node_once, rcu_list_write_tail as write_tail,
    rcu_list_write_tail_once as write_tail_once, rcu_list_write_u8_once as write_u8_once,
    rcu_list_write_ulong as write_ulong,
};
use core::ptr::{addr_of_mut, null_mut};
use kernel::{
    bindings::{self, callback_head as Node, rcu_cblist as List, rcu_segcblist as SegList},
    ffi::{c_int, c_long, c_ulong},
    types::Opaque,
};
use pin_init::stack_pin_init;

const DONE: usize = bindings::RCU_DONE_TAIL as usize;
const WAIT: usize = bindings::RCU_WAIT_TAIL as usize;
const NEXT_READY: usize = bindings::RCU_NEXT_READY_TAIL as usize;
const NEXT: usize = bindings::RCU_NEXT_TAIL as usize;
const NSEGS: usize = bindings::RCU_CBLIST_NSEGS as usize;

// SAFETY contracts for these projections: list is live, index is in 0..NSEGS.
// Cast the address of the whole array before adding; never borrow its elements.
unsafe fn tail_slot(list: *mut SegList, index: usize) -> *mut *mut *mut Node {
    // SAFETY: Caller supplies a live object and valid fixed-array index.
    unsafe {
        addr_of_mut!((*list).tails)
            .cast::<*mut *mut Node>()
            .add(index)
    }
}
unsafe fn seglen_slot(list: *mut SegList, index: usize) -> *mut c_long {
    // SAFETY: Caller supplies a live object and valid fixed-array index.
    unsafe { addr_of_mut!((*list).seglen).cast::<c_long>().add(index) }
}
unsafe fn gp_slot(list: *mut SegList, index: usize) -> *mut c_ulong {
    // SAFETY: Address-only projection; validity of a subsequent read is separate.
    unsafe { addr_of_mut!((*list).gp_seq).cast::<c_ulong>().add(index) }
}
unsafe fn enabled(list: *mut SegList) -> bool {
    // SAFETY: Live initialized flags; retain marked C observation.
    unsafe {
        read_u8_once(addr_of_mut!((*list).flags)) & (bindings::RUSIX_RCU_SEGCBLIST_ENABLED as u8)
            != 0
    }
}
unsafe fn empty(list: *mut SegList) -> bool {
    // SAFETY: Live list; marked head observation does not traverse nodes.
    unsafe { read_node_once(addr_of_mut!((*list).head)).is_null() }
}
unsafe fn restempty(list: *mut SegList, index: usize) -> bool {
    // SAFETY: Caller retains the initialized tail slot and its live target;
    // baseline uses two distinct READ_ONCE operations, not a cached plain read.
    unsafe { read_node_once(read_tail_once(tail_slot(list, index))).is_null() }
}
unsafe fn segempty(list: *mut SegList, index: usize) -> bool {
    // SAFETY: Caller serializes segment topology and supplies a valid index.
    unsafe {
        let previous = if index == DONE {
            addr_of_mut!((*list).head)
        } else {
            read_tail(tail_slot(list, index - 1))
        };
        previous == read_tail(tail_slot(list, index))
    }
}
unsafe fn set_seglen(list: *mut SegList, index: usize, value: c_long) {
    // SAFETY: Live selected field; caller owns mutation, observers use C protocol.
    unsafe { write_long_once(seglen_slot(list, index), value) };
}
unsafe fn add_seglen(list: *mut SegList, index: usize, delta: c_long) {
    // SAFETY: Caller serializes RMW; preserve plain RHS and marked store.
    unsafe {
        let slot = seglen_slot(list, index);
        write_long_once(slot, read_long(slot).wrapping_add(delta));
    }
}
unsafe fn move_seglen(list: *mut SegList, from: usize, to: usize) {
    if from == to {
        return;
    }
    // SAFETY: Both indices valid, owning context serializes segment updates.
    unsafe {
        let len = read_long_once(seglen_slot(list, from));
        if len != 0 {
            add_seglen(list, to, len);
            set_seglen(list, from, 0);
        }
    }
}
fn ulong_lt(a: c_ulong, b: c_ulong) -> bool {
    c_ulong::MAX / 2 < a.wrapping_sub(b)
}

/// # Safety
/// Exclusive writable descriptor at its final address; no live owned chain is lost.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_cblist_init(list: *mut List) {
    // SAFETY: Caller provides exclusive final-address storage; initialize all fields.
    unsafe {
        write_node(addr_of_mut!((*list).head), null_mut());
        write_tail(addr_of_mut!((*list).tail), addr_of_mut!((*list).head));
        write_long(addr_of_mut!((*list).len), 0);
    }
}

/// # Safety
/// Caller serializes live list mutation and retains node storage. The node's next
/// field already has the required chain-end state; baseline does not clear it.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_cblist_enqueue(list: *mut List, node: *mut Node) {
    // SAFETY: Live initialized tail targets a writable link; node remains pinned.
    unsafe {
        write_node(read_tail(addr_of_mut!((*list).tail)), node);
        write_tail(addr_of_mut!((*list).tail), addr_of_mut!((*node).next));
        let len = addr_of_mut!((*list).len);
        write_long_once(len, read_long(len).wrapping_add(1));
    }
}

/// # Safety
/// Distinct live descriptors, serialized source and exclusive destination; caller
/// relinquishes destination's old contents. Optional node is live and unlinked.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_cblist_flush_enqueue(dst: *mut List, src: *mut List, node: *mut Node) {
    // SAFETY: Transfer only addresses/counts; descriptors remain at final addresses.
    unsafe {
        write_node(
            addr_of_mut!((*dst).head),
            read_node(addr_of_mut!((*src).head)),
        );
        let tail = if !read_node(addr_of_mut!((*dst).head)).is_null() {
            read_tail(addr_of_mut!((*src).tail))
        } else {
            addr_of_mut!((*dst).head)
        };
        write_tail(addr_of_mut!((*dst).tail), tail);
        write_long(
            addr_of_mut!((*dst).len),
            read_long(addr_of_mut!((*src).len)),
        );
        if node.is_null() {
            rcu_cblist_init(src);
        } else {
            write_node(addr_of_mut!((*node).next), null_mut());
            write_node(addr_of_mut!((*src).head), node);
            write_tail(addr_of_mut!((*src).tail), addr_of_mut!((*node).next));
            write_long_once(addr_of_mut!((*src).len), 1);
        }
    }
}

/// # Safety
/// Exclusive/serialized descriptor and live chain. Returned node ownership passes
/// to caller; caller may invoke/free it immediately after return.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_cblist_dequeue(list: *mut List) -> *mut Node {
    // SAFETY: Read current node only before transfer; repair empty self-tail.
    unsafe {
        let node = read_node(addr_of_mut!((*list).head));
        if node.is_null() {
            return null_mut();
        }
        let len = addr_of_mut!((*list).len);
        write_long(len, read_long(len).wrapping_sub(1));
        write_node(
            addr_of_mut!((*list).head),
            read_node(addr_of_mut!((*node).next)),
        );
        if read_node(addr_of_mut!((*list).head)).is_null() {
            write_tail(addr_of_mut!((*list).tail), addr_of_mut!((*list).head));
        }
        node
    }
}

/// # Safety
/// Live initialized segmented list and index in 0..RCU_CBLIST_NSEGS.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_get_seglen(list: *mut SegList, seg: c_int) -> c_long {
    // SAFETY: Caller provides valid index and initialized marked count field.
    unsafe { read_long_once(seglen_slot(list, seg as usize)) }
}

/// # Safety
/// Live initialized list; individual counts follow the original marked observations.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_n_segment_cbs(list: *mut SegList) -> c_long {
    let mut len: c_long = 0;
    for i in DONE..NSEGS {
        // SAFETY: Fixed valid index; list retained by caller.
        len = len.wrapping_add(unsafe { rcu_segcblist_get_seglen(list, i as c_int) });
    }
    len
}

/// # Safety
/// Live initialized list; caller serializes non-NOCB length updates. Total count
/// can include detached callbacks; barrier observations retain the pinned protocol.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_add_len(list: *mut SegList, delta: c_long) {
    // SAFETY: Exact combined C mb/update/mb operation; no Rust shared-memory access.
    unsafe { bindings::rcu_list_ordered_add_len(addr_of_mut!((*list).len), delta) };
}

/// # Safety
/// Same live-list serialization and observer contract as rcu_segcblist_add_len.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_inc_len(list: *mut SegList) {
    // SAFETY: Caller supplies add_len's prerequisites.
    unsafe { rcu_segcblist_add_len(list, 1) };
}

/// # Safety
/// Address-stable writable storage with initialized flags; caller excludes access
/// during initialization and accounts for any old callbacks. GP slots are untouched.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_init(list: *mut SegList) {
    // SAFETY: Exclusive initialization, but preserve original marked count/flag stores.
    unsafe {
        write_node(addr_of_mut!((*list).head), null_mut());
        for i in 0..NSEGS {
            write_tail(tail_slot(list, i), addr_of_mut!((*list).head));
            set_seglen(list, i, 0);
        }
        write_long_once(addr_of_mut!((*list).len), 0);
        let flags = addr_of_mut!((*list).flags);
        write_u8_once(
            flags,
            read_u8(flags) | (bindings::RUSIX_RCU_SEGCBLIST_ENABLED as u8),
        );
    }
}

/// # Safety
/// Live initialized list, serialized flag mutation; it should be empty. Misuse
/// retains the original warnings and subsequent flag clear, rather than panicking.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_disable(list: *mut SegList) {
    // SAFETY: Retained list; diagnostics use original independently marked reads.
    unsafe {
        bindings::rcu_list_warn_disable_head(!empty(list));
        bindings::rcu_list_warn_disable_len(read_long_once(addr_of_mut!((*list).len)) != 0);
        let flags = addr_of_mut!((*list).flags);
        write_u8_once(
            flags,
            read_u8(flags) & !(bindings::RUSIX_RCU_SEGCBLIST_ENABLED as u8),
        );
    }
}

/// # Safety
/// Live initialized list, retained through the original marked observations.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_ready_cbs(list: *mut SegList) -> bool {
    // SAFETY: Address comparison does not dereference a callback.
    unsafe { enabled(list) && addr_of_mut!((*list).head) != read_tail_once(tail_slot(list, DONE)) }
}

/// # Safety
/// Live initialized list and live tail target under the baseline observer protocol.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_pend_cbs(list: *mut SegList) -> bool {
    // SAFETY: Retain the enabled short circuit before traversing the tail slot.
    unsafe { enabled(list) && !restempty(list, DONE) }
}

/// # Safety
/// Live list; caller ensures the returned diagnostic pointer's lifetime if used.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_first_cb(list: *mut SegList) -> *mut Node {
    // SAFETY: Original marked flag and plain head observation, no node dereference.
    unsafe {
        if enabled(list) {
            read_node(addr_of_mut!((*list).head))
        } else {
            null_mut()
        }
    }
}

/// # Safety
/// Live initialized list with stable tail topology and target; pointer is borrowed.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_first_pend_cb(list: *mut SegList) -> *mut Node {
    // SAFETY: Original plain tail/target accesses under caller's ownership context.
    unsafe {
        if enabled(list) {
            read_node(read_tail(tail_slot(list, DONE)))
        } else {
            null_mut()
        }
    }
}

/// # Safety
/// Serialized live list; output is exclusively writable. WAIT GP value must be
/// initialized when pending callbacks exist, as in the baseline segment invariant.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_nextgp(list: *mut SegList, out: *mut c_ulong) -> bool {
    // SAFETY: Do not touch output or GP slot on false path.
    unsafe {
        if !rcu_segcblist_pend_cbs(list) {
            return false;
        }
        write_ulong(out, read_ulong(gp_slot(list, WAIT)));
        true
    }
}

/// # Safety
/// Caller serializes live list mutation; node is live, address-stable and available
/// for enqueue. Counts must be published before the linked callback becomes visible.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_enqueue(list: *mut SegList, node: *mut Node) {
    // SAFETY: Caller retains all writable links; publication order matches C.
    unsafe {
        rcu_segcblist_inc_len(list);
        add_seglen(list, NEXT, 1);
        write_node(addr_of_mut!((*node).next), null_mut());
        write_node_once(read_tail(tail_slot(list, NEXT)), node);
        write_tail_once(tail_slot(list, NEXT), addr_of_mut!((*node).next));
    }
}

/// # Safety
/// Serialized initialized list, live unlinked node. This orders behind existing
/// callbacks (including detached callbacks), and does not promise a grace period.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_entrain(list: *mut SegList, node: *mut Node) -> bool {
    // SAFETY: Count may be positive with head NULL; DONE insertion remains valid.
    unsafe {
        if read_long_once(addr_of_mut!((*list).len)) == 0 {
            return false;
        }
        rcu_segcblist_inc_len(list);
        bindings::rcu_list_mb();
        write_node(addr_of_mut!((*node).next), null_mut());
        let mut i = NEXT;
        while i > DONE {
            if !segempty(list, i) {
                break;
            }
            i -= 1;
        }
        add_seglen(list, i, 1);
        write_node_once(read_tail(tail_slot(list, i)), node);
        while i <= NEXT {
            write_tail_once(tail_slot(list, i), addr_of_mut!((*node).next));
            i += 1;
        }
        true
    }
}

/// # Safety
/// Serialized live list and distinct initialized destination descriptor with a
/// writable tail. Detached nodes remain live; total list length is not reduced.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_extract_done_cbs(list: *mut SegList, out: *mut List) {
    // SAFETY: Transfer topology without invoking nodes; reverse iteration preserves
    // the old DONE boundary until its last comparison, exactly as in C.
    unsafe {
        if !rcu_segcblist_ready_cbs(list) {
            return;
        }
        write_long(
            addr_of_mut!((*out).len),
            rcu_segcblist_get_seglen(list, DONE as c_int),
        );
        write_node(
            read_tail(addr_of_mut!((*out).tail)),
            read_node(addr_of_mut!((*list).head)),
        );
        write_node_once(
            addr_of_mut!((*list).head),
            read_node(read_tail(tail_slot(list, DONE))),
        );
        write_node_once(read_tail(tail_slot(list, DONE)), null_mut());
        write_tail(addr_of_mut!((*out).tail), read_tail(tail_slot(list, DONE)));
        for i in (DONE..NSEGS).rev() {
            if read_tail(tail_slot(list, i)) == read_tail(tail_slot(list, DONE)) {
                write_tail_once(tail_slot(list, i), addr_of_mut!((*list).head));
            }
        }
        set_seglen(list, DONE, 0);
    }
}

/// # Safety
/// Serialized live list and distinct initialized destination; pending nodes are
/// transferred without total count adjustment, and their GP progress is lost.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_extract_pend_cbs(list: *mut SegList, out: *mut List) {
    // SAFETY: Retained mutable links and separate output, original transfer order.
    unsafe {
        if !rcu_segcblist_pend_cbs(list) {
            return;
        }
        write_long(addr_of_mut!((*out).len), 0);
        write_node(
            read_tail(addr_of_mut!((*out).tail)),
            read_node(read_tail(tail_slot(list, DONE))),
        );
        write_tail(addr_of_mut!((*out).tail), read_tail(tail_slot(list, NEXT)));
        write_node_once(read_tail(tail_slot(list, DONE)), null_mut());
        for i in DONE + 1..NSEGS {
            let len = addr_of_mut!((*out).len);
            write_long(
                len,
                read_long(len).wrapping_add(rcu_segcblist_get_seglen(list, i as c_int)),
            );
            write_tail_once(tail_slot(list, i), read_tail(tail_slot(list, DONE)));
            set_seglen(list, i, 0);
        }
    }
}

/// # Safety
/// Serialized live segmented count and live source descriptor whose count is valid.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_insert_count(list: *mut SegList, src: *mut List) {
    // SAFETY: Count transfer is independent of node transfer; caller orders both.
    unsafe { rcu_segcblist_add_len(list, read_long(addr_of_mut!((*src).len))) };
}

/// # Safety
/// Serialized live destination and exclusively owned detached source chain;
/// ownership transfers once. Source len stays unchanged after clearing its links.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_insert_done_cbs(list: *mut SegList, src: *mut List) {
    // SAFETY: All nodes retained; prepend without a duplicate owning source chain.
    unsafe {
        if read_node(addr_of_mut!((*src).head)).is_null() {
            return;
        }
        add_seglen(list, DONE, read_long(addr_of_mut!((*src).len)));
        write_node(
            read_tail(addr_of_mut!((*src).tail)),
            read_node(addr_of_mut!((*list).head)),
        );
        write_node_once(
            addr_of_mut!((*list).head),
            read_node(addr_of_mut!((*src).head)),
        );
        for i in DONE..NSEGS {
            if addr_of_mut!((*list).head) == read_tail(tail_slot(list, i)) {
                write_tail_once(tail_slot(list, i), read_tail(addr_of_mut!((*src).tail)));
            } else {
                break;
            }
        }
        write_node(addr_of_mut!((*src).head), null_mut());
        write_tail(addr_of_mut!((*src).tail), addr_of_mut!((*src).head));
    }
}

/// # Safety
/// Serialized destination and detached source chain. Source descriptor is left
/// unchanged by baseline: caller must relinquish it as an independent owning list.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_insert_pend_cbs(list: *mut SegList, src: *mut List) {
    // SAFETY: Transfer live chain without clearing borrowed source descriptor.
    unsafe {
        if read_node(addr_of_mut!((*src).head)).is_null() {
            return;
        }
        add_seglen(list, NEXT, read_long(addr_of_mut!((*src).len)));
        write_node_once(
            read_tail(tail_slot(list, NEXT)),
            read_node(addr_of_mut!((*src).head)),
        );
        write_tail_once(tail_slot(list, NEXT), read_tail(addr_of_mut!((*src).tail)));
    }
}

/// # Safety
/// Serialized live segmented list. GP slots read by the baseline advancement path
/// must contain initialized sequence values. Sequence ordering uses modular ulong.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_advance(list: *mut SegList, seq: c_ulong) {
    // SAFETY: All selected indices stay in fixed arrays; foreign access stays C.
    unsafe {
        bindings::rcu_list_warn_advance(!enabled(list));
        if restempty(list, DONE) {
            return;
        }
        let mut i = WAIT;
        while i < NEXT {
            if ulong_lt(seq, read_ulong(gp_slot(list, i))) {
                break;
            }
            write_tail_once(tail_slot(list, DONE), read_tail(tail_slot(list, i)));
            move_seglen(list, i, DONE);
            i += 1;
        }
        if i == WAIT {
            return;
        }
        for j in WAIT..i {
            write_tail_once(tail_slot(list, j), read_tail(tail_slot(list, DONE)));
        }
        let mut j = WAIT;
        while i < NEXT {
            if read_tail(tail_slot(list, j)) == read_tail(tail_slot(list, NEXT)) {
                break;
            }
            write_tail_once(tail_slot(list, j), read_tail(tail_slot(list, i)));
            move_seglen(list, i, j);
            write_ulong(gp_slot(list, j), read_ulong(gp_slot(list, i)));
            i += 1;
            j += 1;
        }
    }
}

/// # Safety
/// Serialized live list with initialized GP values in nonempty labelled segments;
/// caller supplies the baseline conservative grace-period sequence snapshot.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_accelerate(list: *mut SegList, seq: c_ulong) -> bool {
    // SAFETY: Descending/ascending bounds preserve baseline short circuits and
    // never inspect an unlabelled GP slot merely to compare an empty segment.
    unsafe {
        bindings::rcu_list_warn_accelerate(!enabled(list));
        if restempty(list, DONE) {
            return false;
        }
        let mut i = NEXT_READY;
        while i > DONE {
            if !segempty(list, i) && ulong_lt(read_ulong(gp_slot(list, i)), seq) {
                break;
            }
            i -= 1;
        }
        if restempty(list, i) {
            return false;
        }
        i += 1;
        if i >= NEXT {
            return false;
        }
        for j in i + 1..=NEXT {
            move_seglen(list, j, i);
        }
        while i < NEXT {
            write_tail_once(tail_slot(list, i), read_tail(tail_slot(list, NEXT)));
            write_ulong(gp_slot(list, i), seq);
            i += 1;
        }
        true
    }
}

/// # Safety
/// Distinct live serialized lists, CPUs held as baseline requires; source callbacks
/// are transferred once. Pending callbacks restart GP tracking. No invocation runs.
// SAFETY: Unique selected definition, matching original C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_segcblist_merge(dst: *mut SegList, src: *mut SegList) {
    // SAFETY: Preserve caller's hotplug lockdep assertion before any transfer.
    unsafe { bindings::rcu_list_cpus_held() };
    stack_pin_init!(let done = Opaque::ffi_init(|list: *mut List| {
        // SAFETY: Private final-address stack storage, initialized before linking.
        unsafe { rcu_cblist_init(list) };
    }));
    stack_pin_init!(let pending = Opaque::ffi_init(|list: *mut List| {
        // SAFETY: Separate private final-address descriptor, retained until transfer.
        unsafe { rcu_cblist_init(list) };
    }));
    // SAFETY: Both pinned descriptors survive all transfers; C callbacks never
    // execute here. CPUs-held excludes rcu_barrier, so source reset needs no mb.
    unsafe {
        rcu_segcblist_extract_done_cbs(src, done.get());
        rcu_segcblist_extract_pend_cbs(src, pending.get());
        write_long_once(addr_of_mut!((*src).len), 0);
        rcu_segcblist_insert_count(dst, done.get());
        rcu_segcblist_insert_count(dst, pending.get());
        rcu_segcblist_insert_done_cbs(dst, done.get());
        rcu_segcblist_insert_pend_cbs(dst, pending.get());
        rcu_segcblist_init(src);
    }
}
