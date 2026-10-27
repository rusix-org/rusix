// SPDX-License-Identifier: GPL-2.0-only
// Mapping teardown translated from mm/mmap.c (written by obz; address-space
// accounting <alan@lxorguk.ukuu.org.uk>), mm/vma.c and mm/internal.h.

//! Complete mapping teardown and descriptor close policy. Foreign storage stays
//! behind typed C operations: final MM users do not imply exclusive access by
//! notifier, OOM, rmap or lockless VMA observers. No whole-MM/VMA references exist.

use kernel::{
    bindings::{file, mm_struct, vm_area_struct, vm_operations_struct},
    ffi::{c_int, c_ulong, c_void},
};

type Close = unsafe extern "C" fn(*mut vm_area_struct);

// These generated pointees can transitively contain GNU empty structures, as
// observed in the MM release build. All aggregate values cross this ABI only as
// raw pointers; scalar values are native unsigned long/int/bool, and Close is
// the exact nullable C void (*)(struct vm_area_struct *) callback ABI.
#[allow(improper_ctypes)]
unsafe extern "C" {
    static rusix_exit_account: c_ulong;
    fn rusix_exit_notifier(mm: *mut mm_struct);
    fn rusix_exit_read_lock(mm: *mut mm_struct);
    fn rusix_exit_arch(mm: *mut mm_struct);
    fn rusix_exit_next(ctx: *mut c_void) -> *mut vm_area_struct;
    fn rusix_exit_is_zero(vma: *mut vm_area_struct) -> bool;
    fn rusix_exit_read_unlock(mm: *mut mm_struct);
    fn rusix_exit_write_lock(mm: *mut mm_struct);
    fn rusix_exit_cache(mm: *mut mm_struct);
    fn rusix_exit_gather(ctx: *mut c_void, mm: *mut mm_struct);
    fn rusix_exit_unmap(ctx: *mut c_void, vma: *mut vm_area_struct);
    fn rusix_exit_oom_skip(mm: *mut mm_struct);
    fn rusix_exit_clear_rcu(mm: *mut mm_struct);
    fn rusix_exit_end(vma: *mut vm_area_struct) -> c_ulong;
    fn rusix_exit_iter_set(ctx: *mut c_void, end: c_ulong);
    fn rusix_exit_free_pgtables(ctx: *mut c_void, vma: *mut vm_area_struct);
    fn rusix_exit_finish(ctx: *mut c_void);
    fn rusix_exit_flags(vma: *mut vm_area_struct) -> c_ulong;
    fn rusix_exit_pages(vma: *mut vm_area_struct) -> c_ulong;
    fn rusix_exit_detach(vma: *mut vm_area_struct);
    fn rusix_exit_resched();
    fn rusix_exit_map_count(mm: *mut mm_struct) -> c_int;
    fn rusix_exit_count_bug(mismatch: bool);
    fn rusix_exit_trace(mm: *mut mm_struct);
    fn rusix_exit_destroy(mm: *mut mm_struct);
    fn rusix_exit_write_unlock(mm: *mut mm_struct);
    fn rusix_exit_unaccount(pages: c_ulong);
    fn rusix_remove_might_sleep();
    fn rusix_remove_ops(vma: *mut vm_area_struct) -> *const vm_operations_struct;
    fn rusix_remove_close(ops: *const vm_operations_struct) -> Option<Close>;
    fn rusix_remove_dummy(vma: *mut vm_area_struct);
    fn rusix_remove_file(vma: *mut vm_area_struct) -> *mut file;
    fn rusix_remove_fput(file: *mut file);
    fn rusix_remove_policy(vma: *mut vm_area_struct);
    fn vm_area_free(vma: *mut vm_area_struct);
}

/// Close a descriptor's hook once and invalidate further hooks if called.
///
/// # Safety
/// Caller retains the descriptor and its ops/file/module lifetimes, serializes
/// changes to its hooks, and supplies the callback's required context. The close
/// hook may change fields but must leave the descriptor live for dummy reset and
/// the caller's subsequent resource cleanup, as required by the C inline API.
// SAFETY: The conditional C bridge and Rust removal path call this policy;
// the exported symbol has exactly the bridge's declared pointer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_vma_close(vma: *mut vm_area_struct) {
    // SAFETY: Accessors retain canonical C field semantics under the original
    // caller's exclusion. No ops field is read after the close hook returns.
    unsafe {
        let ops = rusix_remove_ops(vma);
        if !ops.is_null() {
            if let Some(close) = rusix_remove_close(ops) {
                close(vma);
                rusix_remove_dummy(vma);
            }
        }
    }
}

/// Release one removed VMA and its descriptor-owned resources.
///
/// # Safety
/// Caller has completed the original unmap/rmap and reader-exclusion protocol
/// required on its path and retains the descriptor through close. File/policy
/// references belong to this descriptor. Context permits sleeping. After this
/// function no caller may dereference the old descriptor, even if its address
/// immediately becomes a new RCU-typesafe slab object.
// SAFETY: vma.c excludes its original definition only for this selected object;
// existing remove_vma declarations and all callers retain the same ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn remove_vma(vma: *mut vm_area_struct) {
    // SAFETY: Fields/resources are inspected only before their release. The
    // callback can mutate them: file and policy are read freshly AFTER close.
    unsafe {
        rusix_remove_might_sleep();
        rusix_vma_close(vma);
        let file = rusix_remove_file(vma);
        if !file.is_null() {
            rusix_remove_fput(file);
        }
        rusix_remove_policy(vma);
        vm_area_free(vma);
        // Descriptor may be reclaimed/reused; do not access it again.
    }
}

/// Tear down the complete mapping tree at the final MM-user transition.
///
/// # Safety
/// The existing exit_mmap caller owns final-user teardown and retains MM storage
/// through its implicit mm_count (including failed-construction cleanup). `ctx`
/// is the original synchronous C entry's final-address iterator and uninitialized
/// gather storage, valid until return. It is never moved or retained. Native
/// primitives retain exclusion against concurrent notifier/OOM/rmap/RCU readers;
/// this contract grants no exclusive reference to the complete MM or any VMA.
// SAFETY: mmap.c selects the context-only C entry and this unique Rust bridge
// together. Its opaque context pointer ABI matches that local C declaration.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_exit_mmap(mm: *mut mm_struct, ctx: *mut c_void) {
    // SAFETY: Each phase mirrors the original lock/lifetime protocol. The gather
    // is touched only after init on the nonempty path. All traversal/field access
    // stays in C primitives; XA_ZERO_ENTRY is checked before descriptor access.
    unsafe {
        let mut nr_accounted: c_ulong = 0;
        rusix_exit_notifier(mm);
        rusix_exit_read_lock(mm);
        rusix_exit_arch(mm);
        let mut vma = rusix_exit_next(ctx);
        if vma.is_null() || rusix_exit_is_zero(vma) {
            // A failed duplication can leave the leading sentinel. No gather,
            // map-count assertion or trace is valid on this path.
            rusix_exit_read_unlock(mm);
            rusix_exit_write_lock(mm);
        } else {
            rusix_exit_cache(mm);
            rusix_exit_gather(ctx, mm);
            rusix_exit_unmap(ctx, vma);
            rusix_exit_read_unlock(mm);
            rusix_exit_oom_skip(mm);
            rusix_exit_write_lock(mm);
            rusix_exit_clear_rcu(mm);
            rusix_exit_iter_set(ctx, rusix_exit_end(vma));
            rusix_exit_free_pgtables(ctx, vma);
            rusix_exit_finish(ctx);

            // Preserve the second original end read after gather completion.
            // Descriptors remain live until the removal loop below.
            rusix_exit_iter_set(ctx, rusix_exit_end(vma));
            let mut count: c_int = 0;
            loop {
                if rusix_exit_flags(vma) & rusix_exit_account != 0 {
                    nr_accounted = nr_accounted.wrapping_add(rusix_exit_pages(vma));
                }
                rusix_exit_detach(vma);
                remove_vma(vma);
                // No further access to this descriptor. The iterator belongs
                // to the maple tree, not the freed/recycled descriptor.
                count = count.wrapping_add(1);
                rusix_exit_resched();
                vma = rusix_exit_next(ctx);
                if vma.is_null() || rusix_exit_is_zero(vma) {
                    break;
                }
            }
            // Valid map_count bounds exclude signed overflow in the C policy;
            // wrapping_add keeps native representation without a Rust panic.
            rusix_exit_count_bug(count != rusix_exit_map_count(mm));
            rusix_exit_trace(mm);
        }
        rusix_exit_destroy(mm);
        rusix_exit_write_unlock(mm);
        rusix_exit_unaccount(nr_accounted);
    }
}
