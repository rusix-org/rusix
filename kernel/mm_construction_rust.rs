// SPDX-License-Identifier: GPL-2.0-only
// Translation of kernel/fork.c, Copyright (C) 1991, 1992 Linus Torvalds.

//! Address-space construction sequencing over the canonical foreign layout.
//!
//! The descriptor is pinned in its slab; raw pointers encode construction stages,
//! not exclusive access to the whole mm. PGD and RSS counter initializers expose
//! parts to C observers before return. No safe Mm reference or generic destructor
//! can represent the partially copied input accepted by the shared initializer.

use core::ptr::null_mut;
use kernel::{
    bindings::{mm_struct, task_struct, user_namespace},
    ffi::{c_int, c_ulong},
};

unsafe extern "C" {
    static rusix_mm_mdwe_no_inherit: c_ulong;
    static rusix_mm_mdwe_clear: c_ulong;
    static rusix_mm_legacy_mask: c_ulong;
    static rusix_mm_def_mask: c_ulong;
    fn rusix_mm_slab_alloc() -> *mut mm_struct;
    fn rusix_mm_current_task() -> *mut task_struct;
    fn rusix_mm_current_user_ns() -> *mut user_namespace;
    fn rusix_mm_current_mm() -> *mut mm_struct;
    fn rusix_mm_owner_init(mm: *mut mm_struct, p: *mut task_struct);
    fn rusix_mm_flags_read(mm: *mut mm_struct) -> c_ulong;
    fn rusix_mm_def_read(mm: *mut mm_struct) -> c_ulong;
    fn rusix_mm_dump_filter() -> c_ulong;
    fn rusix_mm_flags_write(mm: *mut mm_struct, value: c_ulong);
    fn rusix_mm_def_write(mm: *mut mm_struct, value: c_ulong);
    fn rusix_mm_futex_init(mm: *mut mm_struct) -> c_int;
    fn rusix_mm_pgd_alloc(mm: *mut mm_struct) -> c_int;
    fn rusix_mm_id_alloc(mm: *mut mm_struct) -> c_int;
    fn rusix_mm_context_init(p: *mut task_struct, mm: *mut mm_struct) -> c_int;
    fn rusix_mm_cid_alloc(mm: *mut mm_struct, p: *mut task_struct) -> c_int;
    fn rusix_mm_rss_init(mm: *mut mm_struct) -> c_int;
    fn rusix_mm_user_ns_get(mm: *mut mm_struct, ns: *mut user_namespace);
    fn rusix_mm_tree_init(mm: *mut mm_struct);
    fn rusix_mm_refs_init(mm: *mut mm_struct);
    fn rusix_mm_write_seq_init(mm: *mut mm_struct);
    fn rusix_mm_mmap_lock_init(mm: *mut mm_struct);
    fn rusix_mm_mmlist_init(mm: *mut mm_struct);
    fn rusix_mm_pgtables_init(mm: *mut mm_struct);
    fn rusix_mm_counts_init(mm: *mut mm_struct);
    fn rusix_mm_rss_clear(mm: *mut mm_struct);
    fn rusix_mm_page_table_lock_init(mm: *mut mm_struct);
    fn rusix_mm_arg_lock_init(mm: *mut mm_struct);
    fn rusix_mm_cpumask_init(mm: *mut mm_struct);
    fn rusix_mm_aio_init(mm: *mut mm_struct);
    fn rusix_mm_pasid_init(mm: *mut mm_struct);
    fn rusix_mm_exe_clear(mm: *mut mm_struct);
    fn rusix_mm_notifiers_init(mm: *mut mm_struct);
    fn rusix_mm_tlb_pending_init(mm: *mut mm_struct);
    fn rusix_mm_huge_pmd_clear(mm: *mut mm_struct);
    fn rusix_mm_uprobes_init(mm: *mut mm_struct);
    fn rusix_mm_hugetlb_init(mm: *mut mm_struct);
    fn rusix_mm_flags_clear(mm: *mut mm_struct);
    fn rusix_mm_lru_init(mm: *mut mm_struct);
    fn rusix_mm_cid_destroy(mm: *mut mm_struct);
    fn rusix_mm_context_destroy(mm: *mut mm_struct);
    fn rusix_mm_id_free(mm: *mut mm_struct);
    fn rusix_mm_pgd_free(mm: *mut mm_struct);
    fn rusix_mm_futex_free(mm: *mut mm_struct);
    fn rusix_mm_slab_free(mm: *mut mm_struct);
    fn rusix_mm_zero_fresh(mm: *mut mm_struct);
}

/// Shared initializer for a zeroed fresh slab or dup_mm's copied descriptor.
///
/// # Safety
/// `mm` is the exact final-address allocation from mm_cachep. The caller has
/// either zeroed sizeof(*mm) or copied oldmm there; copied references and PGD are
/// not newly owned. `p` and `user_ns` remain live through the call, as current
/// or the constructing child and a namespace retained by current/oldmm. Context
/// permits the same GFP_KERNEL acquisitions as C (including early poking_init).
/// No other code may initialize these fields concurrently. Canonical subsystem
/// observers may access only the fields their initialization has published.
// SAFETY: One built-in definition; private fork.c shim declares this exact ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_mm_init(
    mm: *mut mm_struct,
    p: *mut task_struct,
    user_ns: *mut user_namespace,
) -> *mut mm_struct {
    // SAFETY: Final-address storage and retained caller pointers satisfy the
    // staged contract above. Every foreign access remains a canonical C operation;
    // no whole-struct references or snapshots cross PGD/counter publication.
    unsafe {
        rusix_mm_tree_init(mm);
        rusix_mm_refs_init(mm);
        rusix_mm_write_seq_init(mm);
        rusix_mm_mmap_lock_init(mm);
        rusix_mm_mmlist_init(mm);
        rusix_mm_pgtables_init(mm);
        rusix_mm_counts_init(mm);
        rusix_mm_rss_clear(mm);
        rusix_mm_page_table_lock_init(mm);
        rusix_mm_arg_lock_init(mm);
        rusix_mm_cpumask_init(mm);
        rusix_mm_aio_init(mm);
        rusix_mm_owner_init(mm, p);
        rusix_mm_pasid_init(mm);
        rusix_mm_exe_clear(mm);
        rusix_mm_notifiers_init(mm);
        rusix_mm_tlb_pending_init(mm);
        rusix_mm_huge_pmd_clear(mm);
        rusix_mm_uprobes_init(mm);
        rusix_mm_hugetlb_init(mm);
        rusix_mm_flags_clear(mm);
        // Baseline inherits from current->mm, which need not be p->mm.
        // Current's mm cannot be switched by another task during this call.
        let parent = rusix_mm_current_mm();
        if !parent.is_null() {
            let mut flags = rusix_mm_flags_read(parent);
            // mmf_init_legacy_flags: MDWE no-inherit clears both MDWE bits
            // before retaining the canonical legacy initialization mask.
            if flags & rusix_mm_mdwe_no_inherit != 0 {
                flags &= !rusix_mm_mdwe_clear;
            }
            rusix_mm_flags_write(mm, flags & rusix_mm_legacy_mask);
            rusix_mm_def_write(mm, rusix_mm_def_read(parent) & rusix_mm_def_mask);
        } else {
            rusix_mm_flags_write(mm, rusix_mm_dump_filter());
            rusix_mm_def_write(mm, 0);
        }

        if rusix_mm_futex_init(mm) != 0 {
            // Futex did not complete: no cleanup of copied resource pointers.
            rusix_mm_slab_free(mm);
            return null_mut();
        }
        if rusix_mm_pgd_alloc(mm) != 0 {
            // PGD allocator unwinds internally; copied/transient mm->pgd is
            // not ours to free after this failure.
            rusix_mm_futex_free(mm);
            rusix_mm_slab_free(mm);
            return null_mut();
        }
        if rusix_mm_id_alloc(mm) != 0 {
            rusix_mm_pgd_free(mm);
            rusix_mm_futex_free(mm);
            rusix_mm_slab_free(mm);
            return null_mut();
        }
        if rusix_mm_context_init(p, mm) != 0 {
            rusix_mm_id_free(mm);
            rusix_mm_pgd_free(mm);
            rusix_mm_futex_free(mm);
            rusix_mm_slab_free(mm);
            return null_mut();
        }
        if rusix_mm_cid_alloc(mm, p) != 0 {
            rusix_mm_context_destroy(mm);
            rusix_mm_id_free(mm);
            rusix_mm_pgd_free(mm);
            rusix_mm_futex_free(mm);
            rusix_mm_slab_free(mm);
            return null_mut();
        }
        if rusix_mm_rss_init(mm) != 0 {
            // Failed counter initialization owns no counters; no counter destroy.
            rusix_mm_cid_destroy(mm);
            rusix_mm_context_destroy(mm);
            rusix_mm_id_free(mm);
            rusix_mm_pgd_free(mm);
            rusix_mm_futex_free(mm);
            rusix_mm_slab_free(mm);
            return null_mut();
        }
        // Only successful construction acquires the namespace reference. It was
        // borrowed from current/oldmm on every preceding rollback path.
        rusix_mm_user_ns_get(mm, user_ns);
        rusix_mm_lru_init(mm);
        mm
    }
}

/// Allocate an empty initialized address space, also used by early text_poke_mm.
///
/// # Safety
/// Caller satisfies the original mm_alloc process/boot context and takes the
/// returned mm_users/mm_count lifetime, or handles NULL. Subsequent mapping,
/// task publication and mmput/mmdrop lifecycle stay with existing C callers.
// SAFETY: Kbuild selects one definition; fork.c retains its existing export site.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn mm_alloc() -> *mut mm_struct {
    // SAFETY: Canonical slab allocator supplies the variable-sized final storage.
    // Zero only the fixed prefix, as C; initializer sets trailing CPU masks.
    unsafe {
        let mm = rusix_mm_slab_alloc();
        if mm.is_null() {
            return null_mut();
        }
        rusix_mm_zero_fresh(mm);
        rusix_mm_init(mm, rusix_mm_current_task(), rusix_mm_current_user_ns())
    }
}
