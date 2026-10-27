// SPDX-License-Identifier: GPL-2.0-or-later
// Translation of mm/vma_init.c and the fresh initialization in linux/mm.h.

//! VMA descriptor lifecycle and permanent slab-cache pointer ownership.
//!
//! TYPESAFE_BY_RCU permits reuse while unstable readers still inspect fields.
//! Even a fresh allocation is only a raw pointer, never an exclusive Rust VMA.

use core::ptr::null_mut;
use kernel::{
    bindings::{kmem_cache, mm_struct, vm_area_struct},
    ffi::{c_uint, c_void},
};

// Only vma_state_init writes this during single-threaded boot, before any VMA
// allocation. The cache is permanent; all later users only read this pointer.
// Keeping the static private prevents C from creating another mutable owner.
static mut VM_AREA_CACHE: *mut kmem_cache = null_mut();

// Canonical aggregates cross only by pointer, never by value. Generated MM/VMA
// graphs contain GNU empty structs (e.g. sched_statistics); recursive FFI lint
// reports these despite the unchanged C pointer ABI. Scalar and pointer types
// below match the C declarations; this exception does not cover field accesses.
#[allow(improper_ctypes)]
unsafe extern "C" {
    static rusix_vma_refcount_max: c_uint;
    fn rusix_vma_cache_create() -> *mut kmem_cache;
    fn rusix_vma_alloc(cache: *mut kmem_cache) -> *mut vm_area_struct;
    fn rusix_vma_slab_free(cache: *mut kmem_cache, vma: *mut vm_area_struct);
    fn rusix_vma_zero(vma: *mut vm_area_struct);
    fn rusix_vma_set_mm(vma: *mut vm_area_struct, mm: *mut mm_struct);
    fn rusix_vma_dummy_ops(vma: *mut vm_area_struct);
    fn rusix_vma_list_init(vma: *mut vm_area_struct);
    fn rusix_vma_lock_init(vma: *mut vm_area_struct, reset: bool);
    fn rusix_vma_assert_flags(vma: *mut vm_area_struct);
    fn rusix_vma_assert_file(vma: *mut vm_area_struct);
    fn rusix_vma_copy_vm_mm(src: *const vm_area_struct, dest: *mut vm_area_struct);
    fn rusix_vma_copy_vm_ops(src: *const vm_area_struct, dest: *mut vm_area_struct);
    fn rusix_vma_copy_vm_start(src: *const vm_area_struct, dest: *mut vm_area_struct);
    fn rusix_vma_copy_vm_end(src: *const vm_area_struct, dest: *mut vm_area_struct);
    fn rusix_vma_copy_anon_vma(src: *const vm_area_struct, dest: *mut vm_area_struct);
    fn rusix_vma_copy_vm_pgoff(src: *const vm_area_struct, dest: *mut vm_area_struct);
    fn rusix_vma_copy_vm_file(src: *const vm_area_struct, dest: *mut vm_area_struct);
    fn rusix_vma_copy_vm_private_data(src: *const vm_area_struct, dest: *mut vm_area_struct);
    fn rusix_vma_copy_flags(src: *const vm_area_struct, dest: *mut vm_area_struct);
    fn rusix_vma_copy_prot(src: *const vm_area_struct, dest: *mut vm_area_struct);
    fn rusix_vma_copy_shared(src: *const vm_area_struct, dest: *mut vm_area_struct);
    fn rusix_vma_copy_userfault(src: *const vm_area_struct, dest: *mut vm_area_struct);
    fn rusix_vma_copy_name(src: *const vm_area_struct, dest: *mut vm_area_struct);
    fn rusix_vma_copy_swap(src: *const vm_area_struct, dest: *mut vm_area_struct);
    fn rusix_vma_copy_policy(src: *const vm_area_struct, dest: *mut vm_area_struct);
    // PFN context layout never crosses this boundary. The C side uses the
    // canonical struct pfnmap_track_ctx pointer, with identical pointer ABI.
    fn rusix_vma_pfn_clear(vma: *mut vm_area_struct);
    fn rusix_vma_pfn_get(vma: *mut vm_area_struct) -> *mut c_void;
    fn rusix_vma_pfn_count(ctx: *mut c_void) -> c_uint;
    fn rusix_vma_pfn_acquire(ctx: *mut c_void);
    fn rusix_vma_pfn_set(vma: *mut vm_area_struct, ctx: *mut c_void);
    fn rusix_vma_pfn_put(ctx: *mut c_void);
    fn rusix_vma_numa_init(vma: *mut vm_area_struct);
    fn rusix_vma_name_dup(orig: *mut vm_area_struct, new: *mut vm_area_struct);
    fn rusix_vma_assert_detached(vma: *mut vm_area_struct);
    fn rusix_vma_numa_free(vma: *mut vm_area_struct);
    fn rusix_vma_name_free(vma: *mut vm_area_struct);
}

/// Initialize the permanent cache from the canonical C boot entry.
///
/// # Safety
/// Single boot-time caller before all VMA allocation, with slab initialized.
/// The cache-create primitive retains SLAB_PANIC; no new fallible init path.
// SAFETY: Only the selected vma_init.c entry calls this unique ABI definition;
// its canonical __init attributes remain in C. This code is boot-only too.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".init.text")]
#[cold]
pub unsafe extern "C" fn rusix_vma_state_init() {
    // SAFETY: Boot publication precedes all readers; pointer remains permanent
    // even when the init code is reclaimed. Cache constructor owns its layout.
    unsafe { VM_AREA_CACHE = rusix_vma_cache_create() };
}

/// Allocate and initialize a detached descriptor, or return NULL.
///
/// # Safety
/// Boot cache initialization has completed. Caller retains `mm` and supplies a
/// sleepable GFP_KERNEL context, then owns publication or detached reclamation.
// SAFETY: Kbuild/selection excludes the original C definition; pointer ABI is
// identical to the existing declaration and all unchanged callers.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn vm_area_alloc(mm: *mut mm_struct) -> *mut vm_area_struct {
    // SAFETY: No Rust references are made to recycled slab storage. C retains
    // original memset/field semantics toward unstable lockless RCU observers.
    unsafe {
        let vma = rusix_vma_alloc(VM_AREA_CACHE);
        if vma.is_null() {
            return null_mut();
        }
        rusix_vma_zero(vma);
        rusix_vma_set_mm(vma, mm);
        rusix_vma_dummy_ops(vma);
        rusix_vma_list_init(vma);
        rusix_vma_lock_init(vma, false);
        vma
    }
}

/// Copy only the baseline-selected fields and acquire descriptor-owned refs.
///
/// # Safety
/// `orig` remains live with the original exclusive-writer field guarantees.
/// Caller supplies sleepable context and retains borrowed resources throughout
/// duplication. The result borrows file/policy/anon-vma/ops resources: callers
/// still acquire those separately before publication, just as for C duplication.
// SAFETY: The selected C body is excluded; unchanged callers use this exact ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn vm_area_dup(orig: *mut vm_area_struct) -> *mut vm_area_struct {
    // SAFETY: Stable source pointers do not imply exclusive whole-VMA access.
    // Every foreign access stays C; shared.rb copies retain data_race(memcpy).
    unsafe {
        let new = rusix_vma_alloc(VM_AREA_CACHE);
        if new.is_null() {
            return null_mut();
        }
        rusix_vma_assert_flags(orig);
        rusix_vma_assert_file(orig);
        rusix_vma_copy_vm_mm(orig, new);
        rusix_vma_copy_vm_ops(orig, new);
        rusix_vma_copy_vm_start(orig, new);
        rusix_vma_copy_vm_end(orig, new);
        rusix_vma_copy_anon_vma(orig, new);
        rusix_vma_copy_vm_pgoff(orig, new);
        rusix_vma_copy_vm_file(orig, new);
        rusix_vma_copy_vm_private_data(orig, new);
        rusix_vma_copy_flags(orig, new);
        rusix_vma_copy_prot(orig, new);
        rusix_vma_copy_shared(orig, new);
        rusix_vma_copy_userfault(orig, new);
        rusix_vma_copy_name(orig, new);
        rusix_vma_copy_swap(orig, new);
        // MMU is required, so the original !MMU vm_region copy is unreachable.
        rusix_vma_copy_policy(orig, new);
        rusix_vma_pfn_clear(new);
        let ctx = rusix_vma_pfn_get(orig);
        if !ctx.is_null() {
            // The original holds the source reference through this operation.
            // Preserve the explicit saturation check and canonical kref_get;
            // no fallible get or duplicated tracking is substituted.
            if rusix_vma_pfn_count(ctx) >= rusix_vma_refcount_max {
                // No lock/list/name initialization or extra refs reached yet.
                // Free only slab storage; borrowed copied pointers aren't owned.
                rusix_vma_slab_free(VM_AREA_CACHE, new);
                return null_mut();
            }
            rusix_vma_pfn_acquire(ctx);
            rusix_vma_pfn_set(new, ctx);
        }
        rusix_vma_lock_init(new, true);
        rusix_vma_list_init(new);
        rusix_vma_numa_init(new);
        // Preserve canonical name saturation fallback (allocation can produce
        // NULL without failing descriptor duplication); no invented unwind.
        rusix_vma_name_dup(orig, new);
        new
    }
}

/// Reclaim a detached descriptor, without releasing caller-owned VMA resources.
///
/// # Safety
/// Caller has performed required detach/drain and released file, policy, ops,
/// tree/rmap resources as appropriate. This consumes the live descriptor; no
/// stable reader may retain it. Unstable RCU observers do not get Rust references.
// SAFETY: Selection excludes the original C definition and preserves its ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn vm_area_free(vma: *mut vm_area_struct) {
    // SAFETY: Original ordered detached assertion and descriptor ref cleanup.
    // PFN put may free the context: only clear the VMA field afterward. The
    // final slab free may immediately permit reuse; no later VMA access occurs.
    unsafe {
        rusix_vma_assert_detached(vma);
        rusix_vma_numa_free(vma);
        rusix_vma_name_free(vma);
        let ctx = rusix_vma_pfn_get(vma);
        if !ctx.is_null() {
            rusix_vma_pfn_put(ctx);
            rusix_vma_pfn_clear(vma);
        }
        rusix_vma_slab_free(VM_AREA_CACHE, vma);
    }
}
