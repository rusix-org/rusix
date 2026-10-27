// SPDX-License-Identifier: GPL-2.0-only
// Translation of kernel/fork.c, Copyright (C) 1991, 1992 Linus Torvalds.

//! Fork MM sharing/duplication transaction over canonical foreign storage.
//!
//! Copied descriptor pointers are borrowed until the relevant initialization
//! succeeds. PGD/counter observers and shared-MM clones prohibit whole-MM Rust
//! references. C retains dup_mmap and its partial maple-tree unwind contract.

use core::ptr::null_mut;
use kernel::{
    bindings::{mm_struct, task_struct, user_namespace},
    error::code::ENOMEM,
    ffi::c_int,
};

// task_struct contains GNU empty structs with SCHEDSTATS=n. Every aggregate
// here crosses only as a raw pointer; C retains the canonical typed prototypes.
// No foreign aggregate layout or by-value aggregate is used by this Rust policy.
#[allow(improper_ctypes)]
unsafe extern "C" {
    static rusix_mm_copy_clone_vm: u64;
    fn rusix_mm_copy_descriptor(mm: *mut mm_struct, oldmm: *mut mm_struct);
    fn rusix_mm_copy_user_ns(mm: *mut mm_struct) -> *mut user_namespace;
    fn rusix_mm_copy_uprobe_start();
    fn rusix_mm_copy_uprobe_end();
    fn rusix_mm_copy_mappings(mm: *mut mm_struct, oldmm: *mut mm_struct) -> c_int;
    fn rusix_mm_copy_hiwater(mm: *mut mm_struct);
    fn rusix_mm_copy_binfmt_get(mm: *mut mm_struct) -> bool;
    fn rusix_mm_copy_binfmt_clear(mm: *mut mm_struct);
    fn rusix_mm_copy_task_counters(tsk: *mut task_struct);
    fn rusix_mm_copy_task_mm(tsk: *mut task_struct, mm: *mut mm_struct);
    fn rusix_mm_copy_users_get(mm: *mut mm_struct);
    fn rusix_mm_copy_cid_fork(tsk: *mut task_struct);
    // Required existing constructor/release primitives: no duplicated ABI or
    // safe ownership wrapper for partially initialized/copied descriptors.
    fn rusix_mm_slab_alloc() -> *mut mm_struct;
    fn rusix_mm_current_mm() -> *mut mm_struct;
    fn rusix_mm_init(
        mm: *mut mm_struct,
        p: *mut task_struct,
        user_ns: *mut user_namespace,
    ) -> *mut mm_struct;
    fn rusix_mm_owner_init(mm: *mut mm_struct, p: *mut task_struct);
    fn rusix_mm_release_has_binfmt(mm: *mut mm_struct) -> bool;
    fn mmput(mm: *mut mm_struct);
}

/// Duplicate current's retained MM for an unpublished child, or return null.
///
/// # Safety
/// `tsk` is the private child under construction. `oldmm` is current's live MM;
/// caller context permits the original sleepable allocation and mapping copy.
/// The same inherited namespace/binfmt and dup_mmap synchronization contracts
/// as pinned C apply. No owner is inferred merely from copying a pointer.
unsafe fn dup_mm(tsk: *mut task_struct, oldmm: *mut mm_struct) -> *mut mm_struct {
    // SAFETY: Fresh slab storage is initially owned only as an allocation. The
    // fixed descriptor copy inherits borrowed resources; mm_init resets its
    // fields, acquires new resources in stages and frees the slab on failure.
    unsafe {
        let mm = rusix_mm_slab_alloc();
        if mm.is_null() {
            return null_mut();
        }
        rusix_mm_copy_descriptor(mm, oldmm);
        if rusix_mm_init(mm, tsk, rusix_mm_copy_user_ns(mm)).is_null() {
            // mm_init already unwound its acquired resources and freed mm.
            return null_mut();
        }

        rusix_mm_copy_uprobe_start();
        let err = rusix_mm_copy_mappings(mm, oldmm);
        if err == 0 {
            rusix_mm_copy_uprobe_end();
            rusix_mm_copy_hiwater(mm);
            // The inherited binfmt pointer has not yet acquired its module ref.
            // Keep the baseline short-circuit; NULL needs no module operation.
            if !rusix_mm_release_has_binfmt(mm) || rusix_mm_copy_binfmt_get(mm) {
                return mm;
            }
        }

        // No module reference was acquired. Clear that borrowed pointer before
        // mmput; the selected teardown handles partial dup_mmap sentinels. Never
        // free copied parent VMAs or perform another constructor-stage unwind.
        rusix_mm_copy_binfmt_clear(mm);
        rusix_mm_owner_init(mm, null_mut());
        mmput(mm);
        // mm may be freed now. Only the independent uprobe lock remains ours
        // when dup_mmap failed; a later module-get failure already unlocked it.
        if err != 0 {
            rusix_mm_copy_uprobe_end();
        }
        null_mut()
    }
}

/// Attach a shared or duplicated MM to a child during copy_process.
///
/// # Safety
/// `tsk` is the live unpublished child from task construction, with exclusive
/// initialization rights to these task fields. Current retains its MM during
/// this operation. After success, copy_process owns the child's users reference
/// and must pass it to the child or its existing bad_fork_cleanup_mm path.
// SAFETY: The selected private C copy_mm shim declares this exact u64/task* ABI;
// Kbuild selects one bridge definition, with no change to public kernel exports.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_copy_mm(clone_flags: u64, tsk: *mut task_struct) -> c_int {
    // SAFETY: All foreign accesses use canonical C primitives, retaining plain
    // field semantics and the original mmget/LKMM boundary. This never makes a
    // whole-task or whole-MM reference, including the shared CLONE_VM path.
    unsafe {
        rusix_mm_copy_task_counters(tsk);
        rusix_mm_copy_task_mm(tsk, null_mut());
        let oldmm = rusix_mm_current_mm();
        if oldmm.is_null() {
            // Kernel thread: lazy active_mm acquisition remains scheduler work.
            return 0;
        }
        let mm = if clone_flags & rusix_mm_copy_clone_vm != 0 {
            rusix_mm_copy_users_get(oldmm);
            oldmm
        } else {
            // Preserve C's second current->mm evaluation on the copying path.
            let mm = dup_mm(tsk, rusix_mm_current_mm());
            if mm.is_null() {
                return ENOMEM.to_errno();
            }
            mm
        };
        rusix_mm_copy_task_mm(tsk, mm);
        rusix_mm_copy_cid_fork(tsk);
        0
    }
}
