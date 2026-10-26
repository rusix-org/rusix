// SPDX-License-Identifier: GPL-2.0

//! Registration of bio-based disks with typed, reference-counted driver state.
//!
//! Registration follows Linux's `__blk_alloc_disk` / `device_add_disk` path,
//! without a blk-mq tag set. The private Arc is released by `free_disk`, not by
//! the registration handle: open devices may outlive unpublication.

use super::bio::SubmittedBio;
use crate::{
    bindings,
    error::{code::EINVAL, from_err_ptr, to_result, Result},
    fmt::{self, Write},
    page::PAGE_SIZE,
    static_lock_class,
    str::NullTerminatedFormatter,
    sync::Arc,
    types::{ForeignOwnable, ScopeGuard},
    ThisModule,
};
use core::{marker::PhantomData, ptr};

/// Driver callbacks for a bio-based disk.
///
/// # Safety
///
/// `OWNER` must identify the module containing this implementation and its
/// associated drop code. That code must remain resident until all registered
/// disks and their final callbacks are gone. Built-in drivers satisfy this
/// lifetime automatically; unloadable drivers must separately establish it.
/// When registering synchronous limits, submit must finish the bio before
/// returning. With NOWAIT limits it must honor `SubmittedBio::nowait`.
pub unsafe trait Operations: Send + Sync + 'static {
    /// The `THIS_MODULE` emitted by the driver's module declaration.
    const OWNER: &'static ThisModule;

    /// Handles a submission, taking its sole completion obligation.
    fn submit(&self, bio: SubmittedBio);
}

/// Device numbering, capacity and queue capabilities.
///
/// Explicit numbering exists for compatibility with an existing block ABI;
/// new devices should normally request automatic numbering (major/minors zero).
pub struct DiskConfig {
    /// Existing registered major, or zero for automatic allocation.
    pub major: u32,
    /// First minor for explicit numbering.
    pub first_minor: u32,
    /// Minor count, or zero for automatic allocation.
    pub minors: u32,
    /// Capacity in 512-byte sectors.
    pub capacity_sectors: u64,
    /// Physical block size; logical block size is 512 bytes.
    pub physical_block_size: u32,
    /// Discard granularity in bytes.
    pub discard_granularity: u32,
    /// Maximum hardware discard sectors (zero disables discard).
    pub max_discard_sectors: u32,
    /// Maximum discard segments.
    pub max_discard_segments: u32,
    /// Submissions always finish in their submitting context.
    pub synchronous: bool,
    /// Driver supports nonblocking submission.
    pub nowait: bool,
}

/// An owned, published disk registration.
///
/// # Invariants
///
/// `disk` owns the initial reference to a successfully added disk. Its private
/// data contains exactly one foreign Arc<T>, owned by the final free callback.
/// Unpublishing the registration does not free that Arc prematurely.
pub struct BioDisk<T: Operations> {
    disk: *mut bindings::gendisk,
    _driver: PhantomData<Arc<T>>,
}

// SAFETY: Disk registration is owned; C serializes unpublication and reference
// release. T is Send+Sync, and the foreign Arc remains owned by the final disk.
unsafe impl<T: Operations> Send for BioDisk<T> {}

impl<T: Operations> BioDisk<T> {
    /// Allocates and publishes a disk, retaining `data` until its final release.
    pub fn new(data: Arc<T>, config: DiskConfig, name: fmt::Arguments<'_>) -> Result<Self> {
        if config.major > i32::MAX as u32
            || config.first_minor > i32::MAX as u32
            || config.minors > i32::MAX as u32
            || config.physical_block_size < 512
            || config.physical_block_size as usize > PAGE_SIZE
            || !config.physical_block_size.is_power_of_two()
        {
            return Err(EINVAL);
        }
        // SAFETY: queue_limits consists of integers and pointers; all-zero is
        // a valid initial value, as in C bio disk drivers. Core validates limits.
        let mut limits: bindings::queue_limits = unsafe { core::mem::zeroed() };
        limits.logical_block_size = 512;
        limits.physical_block_size = config.physical_block_size;
        limits.discard_granularity = config.discard_granularity;
        limits.max_hw_discard_sectors = config.max_discard_sectors;
        limits.max_discard_segments = config.max_discard_segments;
        if config.synchronous {
            // SAFETY: This macro wrapper has no memory accesses or preconditions.
            limits.features |= unsafe { bindings::blk_feat_synchronous() };
        }
        if config.nowait {
            // SAFETY: This macro wrapper has no memory accesses or preconditions.
            limits.features |= unsafe { bindings::blk_feat_nowait() };
        }
        // SAFETY: limits is initialized and writable, -1 means NUMA_NO_NODE,
        // and the lock class is static. Allocation is allowed to sleep here.
        let disk = from_err_ptr(unsafe {
            bindings::__blk_alloc_disk(&mut limits, -1, static_lock_class!().as_ptr())
        })?;
        let cleanup_disk = ScopeGuard::new(|| {
            // SAFETY: This guard owns the unregistered disk's initial reference.
            unsafe { bindings::put_disk(disk) };
        });
        // SAFETY: This disk is private and initialized; its name is writable.
        let mut writer =
            NullTerminatedFormatter::new(unsafe { &mut (*disk).disk_name }).ok_or(EINVAL)?;
        writer.write_fmt(name)?;
        let private = data.into_foreign();
        let cleanup_data = ScopeGuard::new(|| {
            // SAFETY: Before successful publication, free_disk is not called
            // (GD_ADDED is unset). This guard owns exactly the foreign Arc.
            drop(unsafe { Arc::<T>::from_foreign(private) });
        });
        // SAFETY: The unpublished disk is exclusively owned. Values were range
        // checked above and the vtable/private pointer have matching T types.
        unsafe {
            (*disk).major = config.major as i32;
            (*disk).first_minor = config.first_minor as i32;
            (*disk).minors = config.minors as i32;
            (*disk).private_data = private;
            (*disk).fops = &Self::VTABLE;
            bindings::set_capacity(disk, config.capacity_sectors);
        }
        // SAFETY: Disk is fully initialized and owns valid callback state.
        // Partition discovery may submit I/O here, so state is already installed.
        to_result(unsafe { bindings::device_add_disk(ptr::null_mut(), disk, ptr::null_mut()) })?;
        // Successful publication sets GD_ADDED; free_disk now owns private.
        cleanup_data.dismiss();
        cleanup_disk.dismiss();
        Ok(Self {
            disk,
            _driver: PhantomData,
        })
    }

    const VTABLE: bindings::block_device_operations = bindings::block_device_operations {
        submit_bio: Some(Self::submit_callback),
        free_disk: Some(Self::free_callback),
        owner: T::OWNER.as_ptr(),
        // SAFETY: All remaining fields are optional function pointers or raw
        // pointers. Zero disables unsupported callbacks, matching a C initializer.
        ..unsafe { core::mem::zeroed() }
    };

    /// Called only by the block core for a disk registered with this vtable.
    unsafe extern "C" fn submit_callback(raw: *mut bindings::bio) {
        // SAFETY: The block core supplies a submitted bio with a live bdev/disk;
        // the vtable is installed only on disks with this typed private Arc.
        let private = unsafe { (*(*(*raw).bi_bdev).bd_disk).private_data };
        // SAFETY: The block core retains the disk at callback entry. Clone the
        // Arc before calling the driver so completion cannot invalidate our
        // state reference, even if it triggers the final disk release.
        let data = Arc::<T>::from(unsafe { Arc::<T>::borrow(private) });
        // SAFETY: The block core transfers the driver's sole completion duty.
        // No other wrapper is constructed for this submission.
        let bio = unsafe { SubmittedBio::from_raw(raw) };
        data.submit(bio);
    }

    /// Called once by disk_release, after all users of its private state end.
    unsafe extern "C" fn free_callback(disk: *mut bindings::gendisk) {
        // SAFETY: Successful registration handed exactly one Arc to this
        // callback. Failure before GD_ADDED uses the construction guard instead.
        let private = unsafe { (*disk).private_data };
        // SAFETY: The final disk release is the only successful-path consumer.
        drop(unsafe { Arc::<T>::from_foreign(private) });
    }
}

impl<T: Operations> Drop for BioDisk<T> {
    fn drop(&mut self) {
        // SAFETY: The type invariant supplies a published disk and the initial
        // reference. del_gendisk prevents new I/O, then put_disk releases this
        // handle. Existing references retain private data until free_callback.
        unsafe {
            bindings::del_gendisk(self.disk);
            bindings::put_disk(self.disk);
        }
    }
}
