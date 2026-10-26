// SPDX-License-Identifier: GPL-2.0-only
// Translation of Linux 6.18.58 tree.c callback batch transaction/time predicate.

//! The pinned detached descriptor owns dispatch/link rights until explicit
//! reinsertion and total-count commit. Callback payload allocations are foreign;
//! invocation can destroy or requeue the current head. Per-CPU state, shared
//! accesses and architecture/debug/trace primitives remain C, never Rust refs.

use kernel::{
    bindings::{self, rcu_cblist as List},
    ffi::{c_long, c_ulong, c_void},
    types::Opaque,
};
use pin_init::stack_pin_init;

const RUNNING: u32 = bindings::RUSIX_RCU_BATCH_KTHREAD_RUNNING;
const MAX_BLIMIT: c_long = bindings::RUSIX_RCU_BATCH_MAX_BLIMIT as c_long;
const NS_MSEC: c_long = bindings::RUSIX_RCU_BATCH_NSEC_PER_MSEC as c_long;
const NS_SEC: c_long = bindings::RUSIX_RCU_BATCH_NSEC_PER_SEC as c_long;
const NPJ: c_long = NS_SEC / bindings::RUSIX_RCU_BATCH_HZ as c_long;
const DOUBLE_CHECK: bool = bindings::RUSIX_RCU_BATCH_DOUBLE_CHECK != 0;

/// # Safety
/// Same clock/context requirements as local_clock/jiffies. This only observes
/// time and does not grant ownership or change scheduling state.
// SAFETY: Internal bridge prototype matches rusix_rcu_batch.h. Also used by the
// C-first fixture's selected wrapper; production and test execute one predicate.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_rcu_batch_check_time(
    count: c_long,
    tlimit: c_long,
    jlimit_check: bool,
    jlimit: c_ulong,
) -> bool {
    if tlimit == 0 {
        return false;
    }
    if count & 31 != 0 {
        if !DOUBLE_CHECK || !jlimit_check {
            return false;
        }
        // SAFETY: Canonical volatile jiffies read. time_after(jiffies,jlimit)
        // is signed wrapping (jlimit-jiffies)<0, not a direct unsigned comparison.
        let now = unsafe { bindings::rusix_rcubatch_jiffies() };
        if (jlimit.wrapping_sub(now) as c_long) >= 0 {
            return false;
        }
    }
    // SAFETY: Preserve the short circuit and once-per-32 clock cadence. C's
    // u64 local_clock result converts the signed tlimit to unsigned for comparison.
    unsafe { bindings::rusix_rcubatch_clock() >= tlimit as u64 }
}

/// # Safety
/// rdp is live initialized Tree RCU per-CPU state, or the test-only private
/// descriptor satisfying the same accessed-field contract. BH is disabled;
/// current context is softirq or its retained CPU-bound rcuc task. IRQ-save
/// sections serialize local enqueue/accounting; original GP/node ordering and
/// hotplug parking remain the caller's responsibility. Each ready callback has
/// valid links/function and returns with its required RCU callback context.
/// No NOCB/RT/BOOST configuration may select this implementation.
// SAFETY: Internal dispatch ABI preserves the original private rcu_data pointer
// through opaque C typing. No safe ownership or alternate-context API is exposed.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_rcu_do_batch(rdp: *mut c_void) {
    // Initialize self-relative tail only after the descriptor is pinned at its
    // final stack address. No allocation/fallible initializer or callback Drop.
    stack_pin_init!(let owned = Opaque::ffi_init(|list: *mut List| {
        // SAFETY: Exclusive unpublished final-address storage; selected list
        // constructor initializes the descriptor before any chain is transferred.
        unsafe { bindings::rcu_cblist_init(list) };
    }));
    let batch = owned.get();
    // SAFETY: rdp layout projection stays in C; returned canonical list pointer
    // is retained through commit but never becomes a Rust reference.
    let list = unsafe { bindings::rusix_rcubatch_cblist(rdp) };
    // SAFETY: All foreign field access below remains typed C/LKMM, with caller's
    // local-CPU/BH/GP lifetime contract. Local Rust arithmetic cannot panic.
    unsafe {
        if !bindings::rcu_segcblist_ready_cbs(list) {
            bindings::rusix_rcubatch_trace_start(rdp, 0);
            bindings::rusix_rcubatch_trace_end(rdp, 0, !bindings::rusix_rcubatch_empty(list));
            return;
        }

        let flags = bindings::rusix_rcubatch_irq_save(rdp);
        bindings::rusix_rcubatch_warn_offline();
        let pending = bindings::rcu_segcblist_get_seglen(list, bindings::RCU_DONE_TAIL as _);
        let div = bindings::rusix_rcubatch_divisor();
        // x86_64 C long is 64 bits (also asserted by the C adapter). The original
        // negative-divisor branch precedes its unsigned sizeof-derived comparison.
        let div = if div < 0 {
            7
        } else if div > 62 {
            62
        } else {
            div
        };
        let limit = bindings::rusix_rcubatch_blimit(rdp).max(pending.wrapping_shr(div as u32));
        let mut tlimit: c_long = 0;
        let mut jlimit: c_ulong = 0;
        let mut jlimit_check = false;
        if (bindings::rusix_rcubatch_in_softirq()
            || bindings::rusix_rcubatch_status(rdp) == RUNNING)
            && (DOUBLE_CHECK || limit > 100)
        {
            let rrn = bindings::rusix_rcubatch_resched_ns().clamp(NS_MSEC, NS_SEC);
            tlimit = bindings::rusix_rcubatch_clock().wrapping_add(rrn as u64) as c_long;
            jlimit = bindings::rusix_rcubatch_jiffies()
                .wrapping_add((rrn.wrapping_add(NPJ).wrapping_add(1) / NPJ) as c_ulong);
            jlimit_check = true;
        }
        bindings::rusix_rcubatch_trace_start(rdp, limit);
        // Total len stays positive while callbacks are detached/in flight so
        // rcu_barrier cannot mistake an empty main-list head for completed work.
        bindings::rcu_segcblist_extract_done_cbs(list, batch);
        // rcu_rdp_is_offloaded is constant false in the selected !NOCB mode.
        bindings::rusix_rcubatch_trace_dequeued(list);
        bindings::rusix_rcubatch_irq_restore(rdp, flags);

        bindings::rusix_rcubatch_tick_set();
        let mut count: c_long = 0;
        let mut head = bindings::rcu_cblist_dequeue(batch);
        while !head.is_null() {
            count = count.wrapping_add(1);
            bindings::rusix_rcubatch_debug_unqueue(head);
            bindings::rusix_rcubatch_lock_acquire();
            bindings::rusix_rcubatch_trace_invoke(head);
            // Snapshot precedes the debug callback hook exactly as in C.
            let callback = bindings::rusix_rcubatch_func(head).unwrap_unchecked();
            bindings::rusix_rcubatch_debug_callback(head);
            bindings::rusix_rcubatch_clear_func(head);
            callback(head);
            // No current-head read/write/projection after invocation. Only the
            // global lockdep map, rdp, local counters and remaining batch are used.
            bindings::rusix_rcubatch_lock_release();

            if bindings::rusix_rcubatch_in_softirq() {
                if count >= limit
                    && (bindings::rusix_rcubatch_need_resched()
                        || !bindings::rusix_rcubatch_idle_task())
                {
                    break;
                }
                if rusix_rcu_batch_check_time(count, tlimit, jlimit_check, jlimit) {
                    break;
                }
            } else {
                // Preserve the complete rcuc process-context sequence. !BOOST
                // does not remove this path: rcutree.use_softirq=0 selects it.
                bindings::rusix_rcubatch_bh_enable();
                bindings::rusix_rcubatch_assert_irqs_enabled_before();
                bindings::rusix_rcubatch_cond_resched();
                bindings::rusix_rcubatch_assert_irqs_enabled_after();
                bindings::rusix_rcubatch_bh_disable();
                if bindings::rusix_rcubatch_status(rdp) == RUNNING
                    && rusix_rcu_batch_check_time(count, tlimit, jlimit_check, jlimit)
                {
                    bindings::rusix_rcubatch_set_work(rdp, 1);
                    break;
                }
            }
            head = bindings::rcu_cblist_dequeue(batch);
        }

        let flags = bindings::rusix_rcubatch_irq_save(rdp);
        bindings::rusix_rcubatch_set_invoked(
            rdp,
            bindings::rusix_rcubatch_invoked(rdp).wrapping_add(count as c_ulong),
        );
        bindings::rusix_rcubatch_trace_end(
            rdp,
            count,
            bindings::rusix_rcubatch_local_nonempty(batch),
        );
        // Explicit commit: prepend every unconsumed DONE callback, then subtract
        // only the completed invocations from the original conservative total.
        bindings::rcu_segcblist_insert_done_cbs(list, batch);
        bindings::rcu_segcblist_add_len(list, count.wrapping_neg());
        let remaining = bindings::rusix_rcubatch_n_cbs(list);
        if bindings::rusix_rcubatch_blimit(rdp) >= MAX_BLIMIT
            && remaining <= bindings::rusix_rcubatch_qlowmark()
        {
            bindings::rusix_rcubatch_set_blimit(rdp, bindings::rusix_rcubatch_global_blimit());
        }
        if remaining == 0 && bindings::rusix_rcubatch_qlen(rdp) != 0 {
            bindings::rusix_rcubatch_set_qlen(rdp, 0);
            bindings::rusix_rcubatch_set_force_snap(rdp, bindings::rusix_rcubatch_force_qs());
        } else if remaining
            < bindings::rusix_rcubatch_qlen(rdp).wrapping_sub(bindings::rusix_rcubatch_qhimark())
        {
            bindings::rusix_rcubatch_set_qlen(rdp, remaining);
        }
        let empty = bindings::rusix_rcubatch_empty(list);
        bindings::rusix_rcubatch_warn_zero_nonempty(remaining == 0 && !empty);
        bindings::rusix_rcubatch_warn_nonzero_empty(remaining != 0 && empty);
        bindings::rusix_rcubatch_warn_zero_segments(
            remaining == 0 && bindings::rcu_segcblist_n_segment_cbs(list) != 0,
        );
        bindings::rusix_rcubatch_warn_nonempty_no_segments(
            !empty && bindings::rcu_segcblist_n_segment_cbs(list) == 0,
        );
        bindings::rusix_rcubatch_irq_restore(rdp, flags);
        bindings::rusix_rcubatch_tick_clear();
    }
}
