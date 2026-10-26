// SPDX-License-Identifier: GPL-2.0-only
// Translation of kernel/fork.c, Copyright (C) 1991, 1992 Linus Torvalds.

//! Private, unpublished child construction transaction.
//!
//! Raw pointers represent staged ownership, never a live reference-counted Task.
//! C retains allocator/layout/architecture and subsystem primitives. All failure
//! paths return NULL, matching copy_process's preloaded -ENOMEM.

use core::ptr::null_mut;
use kernel::{bindings::task_struct, ffi::c_int};

unsafe extern "C" {
    static rusix_task_numa_no_node: c_int;
    fn rusix_task_fork_node(orig: *mut task_struct) -> c_int;
    fn rusix_task_alloc(node: c_int) -> *mut task_struct;
    fn rusix_task_arch_dup(tsk: *mut task_struct, orig: *mut task_struct) -> c_int;
    fn rusix_task_alloc_stack(tsk: *mut task_struct, node: c_int) -> c_int;
    fn rusix_task_scs(tsk: *mut task_struct, node: c_int) -> c_int;
    fn rusix_task_setup_stack(tsk: *mut task_struct, orig: *mut task_struct);
    fn rusix_task_cpus_are_owned(orig: *mut task_struct) -> bool;
    fn rusix_task_dup_user_cpus(
        tsk: *mut task_struct,
        orig: *mut task_struct,
        node: c_int,
    ) -> c_int;
    fn rusix_task_stack_refcount(tsk: *mut task_struct);
    fn rusix_task_account_stack(tsk: *mut task_struct);
    fn rusix_task_clear_seccomp(tsk: *mut task_struct);
    fn rusix_task_clear_notifier(tsk: *mut task_struct);
    fn rusix_task_clear_resched(tsk: *mut task_struct);
    fn rusix_task_stack_magic(tsk: *mut task_struct);
    fn rusix_task_clear_dispatch(tsk: *mut task_struct);
    fn rusix_task_canary(tsk: *mut task_struct);
    fn rusix_task_own_cpus(tsk: *mut task_struct);
    fn rusix_task_refs(tsk: *mut task_struct);
    fn rusix_task_btrace(tsk: *mut task_struct);
    fn rusix_task_clear_transients(tsk: *mut task_struct);
    fn rusix_task_kcov(tsk: *mut task_struct);
    fn rusix_task_kmsan(tsk: *mut task_struct);
    fn rusix_task_kmap(tsk: *mut task_struct);
    fn rusix_task_fault(tsk: *mut task_struct);
    fn rusix_task_blkcg(tsk: *mut task_struct);
    fn rusix_task_pasid(tsk: *mut task_struct);
    fn rusix_task_memcg(tsk: *mut task_struct);
    fn rusix_task_split_lock(tsk: *mut task_struct);
    fn rusix_task_mm_cid(tsk: *mut task_struct);
    fn rusix_task_bpf(tsk: *mut task_struct);
    fn rusix_task_unaccount_stack(tsk: *mut task_struct);
    fn rusix_task_free_stack(tsk: *mut task_struct);
    fn rusix_task_free_slab(tsk: *mut task_struct);
}

/// Called exclusively by fork.c's private constructor shim in copy_process.
///
/// # Safety
/// `orig` is current, remains alive throughout, and has the baseline fork caller's
/// sleeping/process context. The returned task is still unpublished and partially
/// initialized; only copy_process may continue construction or its staged cleanup.
// SAFETY: Exactly one built-in definition is selected; the C shim has this ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_dup_task_struct(
    orig: *mut task_struct,
    mut node: c_int,
) -> *mut task_struct {
    // SAFETY: The caller pins orig's lifetime. C performs the original accesses
    // (including parent affinity races) without creating Rust references. A slab
    // allocation belongs solely to this transaction until the final return.
    unsafe {
        if node == rusix_task_numa_no_node {
            node = rusix_task_fork_node(orig);
        }
        let tsk = rusix_task_alloc(node);
        if tsk.is_null() {
            return null_mut();
        }
        if rusix_task_arch_dup(tsk, orig) != 0 {
            // Slab only: architecture copy has not acquired any child resources.
            rusix_task_free_slab(tsk);
            return null_mut();
        }
        if rusix_task_alloc_stack(tsk, node) != 0 {
            // Copied stack pointers can STILL ALIAS THE PARENT. The allocator
            // cleans its own failed acquisitions; never free_task/stack here.
            rusix_task_free_slab(tsk);
            return null_mut();
        }
        // The child now owns its stack; initialize its refcount before accounting.
        rusix_task_stack_refcount(tsk);
        rusix_task_account_stack(tsk);
        if rusix_task_scs(tsk, node) != 0 {
            // Only this stage owns an accounted stack. Free encodes delayed RCU
            // reclamation before slab release; it cannot retain a task pointer.
            rusix_task_unaccount_stack(tsk);
            rusix_task_free_stack(tsk);
            rusix_task_free_slab(tsk);
            return null_mut();
        }
        // No later failure aborts this constructor. Seccomp must be detached
        // before later copy_process failure paths may invoke free_task.
        rusix_task_clear_seccomp(tsk);
        rusix_task_setup_stack(tsk, orig);
        rusix_task_clear_notifier(tsk);
        rusix_task_clear_resched(tsk);
        rusix_task_stack_magic(tsk);
        rusix_task_clear_dispatch(tsk);
        rusix_task_canary(tsk);
        if rusix_task_cpus_are_owned(orig) {
            rusix_task_own_cpus(tsk);
        }
        // Deliberately best effort, exactly as C: this clears the copied pointer
        // first and serializes optional affinity copying with orig->pi_lock.
        let _ = rusix_task_dup_user_cpus(tsk, orig, node);
        rusix_task_refs(tsk);
        rusix_task_btrace(tsk);
        rusix_task_clear_transients(tsk);
        rusix_task_kcov(tsk);
        rusix_task_kmsan(tsk);
        rusix_task_kmap(tsk);
        rusix_task_fault(tsk);
        rusix_task_blkcg(tsk);
        rusix_task_pasid(tsk);
        rusix_task_memcg(tsk);
        rusix_task_split_lock(tsk);
        rusix_task_mm_cid(tsk);
        rusix_task_bpf(tsk);
        // Ownership transfers to copy_process, not to a safe Task/ARef API.
        // FPU cloning, shared-resource acquisition and publication are still C.
        tsk
    }
}
