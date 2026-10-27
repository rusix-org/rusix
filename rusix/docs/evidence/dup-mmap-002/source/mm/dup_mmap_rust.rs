// SPDX-License-Identifier: GPL-2.0-only
// Translation of mm/mmap.c: written by obz; address-space accounting
// attribution retained to <alan@lxorguk.ukuu.org.uk>.

//! Complete mapping duplication policy; canonical C primitives retain foreign
//! field accesses, maple storage, subsystem locking and page-table operations.
//! The C entry owns address-stable iterator/userfault list storage until return.

use core::ptr::null_mut;
use kernel::{
    bindings::{address_space, file, mm_struct, vm_area_struct},
    error::code::{EINTR, ENOMEM},
    ffi::{c_int, c_ulong, c_void},
};

// MM and related bindgen pointees can reach GNU empty sched_statistics, as
// observed in the release build. This block passes aggregate types only through
// raw pointers, including the opaque context; values are c_int/c_ulong/bool.
// Rust neither passes foreign aggregates by value nor reads their layout.
// Keep the pointer-only ABI exception local to these reviewed declarations.
#[allow(improper_ctypes)]
unsafe extern "C" {
    static rusix_dup_dontcopy: c_ulong;
    static rusix_dup_account: c_ulong;
    static rusix_dup_wipeonfork: c_ulong;
    fn rusix_dup_lock_parent(mm: *mut mm_struct) -> c_int;
    fn rusix_dup_cache_parent(mm: *mut mm_struct);
    fn rusix_dup_uprobes(oldmm: *mut mm_struct, mm: *mut mm_struct);
    fn rusix_dup_lock_child(mm: *mut mm_struct);
    fn rusix_dup_exe(mm: *mut mm_struct, oldmm: *mut mm_struct);
    fn rusix_dup_vm_counters(mm: *mut mm_struct, oldmm: *mut mm_struct);
    fn rusix_dup_tree(mm: *mut mm_struct, oldmm: *mut mm_struct) -> c_int;
    fn rusix_dup_rcu_clear(ctx: *mut c_void);
    fn rusix_dup_rcu_set(ctx: *mut c_void);
    fn rusix_dup_next(ctx: *mut c_void) -> *mut vm_area_struct;
    fn rusix_dup_vma_write(vma: *mut vm_area_struct);
    fn rusix_dup_flags(vma: *mut vm_area_struct) -> c_ulong;
    fn rusix_dup_clear_range(ctx: *mut c_void, vma: *mut vm_area_struct) -> c_int;
    fn rusix_dup_subtract_stats(mm: *mut mm_struct, vma: *mut vm_area_struct);
    fn rusix_dup_fatal() -> bool;
    fn rusix_dup_pages(vma: *mut vm_area_struct) -> c_ulong;
    fn rusix_dup_charge(oldmm: *mut mm_struct, len: c_ulong) -> c_int;
    fn rusix_dup_vma(vma: *mut vm_area_struct) -> *mut vm_area_struct;
    fn rusix_dup_policy(old: *mut vm_area_struct, new: *mut vm_area_struct) -> c_int;
    fn rusix_dup_vma_mm(vma: *mut vm_area_struct, mm: *mut mm_struct);
    fn rusix_dup_userfault(ctx: *mut c_void, vma: *mut vm_area_struct) -> c_int;
    fn rusix_dup_anon_clear(vma: *mut vm_area_struct);
    fn rusix_dup_anon(new: *mut vm_area_struct, old: *mut vm_area_struct) -> c_int;
    fn rusix_dup_locked_clear(vma: *mut vm_area_struct);
    fn rusix_dup_is_hugetlb(vma: *mut vm_area_struct) -> bool;
    fn rusix_dup_hugetlb(vma: *mut vm_area_struct);
    fn rusix_dup_store(ctx: *mut c_void, vma: *mut vm_area_struct);
    fn rusix_dup_map_count(mm: *mut mm_struct);
    fn rusix_dup_has_open(vma: *mut vm_area_struct) -> bool;
    fn rusix_dup_open(vma: *mut vm_area_struct);
    fn rusix_dup_file(vma: *mut vm_area_struct) -> *mut file;
    fn rusix_dup_mapping(file: *mut file) -> *mut address_space;
    fn rusix_dup_file_get(file: *mut file);
    fn rusix_dup_mapping_lock(mapping: *mut address_space);
    fn rusix_dup_shared_write(vma: *mut vm_area_struct) -> bool;
    fn rusix_dup_mapping_writable(mapping: *mut address_space);
    fn rusix_dup_dcache_lock(mapping: *mut address_space);
    fn rusix_dup_interval_insert(
        new: *mut vm_area_struct,
        old: *mut vm_area_struct,
        mapping: *mut address_space,
    );
    fn rusix_dup_dcache_unlock(mapping: *mut address_space);
    fn rusix_dup_mapping_unlock(mapping: *mut address_space);
    fn rusix_dup_page_range(new: *mut vm_area_struct, old: *mut vm_area_struct) -> c_int;
    fn rusix_dup_arch(oldmm: *mut mm_struct, mm: *mut mm_struct) -> c_int;
    fn rusix_dup_iter_free(ctx: *mut c_void);
    fn rusix_dup_ksm(mm: *mut mm_struct, oldmm: *mut mm_struct);
    fn rusix_dup_khugepaged(mm: *mut mm_struct, oldmm: *mut mm_struct);
    fn rusix_dup_sentinel(ctx: *mut c_void, vma: *mut vm_area_struct);
    fn rusix_dup_oom_skip(mm: *mut mm_struct);
    fn rusix_dup_unstable(mm: *mut mm_struct);
    fn rusix_dup_unlock(mm: *mut mm_struct);
    fn rusix_dup_tlb_parent(mm: *mut mm_struct);
    fn rusix_dup_userfault_complete(ctx: *mut c_void);
    fn rusix_dup_userfault_fail(ctx: *mut c_void);
    fn rusix_dup_policy_put(vma: *mut vm_area_struct);
    fn rusix_dup_vma_free(vma: *mut vm_area_struct);
    fn rusix_dup_uncharge(charge: c_ulong);
}

/// Undo only detached per-VMA acquisitions, never a committed tree entry.
///
/// # Safety
/// `tmp` is null or a live detached allocation. `policy` means vma_dup_policy
/// succeeded and its reference needs putting. Charge has not been transferred
/// into a committed child's VM_ACCOUNT VMA. Subsystems unwind their own failures.
unsafe fn allocation_failure(tmp: *mut vm_area_struct, policy: bool, charge: c_ulong) -> c_int {
    // SAFETY: The caller describes exactly the reached acquisition stage; do
    // not put a policy that failed duplication, or unmap a borrowed parent VMA.
    unsafe {
        if !tmp.is_null() {
            if policy {
                rusix_dup_policy_put(tmp);
            }
            rusix_dup_vma_free(tmp);
        }
        rusix_dup_uncharge(charge);
        ENOMEM.to_errno()
    }
}

/// Duplicate an MM's mappings using the caller-owned final-address C context.
///
/// # Safety
/// `ctx` points to the entry wrapper's live canonical iterator and userfault
/// list, initialized for `mm` and not moved during this call. `oldmm` is current's
/// retained parent MM; `mm` has completed mm_init with an empty compatible tree.
/// The outer dup_mm caller holds the uprobe duplication lock and owns eventual
/// mmput on failure. This may sleep. No pointer or context reference escapes.
// SAFETY: The selected C entry declares this exact pointer ABI; Kbuild provides
// one Rust definition. The opaque context is only forwarded to typed C helpers.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_dup_mmap(
    mm: *mut mm_struct,
    oldmm: *mut mm_struct,
    ctx: *mut c_void,
) -> c_int {
    // SAFETY: The outer lifetime contract pins both descriptors. Every shared
    // field access stays in C with its original synchronization; acquiring the
    // mmap locks never creates a whole-MM/VMA Rust reference or ownership claim.
    unsafe {
        if rusix_dup_lock_parent(oldmm) != 0 {
            return EINTR.to_errno();
        }
        rusix_dup_cache_parent(oldmm);
        rusix_dup_uprobes(oldmm, mm);
        rusix_dup_lock_child(mm);
        rusix_dup_exe(mm, oldmm);
        rusix_dup_vm_counters(mm, oldmm);
        let mut retval = rusix_dup_tree(mm, oldmm);
        if retval == 0 {
            // __mt_dup copied tree nodes but its entries still borrow parent
            // VMAs. Only successful per-VMA stores replace those pointers.
            rusix_dup_rcu_clear(ctx);
            let mut mpnt;
            loop {
                mpnt = rusix_dup_next(ctx);
                if mpnt.is_null() {
                    retval = rusix_dup_arch(oldmm, mm);
                    break;
                }
                rusix_dup_vma_write(mpnt);
                if rusix_dup_flags(mpnt) & rusix_dup_dontcopy != 0 {
                    retval = rusix_dup_clear_range(ctx, mpnt);
                    if retval != 0 {
                        break;
                    }
                    rusix_dup_subtract_stats(mm, mpnt);
                    continue;
                }
                // This reset belongs AFTER the DONTCOPY branch. A failure in
                // that branch must never uncharge a previously committed VMA.
                let mut charge = 0;
                if rusix_dup_fatal() {
                    retval = EINTR.to_errno();
                    break;
                }
                if rusix_dup_flags(mpnt) & rusix_dup_account != 0 {
                    let len = rusix_dup_pages(mpnt);
                    if rusix_dup_charge(oldmm, len) != 0 {
                        retval = allocation_failure(null_mut(), false, charge);
                        break;
                    }
                    charge = len;
                }
                let tmp = rusix_dup_vma(mpnt);
                if tmp.is_null() {
                    retval = allocation_failure(null_mut(), false, charge);
                    break;
                }
                retval = rusix_dup_policy(mpnt, tmp);
                if retval != 0 {
                    retval = allocation_failure(tmp, false, charge);
                    break;
                }
                rusix_dup_vma_mm(tmp, mm);
                retval = rusix_dup_userfault(ctx, tmp);
                if retval != 0 {
                    retval = allocation_failure(tmp, true, charge);
                    break;
                }
                if rusix_dup_flags(tmp) & rusix_dup_wipeonfork != 0 {
                    rusix_dup_anon_clear(tmp);
                } else if rusix_dup_anon(tmp, mpnt) != 0 {
                    retval = allocation_failure(tmp, true, charge);
                    break;
                }
                rusix_dup_locked_clear(tmp);
                if rusix_dup_is_hugetlb(tmp) {
                    rusix_dup_hugetlb(tmp);
                }
                // Canonical insertion cannot require allocation after __mt_dup.
                // Preserve the ignored C return rather than invent an unwind.
                rusix_dup_store(ctx, tmp);
                rusix_dup_map_count(mm);
                if rusix_dup_has_open(tmp) {
                    rusix_dup_open(tmp);
                }
                let file = rusix_dup_file(tmp);
                if !file.is_null() {
                    let mapping = rusix_dup_mapping(file);
                    rusix_dup_file_get(file);
                    rusix_dup_mapping_lock(mapping);
                    if rusix_dup_shared_write(tmp) {
                        rusix_dup_mapping_writable(mapping);
                    }
                    rusix_dup_dcache_lock(mapping);
                    rusix_dup_interval_insert(tmp, mpnt, mapping);
                    rusix_dup_dcache_unlock(mapping);
                    rusix_dup_mapping_unlock(mapping);
                }
                // WIPEONFORK retains the successful userfault result (zero).
                if rusix_dup_flags(tmp) & rusix_dup_wipeonfork == 0 {
                    retval = rusix_dup_page_range(tmp, mpnt);
                }
                if retval != 0 {
                    // tmp is committed: mmput must clean it, even when page
                    // copying failed. Sentinel starts at the NEXT borrowed VMA.
                    mpnt = rusix_dup_next(ctx);
                    break;
                }
            }
            rusix_dup_iter_free(ctx);
            if retval == 0 {
                rusix_dup_rcu_set(ctx);
                rusix_dup_ksm(mm, oldmm);
                rusix_dup_khugepaged(mm, oldmm);
            } else {
                if !mpnt.is_null() {
                    rusix_dup_sentinel(ctx, mpnt);
                    rusix_dup_oom_skip(mm);
                }
                rusix_dup_unstable(mm);
            }
        }
        // __mt_dup failure reaches this epilogue directly, without iter_free,
        // marker insertion or unstable marking, exactly as the original goto.
        rusix_dup_unlock(mm);
        rusix_dup_tlb_parent(oldmm);
        rusix_dup_unlock(oldmm);
        if retval == 0 {
            rusix_dup_userfault_complete(ctx);
        } else {
            rusix_dup_userfault_fail(ctx);
        }
        retval
    }
}
