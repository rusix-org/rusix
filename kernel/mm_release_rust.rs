// SPDX-License-Identifier: GPL-2.0-only
// Translation of kernel/fork.c, Copyright (C) 1991, 1992 Linus Torvalds.

//! Two-stage MM release: final address-space user, then final storage reference.
//!
//! Foreign references and lazy-TLB users prevent exclusive whole-MM ownership.
//! All shared accesses, atomic ordering and subsystem destructors remain typed C
//! primitives. A raw pointer is consumed by each releasing entry point; no Rust
//! reference or generic Drop is constructed for the descriptor.

use kernel::bindings::{mm_struct, work_struct};

// The pinned bindgen MM/work types can reach GNU empty sched_statistics.
// The observed lint concerns that nested type, but all aggregates in this block
// cross only as raw pointers (including the callback's work_struct pointer).
// Scalar results are C bool or void; no foreign aggregate crosses by value or
// has its layout read by Rust. Keep this audited ABI exception local.
#[allow(improper_ctypes)]
unsafe extern "C" {
    fn rusix_mm_release_might_sleep();
    fn rusix_mm_release_users_dec(mm: *mut mm_struct) -> bool;
    fn rusix_mm_release_users_check(mm: *mut mm_struct);
    fn rusix_mm_release_uprobes(mm: *mut mm_struct);
    fn rusix_mm_release_aio(mm: *mut mm_struct);
    fn rusix_mm_release_ksm(mm: *mut mm_struct);
    fn rusix_mm_release_khugepaged(mm: *mut mm_struct);
    fn rusix_mm_release_mappings(mm: *mut mm_struct);
    fn rusix_mm_release_huge_zero(mm: *mut mm_struct);
    fn rusix_mm_release_exe(mm: *mut mm_struct);
    fn rusix_mm_release_list_empty(mm: *mut mm_struct) -> bool;
    fn rusix_mm_release_list_lock();
    fn rusix_mm_release_list_del(mm: *mut mm_struct);
    fn rusix_mm_release_list_unlock();
    fn rusix_mm_release_has_binfmt(mm: *mut mm_struct) -> bool;
    fn rusix_mm_release_binfmt_put(mm: *mut mm_struct);
    fn rusix_mm_release_lru(mm: *mut mm_struct);
    fn rusix_mm_release_count_drop(mm: *mut mm_struct);
    fn rusix_mm_release_work_init(
        mm: *mut mm_struct,
        callback: unsafe extern "C" fn(*mut work_struct),
    );
    fn rusix_mm_release_work_queue(mm: *mut mm_struct);
    fn rusix_mm_release_work_mm(work: *mut work_struct) -> *mut mm_struct;
    fn rusix_mm_release_init_check(mm: *mut mm_struct);
    fn rusix_mm_release_current_check(mm: *mut mm_struct);
    fn rusix_mm_release_lazy_tlbs(mm: *mut mm_struct);
    fn rusix_mm_release_active_check(mm: *mut mm_struct);
    fn rusix_mm_release_notifiers(mm: *mut mm_struct);
    fn rusix_mm_release_check(mm: *mut mm_struct);
    fn rusix_mm_release_user_ns(mm: *mut mm_struct);
    fn rusix_mm_release_pasid(mm: *mut mm_struct);
    fn rusix_mm_release_rss(mm: *mut mm_struct);
    // Existing constructor primitives, selected by the required construction
    // option. Each releases only its named resource, never the full transaction.
    fn rusix_mm_pgd_free(mm: *mut mm_struct);
    fn rusix_mm_id_free(mm: *mut mm_struct);
    fn rusix_mm_context_destroy(mm: *mut mm_struct);
    fn rusix_mm_cid_destroy(mm: *mut mm_struct);
    fn rusix_mm_futex_free(mm: *mut mm_struct);
    fn rusix_mm_slab_free(mm: *mut mm_struct);
}

/// Release mappings after the last users reference, retaining its implicit
/// storage reference until the final call. May sleep.
///
/// # Safety
/// `mm` is initialized, mm_users has reached zero and this caller owns that
/// unique transition. The implicit mm_count reference keeps the descriptor live.
unsafe fn release_users(mm: *mut mm_struct) {
    // SAFETY: The final users transition serializes teardown, but does not imply
    // exclusive access to the whole descriptor. C operations preserve original
    // synchronization with observers. Khugepaged must leave before exit_mmap.
    unsafe {
        rusix_mm_release_users_check(mm);
        rusix_mm_release_uprobes(mm);
        rusix_mm_release_aio(mm);
        rusix_mm_release_ksm(mm);
        rusix_mm_release_khugepaged(mm);
        rusix_mm_release_mappings(mm);
        rusix_mm_release_huge_zero(mm);
        rusix_mm_release_exe(mm);
        if !rusix_mm_release_list_empty(mm) {
            rusix_mm_release_list_lock();
            rusix_mm_release_list_del(mm);
            rusix_mm_release_list_unlock();
        }
        if rusix_mm_release_has_binfmt(mm) {
            rusix_mm_release_binfmt_put(mm);
        }
        rusix_mm_release_lru(mm);
        rusix_mm_futex_free(mm);
        // This is the original full-barrier mmdrop operation. It may immediately
        // invoke __mmdrop and free mm; no field or pointer use follows.
        rusix_mm_release_count_drop(mm);
    }
}

/// Consume one address-space user reference in sleepable context.
///
/// # Safety
/// Caller owns one mm_users reference to this initialized, non-null descriptor.
// SAFETY: Kconfig/Kbuild select one ABI definition; fork.c keeps its export site.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn mmput(mm: *mut mm_struct) {
    // SAFETY: The owned reference pins storage until the atomic operation. Only
    // the successful final transition may use mm afterward; might_sleep remains
    // unconditional, including the nonfinal-reference path.
    unsafe {
        rusix_mm_release_might_sleep();
        if rusix_mm_release_users_dec(mm) {
            release_users(mm);
        }
    }
}

/// Workqueue owns the final users transition and its implicit storage reference.
unsafe extern "C" fn mmput_async_fn(work: *mut work_struct) {
    // SAFETY: Only mmput_async installs this callback on initialized embedded
    // async_put_work. Its storage remains live until release_users drops the
    // implicit count. Workqueue callbacks may free their own work storage.
    unsafe {
        let mm = rusix_mm_release_work_mm(work);
        release_users(mm);
    }
}

/// Consume one users reference, deferring a final teardown to process context.
///
/// # Safety
/// Caller owns one mm_users reference; atomic/RCU context is permitted. The
/// unique zero transition owns async_put_work and transfers the implicit storage
/// reference to its queued callback. No caller access is permitted afterward.
// SAFETY: Kconfig/Kbuild select one ABI definition; fork.c keeps its export site.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn mmput_async(mm: *mut mm_struct) {
    // SAFETY: The original atomic decrement retains its LKMM ordering. On zero,
    // no final storage drop is possible before this transition releases its
    // implicit count. INIT_WORK and schedule_work retain their canonical C ABI.
    unsafe {
        if rusix_mm_release_users_dec(mm) {
            rusix_mm_release_work_init(mm, mmput_async_fn);
            rusix_mm_release_work_queue(mm);
        }
    }
}

/// Destroy MM storage after its final count transition.
///
/// # Safety
/// Caller owns the final mm_count transition, in a context valid for the
/// architecture destructor (on x86, not softirq). This may also be an unpublished
/// initialized MM whose exec stack setup failed: mm_users need not be zero.
// SAFETY: Kconfig/Kbuild select one ABI definition; fork.c keeps its export site.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn __mmdrop(mm: *mut mm_struct) {
    // SAFETY: Final count ownership excludes retained descriptor references.
    // Canonical lazy-TLB cleanup removes architecture users before PGD teardown.
    // Each subsystem still owns its own locking/RCU protocol; this sequence is
    // identical to C and makes no references into possibly shared fields.
    unsafe {
        rusix_mm_release_init_check(mm);
        rusix_mm_release_current_check(mm);
        rusix_mm_release_lazy_tlbs(mm);
        rusix_mm_release_active_check(mm);
        rusix_mm_pgd_free(mm);
        rusix_mm_id_free(mm);
        rusix_mm_context_destroy(mm);
        rusix_mm_release_notifiers(mm);
        rusix_mm_release_check(mm);
        rusix_mm_release_user_ns(mm);
        rusix_mm_release_pasid(mm);
        rusix_mm_cid_destroy(mm);
        rusix_mm_release_rss(mm);
        rusix_mm_slab_free(mm);
    }
}
