// SPDX-License-Identifier: GPL-2.0

//! Ownership of a bio submitted to a bio-based block driver.
//!
//! Segment design informed by Andreas Hindborg's `rnull-v7.1-rc2` bio/SafePage
//! series (20260609-rnull-v6-19-rc5-send-v2-0-82c7404542e2@kernel.org).
//! Unlike ordinary Rust memory, bio payloads may be modified concurrently by
//! userspace or other I/O. No Rust references or slices to payloads are created.
//! Transfers currently use the kernel's C highmem copy/zero primitives; these
//! are transitional boundaries, to be replaced when a reviewed Rust abstraction
//! for externally racy memory is available. Driver policy and ownership are Rust.

use crate::{
    bindings,
    error::code::EINVAL,
    error::Result,
    page::{Page, PAGE_SIZE},
};
use core::{marker::PhantomData, ptr::NonNull};

/// Operation requested by a submitted bio.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Operation {
    /// Transfer data from the device into the bio.
    Read,
    /// Transfer data from the bio into the device.
    Write,
    /// Discard the indicated sector interval.
    Discard,
    /// An operation this interface does not interpret.
    Other,
}

/// Completion result for a submitted bio.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Status {
    /// Successful completion.
    Ok,
    /// I/O failure.
    IoError,
    /// A NOWAIT operation would need to block.
    WouldBlock,
}

/// Sole owner of the obligation to complete a submitted bio.
///
/// Dropping without explicit completion completes it with an I/O error. This
/// object does not own a `bio_put` reference: the submitter's endio callback
/// handles reclamation. Completion consumes this object and may free the bio.
///
/// # Invariants
///
/// Until completion, the bio and its current bvecs are valid until endio, this
/// object owns the sole driver completion obligation, and no other driver code
/// mutates its iterator or status. This excludes neither payload aliasing nor
/// payload changes by userspace. The object is deliberately not Send or Sync.
pub struct SubmittedBio {
    raw: NonNull<bindings::bio>,
    completed: bool,
}

impl SubmittedBio {
    /// Takes the completion obligation delivered by the block submit callback.
    ///
    /// # Safety
    ///
    /// `raw` must be a valid submitted bio whose iterator describes valid pinned
    /// bvecs. The caller must transfer exclusive driver ownership of its
    /// iterator/status and completion obligation, without retaining another
    /// object that can complete or mutate them. The underlying block layer must
    /// retain the bio, bdev/disk and payload pages through completion.
    pub(crate) unsafe fn from_raw(raw: *mut bindings::bio) -> Self {
        Self {
            // SAFETY: Validity, including non-nullness, is a caller requirement.
            raw: unsafe { NonNull::new_unchecked(raw) },
            completed: false,
        }
    }

    fn raw(&self) -> *mut bindings::bio {
        // Completion consumes Self; Drop does not use this accessor afterward.
        self.raw.as_ptr()
    }

    /// Returns the operation, without exposing raw operation flags.
    pub fn operation(&self) -> Operation {
        // SAFETY: The bio is live and driver-owned by the type invariant.
        let op = unsafe { bindings::bio_operation(self.raw()) };
        match op {
            bindings::req_op_REQ_OP_READ => Operation::Read,
            bindings::req_op_REQ_OP_WRITE => Operation::Write,
            bindings::req_op_REQ_OP_DISCARD => Operation::Discard,
            _ => Operation::Other,
        }
    }

    /// Current device sector, in 512-byte units.
    pub fn sector(&self) -> u64 {
        // SAFETY: The live iterator is exclusively driver-owned.
        unsafe { (*self.raw()).bi_iter.bi_sector }
    }

    /// Remaining byte count.
    pub fn len(&self) -> u32 {
        // SAFETY: The live iterator is exclusively driver-owned.
        unsafe { (*self.raw()).bi_iter.bi_size }
    }

    /// Whether the iterator has no remaining bytes.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Whether the submitter forbids blocking allocation.
    pub fn nowait(&self) -> bool {
        // SAFETY: The live bio is driver-owned; operation flags are immutable.
        unsafe { bindings::bio_is_nowait(self.raw()) }
    }

    /// Borrows the current single-page segment without advancing the iterator.
    pub fn segment(&mut self) -> Result<Segment<'_>> {
        if self.is_empty() || !matches!(self.operation(), Operation::Read | Operation::Write) {
            return Err(EINVAL);
        }
        // SAFETY: Read/write bios with nonempty iterators have a current bvec.
        // The helper uses bio_iter_iovec, which handles multipage bvec offsets.
        let vec = unsafe { bindings::bio_current_segment(self.raw()) };
        let offset = vec.bv_offset as usize;
        let len = vec.bv_len as usize;
        if vec.bv_page.is_null() || offset >= PAGE_SIZE || len == 0 || len > PAGE_SIZE - offset {
            return Err(EINVAL);
        }
        Ok(Segment {
            operation: self.operation(),
            vec,
            _bio: PhantomData,
        })
    }

    /// Advances by a nonzero, sector-aligned prefix of the current segment.
    pub fn advance(&mut self, bytes: u32) -> Result {
        if bytes == 0 || bytes & 511 != 0 || bytes as usize > self.segment()?.len() {
            return Err(EINVAL);
        }
        // SAFETY: The checked prefix is within the current bvec and bi_size.
        // The temporary segment borrow has ended, so no borrowed mapping exists.
        unsafe { bindings::bio_advance_single(self.raw(), bytes) };
        Ok(())
    }

    /// Completes the bio once; this may immediately reclaim its storage.
    pub fn complete(mut self, status: Status) {
        self.end(status);
    }

    fn end(&mut self, status: Status) {
        if !self.completed {
            self.completed = true;
            let raw = self.raw;
            // SAFETY: Marking completed claims the sole completion obligation.
            // No accesses to the bio occur after any endio primitive, including
            // in Drop. The C inline helpers retain the pinned status values.
            unsafe {
                match status {
                    Status::Ok => bindings::bio_endio(raw.as_ptr()),
                    Status::IoError => bindings::bio_io_error(raw.as_ptr()),
                    Status::WouldBlock => bindings::bio_wouldblock_error(raw.as_ptr()),
                }
            }
        }
    }
}

impl Drop for SubmittedBio {
    fn drop(&mut self) {
        self.end(Status::IoError);
    }
}

/// Borrowed, single-page portion of a submitted bio.
///
/// # Invariants
///
/// The bvec describes a nonempty in-page range, pinned by the borrowed bio.
/// The exclusive borrow prevents advancing or completing the bio while used.
/// Payload memory remains externally mutable and is never a Rust reference.
/// Only Read bios authorize writing payload pages; Write bios may refer to
/// read-only user mappings and may only be used as a source.
pub struct Segment<'a> {
    operation: Operation,
    vec: bindings::bio_vec,
    _bio: PhantomData<&'a mut SubmittedBio>,
}

impl Segment<'_> {
    /// Available bytes in this single-page segment.
    pub fn len(&self) -> usize {
        self.vec.bv_len as usize
    }

    /// A valid segment is never empty.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    fn check(&self, offset: usize, len: usize) -> Result {
        if offset > PAGE_SIZE || len > PAGE_SIZE - offset || len > self.len() {
            Err(EINVAL)
        } else {
            Ok(())
        }
    }

    /// Copies bio data to a private backing page, without advancing the bio.
    ///
    /// # Safety
    ///
    /// The destination page must not alias any bio payload or be exposed to
    /// userspace/devices. The caller must exclude all concurrent accesses to
    /// its destination interval until this call returns (e.g. a private lock).
    pub unsafe fn copy_to_page(&mut self, page: &Page, offset: usize, len: usize) -> Result {
        self.check(offset, len)?;
        if self.operation != Operation::Write {
            return Err(EINVAL);
        }
        // SAFETY: The bio pins this valid page and its checked segment range.
        let mapping = unsafe { bindings::kmap_local_page(self.vec.bv_page) };
        // SAFETY: The range is within the mapped page. No Rust dereference or
        // slice is made: C's existing highmem primitive accesses the externally
        // mutable source. The caller guarantees exclusive, nonaliasing storage.
        unsafe {
            bindings::memcpy_to_page(
                page.as_ptr(),
                offset,
                mapping.cast::<u8>().add(self.vec.bv_offset as usize).cast(),
                len,
            );
            // Nested mapping inside memcpy_to_page has already been unmapped.
            bindings::kunmap_local(mapping);
        }
        Ok(())
    }

    /// Copies a private initialized backing page into the bio payload.
    ///
    /// # Safety
    ///
    /// The source interval must be initialized and must not alias any bio
    /// payload or be exposed to userspace/devices. The caller must exclude
    /// concurrent writes to it until this call returns.
    pub unsafe fn copy_from_page(&mut self, page: &Page, offset: usize, len: usize) -> Result {
        self.check(offset, len)?;
        if self.operation != Operation::Read {
            return Err(EINVAL);
        }
        // SAFETY: The bio pins this valid page and its checked segment range.
        let mapping = unsafe { bindings::kmap_local_page(self.vec.bv_page) };
        // SAFETY: Bounds were checked, and caller guarantees initialized,
        // stable, nonaliasing source storage. C's existing highmem primitive
        // accesses the externally mutable destination; Rust never dereferences
        // it. Local mappings are released in reverse order on this task.
        unsafe {
            bindings::memcpy_from_page(
                mapping.cast::<u8>().add(self.vec.bv_offset as usize).cast(),
                page.as_ptr(),
                offset,
                len,
            );
            bindings::kunmap_local(mapping);
        }
        Ok(())
    }

    /// Zeros a prefix through the existing C user-page primitive.
    ///
    /// No Rust store touches externally mutable payload memory. The primitive
    /// also flushes the page's data cache. The bio is not advanced.
    pub fn zero(&mut self, len: usize) -> Result {
        self.check(self.vec.bv_offset as usize, len)?;
        if self.operation != Operation::Read {
            return Err(EINVAL);
        }
        // SAFETY: The bio pins the page and check bounds the complete interval.
        // The C primitive is intended for pages that may be mapped to userspace.
        unsafe {
            bindings::zero_user_segment(
                self.vec.bv_page,
                self.vec.bv_offset,
                self.vec.bv_offset + len as u32,
            )
        };
        Ok(())
    }
}
