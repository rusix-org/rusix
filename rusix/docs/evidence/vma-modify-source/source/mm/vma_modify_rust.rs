// SPDX-License-Identifier: GPL-2.0-or-later
// VMA topology transactions translated from mm/vma.c, Linux 6.18.58.
//! Canonical C stack contexts remain at their final addresses. Rust owns the
//! modification, split and shared mutation protocol, without descriptor-wide
//! references. C merge/shrink callers enter the same selected protocol.
use core::ptr::null_mut;
use kernel::{
    bindings::{
        address_space, anon_vma, anon_vma_name, file, mempolicy, mm_struct, vm_area_struct,
        vm_operations_struct,
    },
    ffi::{c_int, c_uint, c_ulong, c_void},
};
type Open = unsafe extern "C" fn(*mut vm_area_struct);
type MaySplit = unsafe extern "C" fn(*mut vm_area_struct, c_ulong) -> c_int;
// Aggregate pointees may contain GNU empty structs. Only typed pointers, exact
// native scalars and nullable native callback pointers cross this private ABI.
#[allow(improper_ctypes)]
unsafe extern "C" {
    fn rusix_prep_vma(opaque: *mut c_void) -> *mut vm_area_struct;
    fn rusix_prep_set_vma(opaque: *mut c_void, value: *mut vm_area_struct);
    fn rusix_prep_adj_next(opaque: *mut c_void) -> *mut vm_area_struct;
    fn rusix_prep_set_adj_next(opaque: *mut c_void, value: *mut vm_area_struct);
    fn rusix_prep_file(opaque: *mut c_void) -> *mut file;
    fn rusix_prep_set_file(opaque: *mut c_void, value: *mut file);
    fn rusix_prep_mapping(opaque: *mut c_void) -> *mut address_space;
    fn rusix_prep_set_mapping(opaque: *mut c_void, value: *mut address_space);
    fn rusix_prep_anon_vma(opaque: *mut c_void) -> *mut anon_vma;
    fn rusix_prep_set_anon_vma(opaque: *mut c_void, value: *mut anon_vma);
    fn rusix_prep_insert(opaque: *mut c_void) -> *mut vm_area_struct;
    fn rusix_prep_set_insert(opaque: *mut c_void, value: *mut vm_area_struct);
    fn rusix_prep_remove(opaque: *mut c_void) -> *mut vm_area_struct;
    fn rusix_prep_set_remove(opaque: *mut c_void, value: *mut vm_area_struct);
    fn rusix_prep_remove2(opaque: *mut c_void) -> *mut vm_area_struct;
    fn rusix_prep_set_remove2(opaque: *mut c_void, value: *mut vm_area_struct);
    fn rusix_prep_skip_vma_uprobe(opaque: *mut c_void) -> bool;
    fn rusix_prep_set_skip_vma_uprobe(opaque: *mut c_void, value: bool);
    fn rusix_prep_zero(opaque: *mut c_void);
    fn rusix_modify_middle(opaque: *mut c_void) -> *mut vm_area_struct;
    fn rusix_modify_next(opaque: *mut c_void) -> *mut vm_area_struct;
    fn rusix_modify_remove_middle(opaque: *mut c_void) -> bool;
    fn rusix_modify_remove_next(opaque: *mut c_void) -> bool;
    fn rusix_modify_adjust_middle_start(opaque: *mut c_void) -> bool;
    fn rusix_modify_adjust_next_start(opaque: *mut c_void) -> bool;
    fn rusix_modify_skip_vma_uprobe(opaque: *mut c_void) -> bool;
    fn rusix_modify_give_up_on_oom(opaque: *mut c_void) -> bool;
    fn rusix_modify_start(opaque: *mut c_void) -> c_ulong;
    fn rusix_modify_end(opaque: *mut c_void) -> c_ulong;
    fn rusix_modify_vmi(opaque: *mut c_void) -> *mut c_void;
    fn rusix_modify_set_vm_flags(opaque: *mut c_void, value: c_ulong);
    fn rusix_modify_set_anon_name(opaque: *mut c_void, value: *mut anon_vma_name);
    fn rusix_modify_set_policy(opaque: *mut c_void, value: *mut mempolicy);
    fn rusix_modify_set_give_up_on_oom(opaque: *mut c_void, value: bool);
    fn rusix_modify_set_uffd(opaque: *mut c_void, context: *const c_void);
    fn rusix_modify_nomem(opaque: *mut c_void) -> bool;
    fn rusix_modify_merged(opaque: *mut c_void) -> bool;
    fn rusix_modify_merge(opaque: *mut c_void) -> *mut vm_area_struct;
    fn rusix_modify_error(error: c_int) -> *mut vm_area_struct;
    fn rusix_modify_is_error(vma: *mut vm_area_struct) -> bool;
    fn rusix_modify_mm(vma: *mut vm_area_struct) -> *mut mm_struct;
    fn rusix_modify_flags(vma: *mut vm_area_struct) -> c_ulong;
    fn rusix_modify_set_start(vma: *mut vm_area_struct, value: c_ulong);
    fn rusix_modify_set_end(vma: *mut vm_area_struct, value: c_ulong);
    fn rusix_modify_set_pgoff(vma: *mut vm_area_struct, value: c_ulong);
    fn rusix_modify_max_map_count() -> c_int;
    fn rusix_modify_may_split(ops: *const vm_operations_struct) -> Option<MaySplit>;
    fn rusix_modify_split(
        iter: *mut c_void,
        vma: *mut vm_area_struct,
        addr: c_ulong,
        new_below: c_int,
    ) -> c_int;
    fn rusix_modify_iter_free(iter: *mut c_void);
    fn rusix_modify_iter_next(iter: *mut c_void);
    fn rusix_modify_prev(iter: *mut c_void);
    fn rusix_modify_adjust_huge(vma: *mut vm_area_struct, start: c_ulong, end: c_ulong);
    fn rusix_modify_is_hugetlb(vma: *mut vm_area_struct) -> bool;
    fn rusix_modify_hugetlb_split(vma: *mut vm_area_struct, addr: c_ulong);
    fn rusix_modify_uprobe_unmap(vma: *mut vm_area_struct, start: c_ulong, end: c_ulong);
    fn rusix_modify_uprobe_map(vma: *mut vm_area_struct);
    fn rusix_modify_anon_lock(anon: *mut anon_vma);
    fn rusix_modify_anon_unlock(anon: *mut anon_vma);
    fn rusix_modify_anon_pre(vma: *mut vm_area_struct);
    fn rusix_modify_anon_post(vma: *mut vm_area_struct);
    fn rusix_modify_interval_remove(vma: *mut vm_area_struct, mapping: *mut address_space);
    fn rusix_modify_unmap_writable(mapping: *mut address_space);
    fn rusix_modify_store_new(iter: *mut c_void, vma: *mut vm_area_struct);
    fn rusix_modify_detach(vma: *mut vm_area_struct);
    fn rusix_modify_anon_merge(vma: *mut vm_area_struct, remove: *mut vm_area_struct);
    fn rusix_modify_warn_start(condition: bool);
    fn rusix_modify_warn_end(condition: bool);
    fn rusix_modify_warn_anon(condition: bool);
    fn rusix_modify_warn_oom(condition: bool);
    fn rusix_modify_warn_removed_end(condition: bool);
    static rusix_copy_page_shift: c_uint;
    static rusix_copy_enomem: c_int;
    fn rusix_copy_start(vma: *mut vm_area_struct) -> c_ulong;
    fn rusix_copy_end(vma: *mut vm_area_struct) -> c_ulong;
    fn rusix_copy_pgoff(vma: *mut vm_area_struct) -> c_ulong;
    fn rusix_copy_anon(vma: *mut vm_area_struct) -> *mut anon_vma;
    fn rusix_copy_dup_policy(old: *mut vm_area_struct, new_vma: *mut vm_area_struct) -> c_int;
    fn rusix_copy_clone_anon(new_vma: *mut vm_area_struct, old: *mut vm_area_struct) -> c_int;
    fn rusix_copy_get_file(file: *mut file);
    fn rusix_copy_open(ops: *const vm_operations_struct) -> Option<Open>;
    fn rusix_link_config(iter: *mut c_void, start: c_ulong, end: c_ulong);
    fn rusix_link_prealloc(iter: *mut c_void, vma: *mut vm_area_struct) -> c_int;
    fn rusix_link_start_write(vma: *mut vm_area_struct);
    fn rusix_link_count(mm: *mut mm_struct) -> c_int;
    fn rusix_link_set_count(mm: *mut mm_struct, count: c_int);
    fn rusix_link_validate(mm: *mut mm_struct);
    fn rusix_link_mapping(file: *mut file) -> *mut address_space;
    fn rusix_link_mapping_lock(mapping: *mut address_space);
    fn rusix_link_mapping_unlock(mapping: *mut address_space);
    fn rusix_link_shared_maywrite(vma: *mut vm_area_struct) -> bool;
    fn rusix_link_dcache_lock(mapping: *mut address_space);
    fn rusix_link_dcache_unlock(mapping: *mut address_space);
    fn rusix_link_interval_insert(vma: *mut vm_area_struct, mapping: *mut address_space);
    fn rusix_vma_link_file_locked(vma: *mut vm_area_struct, mapping: *mut address_space);
    fn rusix_remove_file(vma: *mut vm_area_struct) -> *mut file;
    fn rusix_remove_ops(vma: *mut vm_area_struct) -> *const vm_operations_struct;
    fn rusix_remove_fput(file: *mut file);
    fn rusix_remove_policy(vma: *mut vm_area_struct);
    fn vm_area_dup(vma: *mut vm_area_struct) -> *mut vm_area_struct;
    fn vm_area_free(vma: *mut vm_area_struct);
}

/// Initialize the canonical native preparation context for split/merge/shrink.
/// # Safety
/// `prep` is writable, final-address C vma_prepare storage. VMA and optional
/// merge context remain live under the caller's mmap write lock; this operation
/// neither publishes the context nor acquires new references to its borrowed data.
// SAFETY: Unique selected definition; exact C pointer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_init_multi_vma_prep(
    prep: *mut c_void,
    vma: *mut vm_area_struct,
    merge: *mut c_void,
) {
    // SAFETY: Context is caller-local and disjoint from descriptors. Foreign
    // fields are accessed individually, preserving the native lock/lifetime scope.
    unsafe {
        rusix_prep_zero(prep);
        rusix_prep_set_vma(prep, vma);
        rusix_prep_set_anon_vma(prep, rusix_copy_anon(vma));
        let mut remove_second = false;
        if !merge.is_null() && rusix_modify_remove_middle(merge) {
            rusix_prep_set_remove(prep, rusix_modify_middle(merge));
            remove_second = true;
        }
        if !merge.is_null() && rusix_modify_remove_next(merge) {
            let next = rusix_modify_next(merge);
            if remove_second {
                rusix_prep_set_remove2(prep, next);
            } else {
                rusix_prep_set_remove(prep, next);
            }
        }
        let adjust = if !merge.is_null() && rusix_modify_adjust_middle_start(merge) {
            rusix_modify_middle(merge)
        } else if !merge.is_null() && rusix_modify_adjust_next_start(merge) {
            rusix_modify_next(merge)
        } else {
            null_mut()
        };
        rusix_prep_set_adj_next(prep, adjust);
        if rusix_prep_anon_vma(prep).is_null() && !adjust.is_null() {
            rusix_prep_set_anon_vma(prep, rusix_copy_anon(adjust));
        }
        rusix_modify_warn_anon(
            !rusix_prep_anon_vma(prep).is_null()
                && !adjust.is_null()
                && !rusix_copy_anon(adjust).is_null()
                && rusix_prep_anon_vma(prep) != rusix_copy_anon(adjust),
        );
        rusix_prep_set_file(prep, rusix_remove_file(vma));
        if !rusix_prep_file(prep).is_null() {
            rusix_prep_set_mapping(prep, rusix_link_mapping(rusix_remove_file(vma)));
        }
        if !merge.is_null() && rusix_modify_skip_vma_uprobe(merge) {
            rusix_prep_set_skip_vma_uprobe(prep, true);
        }
    }
}

/// Initialize a split/shrink preparation context without merge state.
/// # Safety
/// Same native storage, lifetime and mmap-write conditions as multi initialization.
// SAFETY: Exact selected C bridge ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_init_vma_prep(prep: *mut c_void, vma: *mut vm_area_struct) {
    // SAFETY: Null merge is the native initialization variant; other inputs valid.
    unsafe { rusix_init_multi_vma_prep(prep, vma, null_mut()) }
}

/// Notify probes and lock/remove interval entries before VMA range mutation.
/// # Safety
/// Initialized caller-local preparation context and all its borrowed objects live
/// under mmap write exclusion. Caller has write-locked each VMA being modified.
/// Must pair with complete after the native range/maple update; may sleep.
// SAFETY: Exact selected C bridge ABI, including calls from native merge/shrink.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_vma_prepare(prep: *mut c_void) {
    // SAFETY: Individual accesses introduce no references spanning callbacks or
    // locks. Order matches native uprobe -> mapping -> anon -> dcache protocol.
    unsafe {
        if !rusix_prep_file(prep).is_null() {
            let vma = rusix_prep_vma(prep);
            rusix_modify_uprobe_unmap(vma, rusix_copy_start(vma), rusix_copy_end(vma));
            let adj = rusix_prep_adj_next(prep);
            if !adj.is_null() {
                rusix_modify_uprobe_unmap(adj, rusix_copy_start(adj), rusix_copy_end(adj));
            }
            rusix_link_mapping_lock(rusix_prep_mapping(prep));
            let insert = rusix_prep_insert(prep);
            if !insert.is_null() && !rusix_remove_file(insert).is_null() {
                rusix_vma_link_file_locked(insert, rusix_link_mapping(rusix_remove_file(insert)));
            }
        }
        if !rusix_prep_anon_vma(prep).is_null() {
            rusix_modify_anon_lock(rusix_prep_anon_vma(prep));
            rusix_modify_anon_pre(rusix_prep_vma(prep));
            if !rusix_prep_adj_next(prep).is_null() {
                rusix_modify_anon_pre(rusix_prep_adj_next(prep));
            }
        }
        if !rusix_prep_file(prep).is_null() {
            rusix_link_dcache_lock(rusix_prep_mapping(prep));
            rusix_modify_interval_remove(rusix_prep_vma(prep), rusix_prep_mapping(prep));
            if !rusix_prep_adj_next(prep).is_null() {
                rusix_modify_interval_remove(rusix_prep_adj_next(prep), rusix_prep_mapping(prep));
            }
        }
    }
}

/// Unlink the shared-file interval while the caller holds mapping write exclusion.
/// # Safety
/// Native VMA/mapping remain live, with the same locked preconditions as
/// __remove_shared_vm_struct; the interval is currently published in this mapping.
unsafe fn remove_shared(vma: *mut vm_area_struct, mapping: *mut address_space) {
    // SAFETY: Locked caller owns this removal; accounting precedes interval removal.
    unsafe {
        if rusix_link_shared_maywrite(vma) {
            rusix_modify_unmap_writable(mapping);
        }
        rusix_link_dcache_lock(mapping);
        rusix_modify_interval_remove(vma, mapping);
        rusix_link_dcache_unlock(mapping);
    }
}

/// Publish changed ranges, release interval locks and retire consumed descriptors.
/// # Safety
/// Matching prepare completed; caller performed the native maple/range mutation.
/// The context, iterator and mm remain live. Removal descriptors have native
/// merge ownership; insertion has preallocated maple storage. May free removals.
// SAFETY: Exact selected C bridge ABI for split, merge and shrink callers.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_vma_complete(
    prep: *mut c_void,
    iter: *mut c_void,
    mm: *mut mm_struct,
) {
    // SAFETY: Follow native publication/unlock order. No reference spans tree
    // publication, anon merging or fput. Freed removal pointers are never read.
    unsafe {
        if !rusix_prep_file(prep).is_null() {
            if !rusix_prep_adj_next(prep).is_null() {
                rusix_link_interval_insert(rusix_prep_adj_next(prep), rusix_prep_mapping(prep));
            }
            rusix_link_interval_insert(rusix_prep_vma(prep), rusix_prep_mapping(prep));
            rusix_link_dcache_unlock(rusix_prep_mapping(prep));
        }
        if !rusix_prep_remove(prep).is_null() && !rusix_prep_file(prep).is_null() {
            remove_shared(rusix_prep_remove(prep), rusix_prep_mapping(prep));
            if !rusix_prep_remove2(prep).is_null() {
                remove_shared(rusix_prep_remove2(prep), rusix_prep_mapping(prep));
            }
        } else if !rusix_prep_insert(prep).is_null() {
            rusix_modify_store_new(iter, rusix_prep_insert(prep));
            rusix_link_set_count(mm, rusix_link_count(mm).wrapping_add(1));
        }
        if !rusix_prep_anon_vma(prep).is_null() {
            rusix_modify_anon_post(rusix_prep_vma(prep));
            if !rusix_prep_adj_next(prep).is_null() {
                rusix_modify_anon_post(rusix_prep_adj_next(prep));
            }
            rusix_modify_anon_unlock(rusix_prep_anon_vma(prep));
        }
        if !rusix_prep_file(prep).is_null() {
            rusix_link_mapping_unlock(rusix_prep_mapping(prep));
            if !rusix_prep_skip_vma_uprobe(prep) {
                rusix_modify_uprobe_map(rusix_prep_vma(prep));
                if !rusix_prep_adj_next(prep).is_null() {
                    rusix_modify_uprobe_map(rusix_prep_adj_next(prep));
                }
            }
        }
        if !rusix_prep_remove(prep).is_null() {
            loop {
                rusix_modify_detach(rusix_prep_remove(prep));
                if !rusix_prep_file(prep).is_null() {
                    let remove = rusix_prep_remove(prep);
                    rusix_modify_uprobe_unmap(
                        remove,
                        rusix_copy_start(remove),
                        rusix_copy_end(remove),
                    );
                    rusix_remove_fput(rusix_prep_file(prep));
                }
                if !rusix_copy_anon(rusix_prep_remove(prep)).is_null() {
                    rusix_modify_anon_merge(rusix_prep_vma(prep), rusix_prep_remove(prep));
                }
                rusix_link_set_count(mm, rusix_link_count(mm).wrapping_sub(1));
                rusix_remove_policy(rusix_prep_remove(prep));
                if rusix_prep_remove2(prep).is_null() {
                    rusix_modify_warn_removed_end(
                        rusix_copy_end(rusix_prep_vma(prep))
                            < rusix_copy_end(rusix_prep_remove(prep)),
                    );
                }
                // Native merge retirement does NOT call vm_ops.close.
                vm_area_free(rusix_prep_remove(prep));
                if rusix_prep_remove2(prep).is_null() {
                    break;
                }
                rusix_prep_set_remove(prep, rusix_prep_remove2(prep));
                rusix_prep_set_remove2(prep, null_mut());
            }
        }
        if !rusix_prep_insert(prep).is_null() && !rusix_prep_file(prep).is_null() {
            rusix_modify_uprobe_map(rusix_prep_insert(prep));
        }
    }
}

/// Split without the public map-count check, as required by native munmap.
/// # Safety
/// Caller holds mmap write lock, has a valid iterator positioned on live VMA and
/// supplies a strictly interior page-aligned address. `prep` is uninitialized
/// final-address native vma_prepare storage, disjoint from all other inputs.
// SAFETY: The native __split_vma entry supplies exactly this private pointer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_split_vma_inner(
    iter: *mut c_void,
    vma: *mut vm_area_struct,
    addr: c_ulong,
    new_below: c_int,
    prep: *mut c_void,
) -> c_int {
    // SAFETY: mmap exclusion protects source/iterator; detached duplicate ownership
    // permits range writes. Stages release only acquired resources, with native
    // clone failure already unwinding partial anon chains. Open is a callback
    // boundary; subsequent accesses are fresh and hold no descriptor references.
    unsafe {
        rusix_modify_warn_start(rusix_copy_start(vma) >= addr);
        rusix_modify_warn_end(rusix_copy_end(vma) <= addr);
        let ops = rusix_remove_ops(vma);
        if !ops.is_null() {
            if let Some(may_split) = rusix_modify_may_split(ops) {
                let err = may_split(vma, addr);
                if err != 0 {
                    return err;
                }
            }
        }
        let new_vma = vm_area_dup(vma);
        if new_vma.is_null() {
            return rusix_copy_enomem;
        }
        if new_below != 0 {
            rusix_modify_set_end(new_vma, addr);
        } else {
            rusix_modify_set_start(new_vma, addr);
            rusix_modify_set_pgoff(
                new_vma,
                rusix_copy_pgoff(new_vma).wrapping_add(
                    addr.wrapping_sub(rusix_copy_start(vma))
                        .wrapping_shr(rusix_copy_page_shift),
                ),
            );
        }
        rusix_link_config(iter, rusix_copy_start(new_vma), rusix_copy_end(new_vma));
        if rusix_link_prealloc(iter, new_vma) != 0 {
            vm_area_free(new_vma);
            return rusix_copy_enomem;
        }
        let err = rusix_copy_dup_policy(vma, new_vma);
        if err != 0 {
            rusix_modify_iter_free(iter);
            vm_area_free(new_vma);
            return err;
        }
        let err = rusix_copy_clone_anon(new_vma, vma);
        if err != 0 {
            rusix_remove_policy(new_vma);
            rusix_modify_iter_free(iter);
            vm_area_free(new_vma);
            return err;
        }
        let file = rusix_remove_file(new_vma);
        if !file.is_null() {
            rusix_copy_get_file(file);
        }
        let ops = rusix_remove_ops(new_vma);
        if !ops.is_null() {
            if let Some(open) = rusix_copy_open(ops) {
                open(new_vma);
            }
        }
        rusix_link_start_write(vma);
        rusix_link_start_write(new_vma);
        rusix_init_vma_prep(prep, vma);
        rusix_prep_set_insert(prep, new_vma);
        rusix_vma_prepare(prep);
        rusix_modify_adjust_huge(vma, rusix_copy_start(vma), addr);
        if rusix_modify_is_hugetlb(vma) {
            rusix_modify_hugetlb_split(vma, addr);
        }
        if new_below != 0 {
            rusix_modify_set_start(vma, addr);
            rusix_modify_set_pgoff(
                vma,
                rusix_copy_pgoff(vma).wrapping_add(
                    addr.wrapping_sub(rusix_copy_start(new_vma))
                        .wrapping_shr(rusix_copy_page_shift),
                ),
            );
        } else {
            rusix_modify_set_end(vma, addr);
        }
        rusix_vma_complete(prep, iter, rusix_modify_mm(vma));
        rusix_link_validate(rusix_modify_mm(vma));
        if new_below != 0 {
            rusix_modify_iter_next(iter);
        } else {
            rusix_modify_prev(iter);
        }
        0
    }
}

/// Public checked split, preserving the separate unchecked munmap entry.
/// # Safety
/// Native split preconditions as above; caller owns live mmap-locked MM/VMA/iterator.
// SAFETY: Replaces the guarded public C definition, with its native scalar ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn split_vma(
    iter: *mut c_void,
    vma: *mut vm_area_struct,
    addr: c_ulong,
    new_below: c_int,
) -> c_int {
    // SAFETY: Map count belongs to the same mmap-locked MM; the native unchecked
    // wrapper creates final-address preparation storage only after admission.
    unsafe {
        if rusix_link_count(rusix_modify_mm(vma)) >= rusix_modify_max_map_count() {
            return rusix_copy_enomem;
        }
        rusix_modify_split(iter, vma, addr, new_below)
    }
}

/// Prepare a requested range, preserving partial topology on later split failure.
/// # Safety
/// Canonical merge context satisfies vma_merge_existing_range's mmap write,
/// iterator/range and adjacent-VMA contracts; merge may consume original VMAs.
unsafe fn modify(merge: *mut c_void) -> *mut vm_area_struct {
    // SAFETY: Save only native pre-merge values. Successful merge returns before
    // any old VMA dereference. Failed merge leaves the original live; first split
    // success is deliberately retained if the trailing split then fails.
    unsafe {
        let vma = rusix_modify_middle(merge);
        let start = rusix_modify_start(merge);
        let end = rusix_modify_end(merge);
        let merged = rusix_modify_merge(merge);
        if !merged.is_null() {
            return merged;
        }
        if rusix_modify_nomem(merge) {
            return rusix_modify_error(rusix_copy_enomem);
        }
        rusix_modify_warn_oom(
            rusix_modify_give_up_on_oom(merge)
                && (rusix_copy_start(vma) != start || rusix_copy_end(vma) != end),
        );
        if rusix_copy_start(vma) < start {
            let err = split_vma(rusix_modify_vmi(merge), vma, start, 1);
            if err != 0 {
                return rusix_modify_error(err);
            }
        }
        if rusix_copy_end(vma) > end {
            let err = split_vma(rusix_modify_vmi(merge), vma, end, 0);
            if err != 0 {
                return rusix_modify_error(err);
            }
        }
        vma
    }
}

/// Prepare a flags range and preserve sticky flags on successful merge.
/// # Safety
/// Native wrapper supplies live canonical context; flags is a writable caller
/// scalar, disjoint from context/descriptors, retained through all native calls.
// SAFETY: Exact selected private pointer/scalar bridge ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_vma_modify_flags(
    merge: *mut c_void,
    flags: *mut c_ulong,
) -> *mut vm_area_struct {
    // SAFETY: Only local flags storage is dereferenced; selected VMA is read only
    // after successful topology preparation, not through a stale original pointer.
    unsafe {
        let requested = flags.read();
        rusix_modify_set_vm_flags(merge, requested);
        let ret = modify(merge);
        if rusix_modify_is_error(ret) {
            return ret;
        }
        if rusix_modify_merged(merge) {
            flags.write(rusix_modify_flags(ret));
        }
        ret
    }
}

/// Prepare an anonymous-name range without applying the caller's actual update.
/// # Safety
/// Native wrapper supplies initialized canonical context and borrowed name under
/// mmap write exclusion; caller retains the name through the transaction.
// SAFETY: Exact selected C bridge ABI; no Rust layout assumptions for the name.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_vma_modify_name(
    merge: *mut c_void,
    name: *mut anon_vma_name,
) -> *mut vm_area_struct {
    // SAFETY: Canonical context stores a borrowed pointer for native merge matching.
    unsafe {
        rusix_modify_set_anon_name(merge, name);
        modify(merge)
    }
}

/// Prepare a policy range without applying the caller's actual policy update.
/// # Safety
/// Canonical context and borrowed policy remain live under native mmap exclusion.
// SAFETY: Exact selected C bridge ABI; no Rust mempolicy layout assumptions.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_vma_modify_policy(
    merge: *mut c_void,
    policy: *mut mempolicy,
) -> *mut vm_area_struct {
    // SAFETY: Only the canonical context's borrowed policy field is changed.
    unsafe {
        rusix_modify_set_policy(merge, policy);
        modify(merge)
    }
}

/// Prepare a flags/userfaultfd range with the original best-effort merge flag.
/// # Safety
/// Native wrapper supplies canonical merge and config-dependent uffd context
/// storage, both retained through return under the original mmap write contract.
// SAFETY: Pointer-only uffd bridge avoids passing an empty/config-dependent aggregate.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_vma_modify_flags_uffd(
    merge: *mut c_void,
    flags: c_ulong,
    context: *const c_void,
    give_up_on_oom: bool,
) -> *mut vm_area_struct {
    // SAFETY: Native copy handles canonical uffd layout; pointers remain borrowed.
    unsafe {
        rusix_modify_set_vm_flags(merge, flags);
        rusix_modify_set_uffd(merge, context);
        if give_up_on_oom {
            rusix_modify_set_give_up_on_oom(merge, true);
        }
        modify(merge)
    }
}
