// SPDX-License-Identifier: GPL-2.0-or-later
// Copy/link policies translated from mm/vma.c, Linux 6.18.58.
//! Native C callers retain mmap/i_mmap locking and final-address iterator/merge
//! context storage. No descriptor-wide references or Rust layout overlays exist.
use core::ptr::null_mut;
use kernel::{
    bindings::{address_space, anon_vma, file, mm_struct, vm_area_struct, vm_operations_struct},
    ffi::{c_int, c_uint, c_ulong, c_void},
};
type Open = unsafe extern "C" fn(*mut vm_area_struct);
// Generated pointees may contain GNU empty structs. Only typed raw pointers,
// native scalar values and the exact nullable void(VMA*) callback cross this ABI.
#[allow(improper_ctypes)]
unsafe extern "C" {
    static rusix_copy_page_shift: c_uint;
    static rusix_copy_enomem: c_int;
    fn rusix_copy_source(opaque: *mut c_void) -> *mut vm_area_struct;
    fn rusix_copy_mm(opaque: *mut c_void) -> *mut mm_struct;
    fn rusix_copy_source_start(opaque: *mut c_void) -> c_ulong;
    fn rusix_copy_start(vma: *mut vm_area_struct) -> c_ulong;
    fn rusix_copy_end(vma: *mut vm_area_struct) -> c_ulong;
    fn rusix_copy_pgoff(vma: *mut vm_area_struct) -> c_ulong;
    fn rusix_copy_anonymous(vma: *mut vm_area_struct) -> bool;
    fn rusix_copy_anon(vma: *mut vm_area_struct) -> *mut anon_vma;
    fn rusix_copy_skip_uprobe(opaque: *mut c_void);
    fn rusix_copy_find_prev(opaque: *mut c_void, addr: c_ulong) -> *mut vm_area_struct;
    fn rusix_copy_set_pgoff(opaque: *mut c_void, pgoff: c_ulong);
    fn rusix_copy_next_rewind(opaque: *mut c_void) -> *mut vm_area_struct;
    fn rusix_copy_set_next(opaque: *mut c_void, vma: *mut vm_area_struct);
    fn rusix_copy_set_prev(opaque: *mut c_void, vma: *mut vm_area_struct);
    fn rusix_copy_prev(opaque: *mut c_void) -> *mut vm_area_struct;
    fn rusix_copy_next(opaque: *mut c_void) -> *mut vm_area_struct;
    fn rusix_copy_merge(opaque: *mut c_void) -> *mut vm_area_struct;
    fn rusix_copy_merge_bug(faulted: bool, vma: *mut vm_area_struct);
    fn rusix_copy_set_range(vma: *mut vm_area_struct, start: c_ulong, end: c_ulong, pgoff: c_ulong);
    fn rusix_copy_dup_policy(old: *mut vm_area_struct, new_vma: *mut vm_area_struct) -> c_int;
    fn rusix_copy_clone_anon(new_vma: *mut vm_area_struct, old: *mut vm_area_struct) -> c_int;
    fn rusix_copy_get_file(file: *mut file);
    fn rusix_copy_open(ops: *const vm_operations_struct) -> Option<Open>;
    fn rusix_copy_fixup_huge(vma: *mut vm_area_struct);
    fn rusix_copy_unlink_anon(vma: *mut vm_area_struct);
    fn rusix_link_config(iter: *mut c_void, start: c_ulong, end: c_ulong);
    fn rusix_link_prealloc(iter: *mut c_void, vma: *mut vm_area_struct) -> c_int;
    fn rusix_link_start_write(vma: *mut vm_area_struct);
    fn rusix_link_store(iter: *mut c_void, vma: *mut vm_area_struct);
    fn rusix_link_count(mm: *mut mm_struct) -> c_int;
    fn rusix_link_set_count(mm: *mut mm_struct, count: c_int);
    fn rusix_link_validate(mm: *mut mm_struct);
    fn rusix_link_mapping(file: *mut file) -> *mut address_space;
    fn rusix_link_mapping_lock(mapping: *mut address_space);
    fn rusix_link_mapping_unlock(mapping: *mut address_space);
    fn rusix_link_shared_maywrite(vma: *mut vm_area_struct) -> bool;
    fn rusix_link_allow_writable(mapping: *mut address_space);
    fn rusix_link_dcache_lock(mapping: *mut address_space);
    fn rusix_link_dcache_unlock(mapping: *mut address_space);
    fn rusix_link_interval_insert(vma: *mut vm_area_struct, mapping: *mut address_space);
    fn rusix_remove_file(vma: *mut vm_area_struct) -> *mut file;
    fn rusix_remove_ops(vma: *mut vm_area_struct) -> *const vm_operations_struct;
    fn rusix_remove_fput(file: *mut file);
    fn rusix_remove_policy(vma: *mut vm_area_struct);
    fn rusix_vma_close(vma: *mut vm_area_struct);
    fn vm_area_dup(vma: *mut vm_area_struct) -> *mut vm_area_struct;
    fn vm_area_free(vma: *mut vm_area_struct);
    fn vma_link(mm: *mut mm_struct, vma: *mut vm_area_struct) -> c_int;
}

/// Insert a VMA into the already locked file mapping.
/// # Safety
/// Caller retains VMA/mapping, holds the mapping write lock and satisfies native
/// rmap publication rules. vma_prepare calls this with that lock already held.
// SAFETY: Unique selected definition, exact C bridge pointer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_vma_link_file_locked(
    vma: *mut vm_area_struct,
    mapping: *mut address_space,
) {
    // SAFETY: Caller-held lock serializes native mapping accounting/tree writes;
    // dcache lock ordering is exactly the original locked operation.
    unsafe {
        if rusix_link_shared_maywrite(vma) {
            rusix_link_allow_writable(mapping);
        }
        rusix_link_dcache_lock(mapping);
        rusix_link_interval_insert(vma, mapping);
        rusix_link_dcache_unlock(mapping);
    }
}

/// Link the optional file mapping, acquiring its write lock.
/// # Safety
/// VMA fields/file remain live under the native caller's mmap write/VMA locking
/// contract. Caller must not already hold the mapping lock (use locked entry).
// SAFETY: Replaces only the guarded C definition, with the unchanged pointer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn vma_link_file(vma: *mut vm_area_struct) {
    // SAFETY: File and mapping lifetime follows the VMA's acquired file reference.
    unsafe {
        let file = rusix_remove_file(vma);
        if !file.is_null() {
            let mapping = rusix_link_mapping(file);
            rusix_link_mapping_lock(mapping);
            rusix_vma_link_file_locked(vma, mapping);
            rusix_link_mapping_unlock(mapping);
        }
    }
}

/// Publish a detached descriptor into its MM and optional file mapping.
/// # Safety
/// C entry owns a final-address initialized iterator for this MM through return;
/// caller holds mmap write lock and owns the unpublished VMA/resource references.
// SAFETY: Exact bridge ABI; no new allocation beyond native maple preallocation.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_vma_link(
    mm: *mut mm_struct,
    vma: *mut vm_area_struct,
    iter: *mut c_void,
) -> c_int {
    // SAFETY: Native synchronization permits these field accesses/publication.
    // Once stored, rmap observers may see the descriptor: no exclusive references.
    unsafe {
        rusix_link_config(iter, rusix_copy_start(vma), rusix_copy_end(vma));
        if rusix_link_prealloc(iter, vma) != 0 {
            return rusix_copy_enomem;
        }
        rusix_link_start_write(vma);
        rusix_link_store(iter, vma);
        vma_link_file(vma);
        rusix_link_set_count(mm, rusix_link_count(mm).wrapping_add(1));
        rusix_link_validate(mm);
        0
    }
}

/// Copy or merge a VMA for mremap, retaining the original staged ownership rules.
/// # Safety
/// C entry supplies its live final-address iterator/VMG context; caller holds
/// mmap write and source VMA locks. vmap/need_rmap_locks are live writable caller
/// locals, disjoint from descriptors/context, retained through this call. Native
/// callbacks may mutate fields but retain the descriptor; merge may consume the
/// original source, so only the saved start is used before possible rebinding.
// SAFETY: Selected C bridge declares exactly these scalar/raw-pointer arguments.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_copy_vma(
    ctx: *mut c_void,
    vmap: *mut *mut vm_area_struct,
    addr: c_ulong,
    len: c_ulong,
    mut pgoff: c_ulong,
    need_rmap_locks: *mut bool,
    keep_source: bool,
) -> *mut vm_area_struct {
    // SAFETY: Every native accessor/subsystem call has the original caller's
    // locking/lifetime context. Raw output writes touch only its local outputs.
    // Rollback releases acquired resources only, never borrowed copied pointers.
    unsafe {
        let mut vma = rusix_copy_source(ctx);
        let mm = rusix_copy_mm(ctx);
        let saved_start = rusix_copy_source_start(ctx);
        let end = addr.wrapping_add(len);
        let mut faulted = true;
        if rusix_copy_anonymous(vma) && rusix_copy_anon(vma).is_null() {
            // PAGE_SHIFT is the canonical x86_64 value, below unsigned-long width.
            pgoff = addr.wrapping_shr(rusix_copy_page_shift);
            faulted = false;
        }
        if !rusix_remove_file(vma).is_null() {
            rusix_copy_skip_uprobe(ctx);
        }
        let found = rusix_copy_find_prev(ctx, addr);
        if !found.is_null() && rusix_copy_start(found) < end {
            return null_mut();
        }
        rusix_copy_set_pgoff(ctx, pgoff);
        rusix_copy_set_next(ctx, rusix_copy_next_rewind(ctx));
        if !faulted && keep_source {
            if rusix_copy_prev(ctx) == vma {
                rusix_copy_set_prev(ctx, null_mut());
            }
            if rusix_copy_next(ctx) == vma {
                rusix_copy_set_next(ctx, null_mut());
            }
            faulted = true;
        }
        let merged = rusix_copy_merge(ctx);
        if !merged.is_null() {
            if saved_start >= rusix_copy_start(merged) && saved_start < rusix_copy_end(merged) {
                rusix_copy_merge_bug(faulted, merged);
                vma = merged;
                vmap.write(merged);
            }
            need_rmap_locks.write(rusix_copy_pgoff(merged) <= rusix_copy_pgoff(vma));
            return merged;
        }
        let new_vma = vm_area_dup(vma);
        if new_vma.is_null() {
            return null_mut();
        }
        rusix_copy_set_range(new_vma, addr, end, pgoff);
        if rusix_copy_dup_policy(vma, new_vma) != 0 {
            vm_area_free(new_vma);
            return null_mut();
        }
        if rusix_copy_clone_anon(new_vma, vma) != 0 {
            // Native clone failure already unlinks any partial anon chains.
            rusix_remove_policy(new_vma);
            vm_area_free(new_vma);
            return null_mut();
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
        // Open may alter fields: link and unwind use fresh native accesses.
        if vma_link(mm, new_vma) != 0 {
            rusix_copy_fixup_huge(new_vma);
            rusix_vma_close(new_vma);
            let file = rusix_remove_file(new_vma);
            if !file.is_null() {
                rusix_remove_fput(file);
            }
            rusix_copy_unlink_anon(new_vma);
            rusix_remove_policy(new_vma);
            vm_area_free(new_vma);
            return null_mut();
        }
        need_rmap_locks.write(false);
        new_vma
    }
}
