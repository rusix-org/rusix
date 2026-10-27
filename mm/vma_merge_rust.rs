// SPDX-License-Identifier: GPL-2.0-or-later
// Complete merge/expand/shrink policies translated from Linux 6.18.58 mm/vma.c.
//! Native callers retain final-address stack context and iterator storage.
//! Rust owns eligibility, topology decisions, allocation ordering and rollback.
//! No descriptor-wide reference or copied C layout crosses callback/free points.
use core::ptr::null_mut;
use kernel::{
    bindings::{anon_vma, file, mm_struct, vm_area_struct, vm_operations_struct},
    ffi::{c_int, c_uint, c_ulong, c_void},
};
mod n {
    use super::*;
    #[allow(improper_ctypes)]
    unsafe extern "C" {
        #[link_name = "rusix_merge_mm"]
        pub fn mm(g: *mut c_void) -> *mut mm_struct;
        #[link_name = "rusix_merge_prev"]
        pub fn prev(g: *mut c_void) -> *mut vm_area_struct;
        #[link_name = "rusix_merge_set_middle"]
        pub fn set_middle(g: *mut c_void, value: *mut vm_area_struct);
        #[link_name = "rusix_merge_set_next"]
        pub fn set_next(g: *mut c_void, value: *mut vm_area_struct);
        #[link_name = "rusix_merge_target"]
        pub fn target(g: *mut c_void) -> *mut vm_area_struct;
        #[link_name = "rusix_merge_set_target"]
        pub fn set_target(g: *mut c_void, value: *mut vm_area_struct);
        #[link_name = "rusix_merge_copied_from"]
        pub fn copied_from(g: *mut c_void) -> *mut vm_area_struct;
        #[link_name = "rusix_merge_set_copied_from"]
        pub fn set_copied_from(g: *mut c_void, value: *mut vm_area_struct);
        #[link_name = "rusix_merge_set_start"]
        pub fn set_start(g: *mut c_void, value: c_ulong);
        #[link_name = "rusix_merge_set_end"]
        pub fn set_end(g: *mut c_void, value: c_ulong);
        #[link_name = "rusix_merge_pgoff"]
        pub fn pgoff(g: *mut c_void) -> c_ulong;
        #[link_name = "rusix_merge_set_pgoff"]
        pub fn set_pgoff(g: *mut c_void, value: c_ulong);
        #[link_name = "rusix_merge_vm_flags"]
        pub fn vm_flags(g: *mut c_void) -> c_ulong;
        #[link_name = "rusix_merge_anon_vma"]
        pub fn anon_vma(g: *mut c_void) -> *mut anon_vma;
        #[link_name = "rusix_merge_file"]
        pub fn file(g: *mut c_void) -> *mut file;
        #[link_name = "rusix_merge_just_expand"]
        pub fn just_expand(g: *mut c_void) -> bool;
        #[link_name = "rusix_merge_set_adjust_middle_start"]
        pub fn set_adjust_middle_start(g: *mut c_void, value: bool);
        #[link_name = "rusix_merge_set_adjust_next_start"]
        pub fn set_adjust_next_start(g: *mut c_void, value: bool);
        #[link_name = "rusix_merge_set_remove_middle"]
        pub fn set_remove_middle(g: *mut c_void, value: bool);
        #[link_name = "rusix_merge_set_remove_next"]
        pub fn set_remove_next(g: *mut c_void, value: bool);
        #[link_name = "rusix_merge_set_state"]
        pub fn set_state(g: *mut c_void, state: c_int);
        #[link_name = "rusix_merge_singular"]
        pub fn singular(v: *mut vm_area_struct) -> bool;
        #[link_name = "rusix_merge_policy_equal"]
        pub fn policy_equal(g: *mut c_void, v: *mut vm_area_struct) -> bool;
        #[link_name = "rusix_merge_uffd_equal"]
        pub fn uffd_equal(g: *mut c_void, v: *mut vm_area_struct) -> bool;
        #[link_name = "rusix_merge_name_equal"]
        pub fn name_equal(g: *mut c_void, v: *mut vm_area_struct) -> bool;
        #[link_name = "rusix_merge_set_anon"]
        pub fn set_anon(v: *mut vm_area_struct, anon: *mut anon_vma);
        #[link_name = "rusix_merge_assert_mm"]
        pub fn assert_mm(mm: *mut mm_struct);
        #[link_name = "rusix_merge_assert_vma"]
        pub fn assert_vma(v: *mut vm_area_struct);
        #[link_name = "rusix_merge_warn"]
        pub fn warn(condition: bool);
        #[link_name = "rusix_merge_warn_range"]
        pub fn warn_range(condition: bool);
        #[link_name = "rusix_merge_warn_vmg"]
        pub fn warn_vmg(condition: bool, g: *mut c_void);
        #[link_name = "rusix_merge_iter_addr"]
        pub fn iter_addr(i: *mut c_void) -> c_ulong;
        #[link_name = "rusix_merge_iter_next_range"]
        pub fn iter_next_range(i: *mut c_void) -> *mut vm_area_struct;
        #[link_name = "rusix_merge_iter_prev_range"]
        pub fn iter_prev_range(i: *mut c_void);
        #[link_name = "rusix_merge_iter_set"]
        pub fn iter_set(i: *mut c_void, start: c_ulong);
        #[link_name = "rusix_merge_iter_load"]
        pub fn iter_load(i: *mut c_void);
        #[link_name = "rusix_merge_iter_store"]
        pub fn iter_store(i: *mut c_void, v: *mut vm_area_struct);
        #[link_name = "rusix_merge_iter_clear"]
        pub fn iter_clear(i: *mut c_void);
        #[link_name = "rusix_merge_iter_next_rewind"]
        pub fn iter_next_rewind(i: *mut c_void) -> *mut vm_area_struct;
        #[link_name = "rusix_merge_adjust_huge"]
        pub fn adjust_huge(
            v: *mut vm_area_struct,
            start: c_ulong,
            end: c_ulong,
            adjust: *mut vm_area_struct,
        );
        #[link_name = "rusix_merge_flags_set"]
        pub fn flags_set(v: *mut vm_area_struct, flags: c_ulong);
        #[link_name = "rusix_merge_khugepaged"]
        pub fn khugepaged(v: *mut vm_area_struct, flags: c_ulong);
        #[link_name = "rusix_modify_vmi"]
        pub fn vmi(g: *mut c_void) -> *mut c_void;
        #[link_name = "rusix_modify_middle"]
        pub fn middle(g: *mut c_void) -> *mut vm_area_struct;
        #[link_name = "rusix_modify_next"]
        pub fn next(g: *mut c_void) -> *mut vm_area_struct;
        #[link_name = "rusix_modify_start"]
        pub fn start(g: *mut c_void) -> c_ulong;
        #[link_name = "rusix_modify_end"]
        pub fn end(g: *mut c_void) -> c_ulong;
        #[link_name = "rusix_modify_give_up_on_oom"]
        pub fn give_up_on_oom(g: *mut c_void) -> bool;
        #[link_name = "rusix_modify_adjust_middle_start"]
        pub fn adjust_middle_start(g: *mut c_void) -> bool;
        #[link_name = "rusix_modify_adjust_next_start"]
        pub fn adjust_next_start(g: *mut c_void) -> bool;
        #[link_name = "rusix_modify_remove_middle"]
        pub fn remove_middle(g: *mut c_void) -> bool;
        #[link_name = "rusix_modify_remove_next"]
        pub fn remove_next(g: *mut c_void) -> bool;
        #[link_name = "rusix_copy_start"]
        pub fn vstart(v: *mut vm_area_struct) -> c_ulong;
        #[link_name = "rusix_copy_end"]
        pub fn vend(v: *mut vm_area_struct) -> c_ulong;
        #[link_name = "rusix_copy_pgoff"]
        pub fn vpgoff(v: *mut vm_area_struct) -> c_ulong;
        #[link_name = "rusix_copy_anon"]
        pub fn anon(v: *mut vm_area_struct) -> *mut anon_vma;
        #[link_name = "rusix_modify_flags"]
        pub fn flags(v: *mut vm_area_struct) -> c_ulong;
        #[link_name = "rusix_remove_file"]
        pub fn vfile(v: *mut vm_area_struct) -> *mut file;
        #[link_name = "rusix_remove_ops"]
        pub fn ops(v: *mut vm_area_struct) -> *const vm_operations_struct;
        #[link_name = "rusix_copy_clone_anon"]
        pub fn clone_anon(v: *mut vm_area_struct, src: *mut vm_area_struct) -> c_int;
        #[link_name = "rusix_copy_unlink_anon"]
        pub fn unlink_anon(v: *mut vm_area_struct);
        #[link_name = "rusix_copy_set_range"]
        pub fn set_range(v: *mut vm_area_struct, start: c_ulong, end: c_ulong, offset: c_ulong);
        #[link_name = "rusix_link_config"]
        pub fn config(i: *mut c_void, start: c_ulong, end: c_ulong);
        #[link_name = "rusix_link_prealloc"]
        pub fn prealloc(i: *mut c_void, v: *mut vm_area_struct) -> c_int;
        #[link_name = "rusix_link_start_write"]
        pub fn start_write(v: *mut vm_area_struct);
        #[link_name = "rusix_modify_prev"]
        pub fn prev_iter(i: *mut c_void);
        #[link_name = "rusix_modify_mm"]
        pub fn vmm(v: *mut vm_area_struct) -> *mut mm_struct;
        #[link_name = "rusix_link_validate"]
        pub fn validate(mm: *mut mm_struct);
        #[link_name = "rusix_init_multi_vma_prep"]
        pub fn init_prep(prep: *mut c_void, v: *mut vm_area_struct, g: *mut c_void);
        #[link_name = "rusix_init_vma_prep"]
        pub fn init_single_prep(prep: *mut c_void, v: *mut vm_area_struct);
        #[link_name = "rusix_vma_prepare"]
        pub fn prepare(prep: *mut c_void);
        #[link_name = "rusix_vma_complete"]
        pub fn complete(prep: *mut c_void, i: *mut c_void, mm: *mut mm_struct);
        #[link_name = "rusix_remove_close"]
        pub fn close(
            ops: *const vm_operations_struct,
        ) -> Option<unsafe extern "C" fn(*mut vm_area_struct)>;
        #[link_name = "rusix_merge_sticky"]
        pub static sticky: c_ulong;
        #[link_name = "rusix_merge_special"]
        pub static special: c_ulong;
        #[link_name = "rusix_merge_ignore"]
        pub static ignore: c_ulong;
        #[link_name = "rusix_merge_nomerge"]
        pub static nomerge: c_int;
        #[link_name = "rusix_merge_success"]
        pub static success: c_int;
        #[link_name = "rusix_merge_nomem"]
        pub static nomem: c_int;
        #[link_name = "rusix_copy_page_shift"]
        pub static page_shift: c_uint;
        #[link_name = "rusix_copy_enomem"]
        pub static enomem: c_int;
    }
}

/// Caller holds mmap write lock; a nonnull VMA remains live for these accesses.
unsafe fn vma_is_fork_child(v: *mut vm_area_struct) -> bool {
    // SAFETY: Native short-circuit order avoids dereferencing absent descriptors.
    unsafe { !v.is_null() && !n::anon(v).is_null() && !n::singular(v) }
}

/// The selected neighbor is nonnull and protected by the caller's mmap lock.
unsafe fn is_mergeable_vma(g: *mut c_void, right: bool) -> bool {
    // SAFETY: Only individual native field/predicate accesses; no Rust borrowing
    // of the descriptor or shared file/policy objects is introduced.
    unsafe {
        let v = if right { n::next(g) } else { n::prev(g) };
        if !n::policy_equal(g, v) {
            return false;
        }
        if (n::flags(v) ^ n::vm_flags(g)) & !n::ignore != 0 {
            return false;
        }
        if n::vfile(v) != n::file(g) {
            return false;
        }
        if !n::uffd_equal(g, v) {
            return false;
        }
        n::name_equal(g, v)
    }
}

/// Merge context and its candidate descriptors are live under mmap write lock.
unsafe fn is_mergeable_anon_vma(g: *mut c_void, right: bool) -> bool {
    // SAFETY: The target exists. Source/copy pointers are checked before use;
    // pointer equality preserves ancestry identity without dereferencing anon_vma.
    unsafe {
        let target = if right { n::next(g) } else { n::prev(g) };
        let source = n::middle(g);
        let target_anon = n::anon(target);
        let source_anon = n::anon_vma(g);
        n::warn(!source.is_null() && source_anon != n::anon(source));
        if target_anon.is_null() && !source_anon.is_null() {
            let copied = n::copied_from(g);
            if vma_is_fork_child(source) {
                return false;
            }
            if vma_is_fork_child(copied) {
                return false;
            }
            return true;
        }
        if !target_anon.is_null() && source_anon.is_null() {
            return !vma_is_fork_child(target);
        }
        source_anon == target_anon
    }
}

/// Right neighbor exists; input range and page offsets obey the native contract.
unsafe fn can_vma_merge_before(g: *mut c_void) -> bool {
    // SAFETY: mmap write lock stabilizes scalar reads. Explicit wrapping matches
    // unsigned C arithmetic, rather than adding a new overflow failure path.
    unsafe {
        let pages = n::end(g).wrapping_sub(n::start(g)) >> n::page_shift;
        is_mergeable_vma(g, true)
            && is_mergeable_anon_vma(g, true)
            && n::vpgoff(n::next(g)) == n::pgoff(g).wrapping_add(pages)
    }
}

/// Left neighbor exists and remains live under mmap write lock.
unsafe fn can_vma_merge_after(g: *mut c_void) -> bool {
    // SAFETY: Read the same native page count/offset after compatibility checks.
    unsafe {
        if is_mergeable_vma(g, false) && is_mergeable_anon_vma(g, false) {
            let prev = n::prev(g);
            let pages = n::vend(prev).wrapping_sub(n::vstart(prev)) >> n::page_shift;
            return n::vpgoff(prev).wrapping_add(pages) == n::pgoff(g);
        }
        false
    }
}

/// Context is caller-local, and any nonnull neighbor is live and locked.
unsafe fn can_vma_merge_left(g: *mut c_void) -> bool {
    // SAFETY: Short-circuiting protects nullable previous pointer.
    unsafe { !n::prev(g).is_null() && n::vend(n::prev(g)) == n::start(g) && can_vma_merge_after(g) }
}

/// `left` was obtained for this context under the same mmap write lock.
unsafe fn can_vma_merge_right(g: *mut c_void, left: bool) -> bool {
    // SAFETY: Successful left eligibility implies prev exists. Check cross-side
    // ancestry separately: compatibility with middle is not transitive.
    unsafe {
        let next = n::next(g);
        if next.is_null() || n::end(g) != n::vstart(next) || !can_vma_merge_before(g) {
            return false;
        }
        if !left {
            return true;
        }
        let prev = n::prev(g);
        n::anon(prev).is_null() || n::anon(next).is_null() || n::anon(prev) == n::anon(next)
    }
}

/// VMA is live. This only inspects a callback; it never calls close on retirement.
unsafe fn can_merge_remove_vma(v: *mut vm_area_struct) -> bool {
    // SAFETY: ops lifetime follows VMA. Native typed callback read handles only
    // the nonnull branch, retaining the original nullable-function semantics.
    unsafe {
        let ops = n::ops(v);
        ops.is_null() || n::close(ops).is_none()
    }
}

/// Both descriptors are live; destination is VMA-write locked on clone path.
/// `dup` is private rollback storage, disjoint from native descriptors/context.
unsafe fn dup_anon_vma(
    dst: *mut vm_area_struct,
    src: *mut vm_area_struct,
    dup: &mut *mut vm_area_struct,
) -> c_int {
    // SAFETY: The native clone owns partial-failure cleanup, including clearing
    // dst->anon_vma. Record rollback ownership only after successful clone.
    unsafe {
        if !n::anon(src).is_null() && n::anon(dst).is_null() {
            n::assert_vma(dst);
            n::set_anon(dst, n::anon(src));
            let ret = n::clone_anon(dst, src);
            if ret != 0 {
                return ret;
            }
            *dup = dst;
        }
        0
    }
}

/// Selected adjustment descriptor remains locked/live before transaction commit.
unsafe fn vmg_adjust_set_range(g: *mut c_void) {
    // SAFETY: The corresponding flag implies a valid middle/next. Native
    // unsigned page-offset arithmetic is preserved for both adjustment modes.
    unsafe {
        let adjust;
        let offset;
        if n::adjust_middle_start(g) {
            adjust = n::middle(g);
            offset = n::vpgoff(adjust)
                .wrapping_add(n::end(g).wrapping_sub(n::vstart(adjust)) >> n::page_shift);
        } else if n::adjust_next_start(g) {
            adjust = n::next(g);
            offset = n::vpgoff(adjust)
                .wrapping_sub(n::vstart(adjust).wrapping_sub(n::end(g)) >> n::page_shift);
        } else {
            return;
        }
        n::set_range(adjust, n::end(g), n::vend(adjust), offset);
    }
}

/// `prep` is writable canonical C vma_prepare storage, disjoint from `g` and
/// descriptors. Native mmap/VMA write and cursor contracts hold. Completion may
/// consume middle/next; no retired descriptor may be accessed afterwards.
unsafe fn commit_merge(g: *mut c_void, prep: *mut c_void) -> c_int {
    // SAFETY: Preallocation precedes any prepare/range mutation. The successful
    // prepare/complete interval cannot fail; C subsystems retain their locks and
    // Rust's existing preparation policy owns publication and retirement.
    unsafe {
        let v;
        if n::adjust_next_start(g) {
            v = n::middle(g);
            n::config(n::vmi(g), n::end(g), n::vend(n::next(g)));
        } else {
            v = n::target(g);
            n::config(n::vmi(g), n::start(g), n::end(g));
        }
        n::init_prep(prep, v, g);
        if n::prealloc(n::vmi(g), v) != 0 {
            return n::enomem;
        }
        n::prepare(prep);
        n::adjust_huge(
            v,
            n::start(g),
            n::end(g),
            if n::adjust_middle_start(g) {
                n::middle(g)
            } else {
                null_mut()
            },
        );
        n::set_range(v, n::start(g), n::end(g), n::pgoff(g));
        vmg_adjust_set_range(g);
        n::iter_store(n::vmi(g), n::target(g));
        n::complete(prep, n::vmi(g), n::vmm(v));
        0
    }
}

/// Merge an existing range; may consume middle and next on success.
/// # Safety
/// Native existing-range contract: valid caller-local merge/prep storage, mmap
/// write lock, middle covers the requested nonempty range, cursor lies within
/// middle, and prev is its proper left candidate (possibly middle itself).
// SAFETY: Unique selected entry, exact pointer/scalar C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_merge_existing(
    g: *mut c_void,
    prep: *mut c_void,
) -> *mut vm_area_struct {
    // SAFETY: All descriptor access is under the native locks. Save only scalar
    // and pointer values; commit may retire descriptors, so its success branch
    // reads only surviving target/context and never the saved middle/next.
    unsafe {
        let mut sticky = n::vm_flags(g) & n::sticky;
        let middle = n::middle(g);
        let prev = n::prev(g);
        let start = n::start(g);
        let end = n::end(g);
        let left_side = !middle.is_null() && start == n::vstart(middle);
        let right_side = !middle.is_null() && end == n::vend(middle);
        let mut anon_dup = null_mut();
        n::assert_mm(n::mm(g));
        n::warn_vmg(middle.is_null(), g);
        n::warn_vmg(!n::next(g).is_null(), g);
        n::warn_vmg(!prev.is_null() && start <= n::vstart(prev), g);
        n::warn_vmg(start >= end, g);
        n::warn_vmg(
            !middle.is_null()
                && ((middle != prev && n::start(g) != n::vstart(middle))
                    || n::end(g) > n::vend(middle)),
            g,
        );
        n::warn_vmg(
            !middle.is_null()
                && !(n::iter_addr(n::vmi(g)) >= n::vstart(middle)
                    && n::iter_addr(n::vmi(g)) < n::vend(middle)),
            g,
        );
        n::warn_vmg(!n::copied_from(g).is_null(), g);
        n::set_state(g, n::nomerge);
        if n::vm_flags(g) & n::special != 0 || (!left_side && !right_side) {
            return null_mut();
        }
        let merge_left = left_side && can_vma_merge_left(g);
        let next;
        let mut merge_right;
        if right_side {
            next = n::iter_next_range(n::vmi(g));
            n::set_next(g, next);
            n::iter_prev_range(n::vmi(g));
            merge_right = can_vma_merge_right(g, merge_left);
        } else {
            merge_right = false;
            next = null_mut();
        }
        if merge_left {
            n::prev_iter(n::vmi(g));
        } else if !merge_right {
            return null_mut();
        }
        let mut merge_both = merge_left && merge_right;
        n::set_remove_middle(g, left_side && right_side);
        if n::remove_middle(g) && !can_merge_remove_vma(middle) {
            return null_mut();
        }
        n::set_remove_next(g, merge_both);
        if n::remove_next(g) && !can_merge_remove_vma(next) {
            n::set_remove_next(g, false);
            merge_right = false;
            merge_both = false;
        }
        n::start_write(middle);
        if merge_right {
            n::start_write(next);
            n::set_target(g, next);
            sticky |= n::flags(next) & n::sticky;
        }
        if merge_left {
            n::start_write(prev);
            n::set_target(g, prev);
            sticky |= n::flags(prev) & n::sticky;
        }
        let err;
        if merge_both {
            n::set_start(g, n::vstart(prev));
            n::set_end(g, n::vend(next));
            n::set_pgoff(g, n::vpgoff(prev));
            err = dup_anon_vma(
                prev,
                if !n::anon(next).is_null() {
                    next
                } else {
                    middle
                },
                &mut anon_dup,
            );
        } else if merge_left {
            n::set_start(g, n::vstart(prev));
            n::set_pgoff(g, n::vpgoff(prev));
            if !n::remove_middle(g) {
                n::set_adjust_middle_start(g, true);
            }
            err = dup_anon_vma(prev, middle, &mut anon_dup);
        } else {
            let pages = n::end(g).wrapping_sub(n::start(g)) >> n::page_shift;
            n::warn_vmg(!merge_right, g);
            n::warn_vmg(
                n::start(g) > n::vstart(middle) && !prev.is_null() && middle != prev,
                g,
            );
            if n::remove_middle(g) {
                n::set_end(g, n::vend(next));
                n::set_pgoff(g, n::vpgoff(next).wrapping_sub(pages));
            } else {
                n::set_adjust_next_start(g, true);
                n::set_start(g, n::vstart(middle));
                n::set_end(g, start);
                n::set_pgoff(g, n::vpgoff(middle));
            }
            err = dup_anon_vma(next, middle, &mut anon_dup);
        }
        if err != 0 || commit_merge(g, prep) != 0 {
            n::iter_set(n::vmi(g), start);
            n::iter_load(n::vmi(g));
            if !anon_dup.is_null() {
                n::unlink_anon(anon_dup);
            }
            if !n::give_up_on_oom(g) {
                n::set_state(g, n::nomem);
            }
            return null_mut();
        }
        n::flags_set(n::target(g), sticky);
        n::khugepaged(n::target(g), n::vm_flags(g));
        n::set_state(g, n::success);
        n::target(g)
    }
}

/// Merge a proposed new range into one or both adjacent VMAs.
/// # Safety
/// Native new-range contract, mmap write lock, nonempty valid range, no middle
/// or target initially, and cursor at/before gap (at prev for just_expand).
/// Prep is disjoint, writable, final-address canonical native stack storage.
// SAFETY: Unique selected C entry; contexts are opaque pointers.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_merge_new(g: *mut c_void, prep: *mut c_void) -> *mut vm_area_struct {
    // SAFETY: Saved neighbors are used only before expansion may retire next.
    // The successful path reads surviving target; no foreign borrow spans commit.
    unsafe {
        let prev = n::prev(g);
        let next = n::next(g);
        let end = n::end(g);
        n::assert_mm(n::mm(g));
        n::warn_vmg(!n::middle(g).is_null(), g);
        n::warn_vmg(!n::target(g).is_null(), g);
        n::warn_vmg(n::iter_addr(n::vmi(g)) > end, g);
        n::set_state(g, n::nomerge);
        if n::vm_flags(g) & n::special != 0 || (prev.is_null() && next.is_null()) {
            return null_mut();
        }
        let left = can_vma_merge_left(g);
        let right = !n::just_expand(g) && can_vma_merge_right(g, left);
        if right {
            n::set_end(g, n::vend(next));
            n::set_target(g, next);
        }
        if left {
            n::set_start(g, n::vstart(prev));
            n::set_target(g, prev);
            n::set_pgoff(g, n::vpgoff(prev));
            if right && !can_merge_remove_vma(next) {
                n::set_end(g, end);
            }
            if !n::just_expand(g) {
                n::prev_iter(n::vmi(g));
            }
        }
        if !n::target(g).is_null() && rusix_merge_expand(g, prep) == 0 {
            n::khugepaged(n::target(g), n::vm_flags(g));
            n::set_state(g, n::success);
            return n::target(g);
        }
        null_mut()
    }
}

/// Translate copied-range input into new-range form.
/// # Safety
/// Same lock/storage contract as new-range; middle is the live copied-from VMA.
// SAFETY: Selected private C ABI; no native layout is reconstructed.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_merge_copied(
    g: *mut c_void,
    prep: *mut c_void,
) -> *mut vm_area_struct {
    // SAFETY: Context mutation transfers the pointer identity, not VMA ownership;
    // new-range may consume destination neighbors but not the copied source.
    unsafe {
        n::warn_vmg(n::middle(g).is_null(), g);
        n::set_copied_from(g, n::middle(g));
        n::set_middle(g, null_mut());
        rusix_merge_new(g, prep)
    }
}

/// Expand an existing target, optionally retiring next.
/// # Safety
/// Caller holds mmap write lock, target exists and expansion bounds/adjacent
/// compatibility were checked by caller. Prep has canonical disjoint storage.
// SAFETY: Exact selected native expansion signature via opaque context pointers.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_merge_expand(g: *mut c_void, prep: *mut c_void) -> c_int {
    // SAFETY: Per-VMA write locks precede mutation. Anon clone owns its partial
    // failures; only successful duplication is explicitly rolled back after
    // preallocation failure. Target survives commit; next may not.
    unsafe {
        let mut anon_dup = null_mut();
        let mut remove_next = false;
        let target = n::target(g);
        let next = n::next(g);
        let mut ret = 0;
        let mut sticky = (n::vm_flags(g) & n::sticky) | (n::flags(target) & n::sticky);
        n::warn_vmg(target.is_null(), g);
        n::assert_mm(n::mm(g));
        n::start_write(target);
        if !next.is_null() && target != next && n::end(g) == n::vend(next) {
            sticky |= n::flags(next) & n::sticky;
            remove_next = true;
        }
        n::warn_vmg(target.is_null(), g);
        n::warn_vmg(remove_next && !can_merge_remove_vma(next), g);
        n::warn_vmg(
            !next.is_null() && !remove_next && next != target && n::end(g) > n::vstart(next),
            g,
        );
        n::warn_vmg(
            n::vstart(target) < n::start(g) || n::vend(target) > n::end(g),
            g,
        );
        if remove_next {
            ret = dup_anon_vma(target, next, &mut anon_dup);
        }
        if ret == 0 && !n::copied_from(g).is_null() {
            ret = dup_anon_vma(target, n::copied_from(g), &mut anon_dup);
        }
        if ret != 0 {
            return ret;
        }
        if remove_next {
            n::start_write(next);
            n::set_remove_next(g, true);
        }
        if commit_merge(g, prep) != 0 {
            if !anon_dup.is_null() {
                n::unlink_anon(anon_dup);
            }
            if !n::give_up_on_oom(g) {
                n::set_state(g, n::nomem);
            }
            return n::enomem;
        }
        n::flags_set(target, sticky);
        0
    }
}

/// Shrink exactly one side of a VMA using the shared preparation protocol.
/// # Safety
/// Caller holds mmap write lock with a valid VMA/range/cursor and canonical
/// disjoint prep storage. At least one endpoint is unchanged, as in native C.
// SAFETY: Selected scalar/pointer ABI agrees with native wrapper.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_merge_shrink(
    i: *mut c_void,
    v: *mut vm_area_struct,
    start: c_ulong,
    end: c_ulong,
    pgoff: c_ulong,
    prep: *mut c_void,
) -> c_int {
    // SAFETY: Preallocation precedes VMA write and mutation; this preparation
    // has no removal entries, so v remains live through validation.
    unsafe {
        n::warn_range(n::vstart(v) != start && n::vend(v) != end);
        if n::vstart(v) < start {
            n::config(i, n::vstart(v), start);
        } else {
            n::config(i, end, n::vend(v));
        }
        if n::prealloc(i, null_mut()) != 0 {
            return n::enomem;
        }
        n::start_write(v);
        n::init_single_prep(prep, v);
        n::prepare(prep);
        n::adjust_huge(v, start, end, null_mut());
        n::iter_clear(i);
        n::set_range(v, start, end, pgoff);
        n::complete(prep, i, n::vmm(v));
        n::validate(n::vmm(v));
        0
    }
}

/// Extend a live VMA using a canonical native VMG_VMA_STATE context.
/// # Safety
/// Wrapper constructs the original delta range under mmap write lock. Context
/// and prep are caller-local; cursor points at the existing VMA.
// SAFETY: Unique selected entry; exact opaque pointer ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rusix_merge_extend(
    g: *mut c_void,
    prep: *mut c_void,
) -> *mut vm_area_struct {
    // SAFETY: Iterator primitive preserves native rewind behavior; middle was
    // used only to initialize context metadata and is cleared before new merge.
    unsafe {
        n::set_next(g, n::iter_next_rewind(n::vmi(g)));
        n::set_middle(g, null_mut());
        rusix_merge_new(g, prep)
    }
}
