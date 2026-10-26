// SPDX-License-Identifier: GPL-2.0-only
// Rust implementation of drivers/block/brd.c.
// Original BRD: Copyright (C) 2007 Nick Piggin and Novell Inc.; see brd.c.

//! RAM-backed bio block driver, retaining the pinned Linux BRD device contract.

use core::num::NonZeroU32;
use kernel::{
    bindings,
    block::{
        bio::{Operation, Status, SubmittedBio},
        bio_disk::{BioDisk, DiskConfig, Operations},
    },
    c_str, debugfs,
    page::PAGE_SIZE,
    prelude::*,
    str::CString,
    sync::{Arc, Mutex},
};

#[path = "brd_rust/store.rs"]
mod store;
use store::Store;

module! {
    type: RustBrd,
    name: "brd",
    description: "Rust RAM-backed block device driver",
    license: "GPL",
    alias: ["rd", "block-major-1-*"],
}

const RAMDISK_MAJOR: u32 = 1;
const MINOR_BITS: u32 = 20;
const MINOR_COUNT: u32 = 1 << MINOR_BITS;
const MINOR_MASK: u32 = MINOR_COUNT - 1;
const MAX_PARTITIONS: u32 = 256;
const SECTOR_SHIFT: u32 = 9;
const PAGE_SECTORS: u64 = (PAGE_SIZE >> SECTOR_SHIFT) as u64;

extern "C" {
    static mut rusix_brd_rd_nr: c_int;
    static mut rd_size: c_ulong;
    static mut rusix_brd_max_part: c_int;
    fn rusix_brd_params_lock();
    fn rusix_brd_params_unlock();
}

struct ParameterGuard;

impl ParameterGuard {
    fn lock() -> Self {
        // SAFETY: This wrapper uses this module's own parameter lock. The
        // matching guard unlocks it; module init runs in sleepable context.
        unsafe { rusix_brd_params_lock() };
        Self
    }
}

impl Drop for ParameterGuard {
    fn drop(&mut self) {
        // SAFETY: This guard owns the parameter lock taken by `lock`.
        unsafe { rusix_brd_params_unlock() };
    }
}

#[derive(Clone, Copy)]
struct Parameters {
    preallocate: c_int,
    capacity_sectors: u64,
    minors: NonZeroU32,
}

impl Parameters {
    fn read() -> Result<Self> {
        let _guard = ParameterGuard::lock();
        // SAFETY: Kernel parameter parsing and sysfs readers use the same
        // lock. Parameters are read-only after initialization (mode 0444).
        let (preallocate, size, requested) =
            unsafe { (rusix_brd_rd_nr, rd_size, rusix_brd_max_part) };
        let minors = NonZeroU32::new(normalize_minors(requested)?).ok_or(EINVAL)?;
        // SAFETY: The parameter lock excludes sysfs readers during this
        // initialization-time update; later driver accesses use this snapshot.
        unsafe { rusix_brd_max_part = minors.get() as c_int };
        Ok(Self {
            preallocate,
            // The C expression multiplies unsigned long before converting to
            // sector_t, so preserve its native-word wrapping behavior.
            capacity_sectors: size.wrapping_mul(2) as u64,
            minors,
        })
    }
}

fn normalize_minors(requested: c_int) -> Result<u32> {
    let mut value = if requested == 0 { 1 } else { requested };
    if MINOR_COUNT % (value as u32) != 0 {
        let bits = u32::BITS - (value as u32).leading_zeros();
        value = (1u64 << bits) as c_int;
    }
    // On the declared 64-bit targets, negative inputs narrow 1UL << 32 to
    // zero. The C probe would subsequently divide by zero; retain a guard at
    // that undefined-behavior boundary rather than introducing a Rust panic.
    if value == 0 {
        return Err(EINVAL);
    }
    // Positive inputs >= 2^30 narrow 1UL << 31 to INT_MIN. C's comparison
    // here is signed, so they must NOT be clamped or rejected at initialization.
    // Preserve their bit pattern: parameter sysfs reads INT_MIN, major 1 remains
    // registered, and the probe's unsigned divisor is 0x80000000. Disk creation
    // rejects that out-of-range minor count, so opens fail with ENXIO.
    if value > MAX_PARTITIONS as c_int {
        pr_info!("max_part can't exceed {}, resetting it\n", MAX_PARTITIONS);
        value = MAX_PARTITIONS as c_int;
    }
    Ok(value as u32)
}

/// Preserve the legacy simple_strtol(value, NULL, 0) conversion, including
/// prefix parsing, trailing garbage and native-word wrapping. Normal module
/// parameters continue to use the kernel's standard typed parameter metadata.
fn legacy_size(value: &[u8]) -> c_ulong {
    let (negative, digits) = match value.split_first() {
        Some((b'-', rest)) => (true, rest),
        _ => (false, value),
    };
    let (base, digits) = match digits {
        [b'0', b'x' | b'X', first, ..] if hex_digit(*first).is_some() => (16, &digits[2..]),
        [b'0', ..] => (8, digits),
        _ => (10, digits),
    };
    let mut result = 0u64;
    for &byte in digits {
        let Some(digit) = hex_digit(byte) else { break };
        if digit >= base {
            break;
        }
        result = result.wrapping_mul(base as u64).wrapping_add(digit as u64);
    }
    let result = result as c_ulong;
    if negative {
        result.wrapping_neg()
    } else {
        result
    }
}

fn hex_digit(byte: u8) -> Option<u32> {
    match byte {
        b'0'..=b'9' => Some((byte - b'0') as u32),
        b'a'..=b'f' => Some((byte - b'a' + 10) as u32),
        b'A'..=b'F' => Some((byte - b'A' + 10) as u32),
        _ => None,
    }
}

#[cfg(not(MODULE))]
#[no_mangle]
unsafe extern "C" fn rusix_brd_legacy_size(value: *mut c_char) -> c_int {
    // SAFETY: The __setup ABI supplies a valid NUL-terminated command-line
    // string during single-threaded boot parsing, before driver initialization.
    let value = unsafe { CStr::from_char_ptr(value) };
    // SAFETY: Legacy boot parsing runs before the driver or sysfs parameter
    // readers are published, so this write cannot race another access.
    unsafe { rd_size = legacy_size(value.as_bytes()) };
    1
}

#[pin_data]
struct Device {
    #[pin]
    store: Store,
    capacity_sectors: u64,
}

impl Device {
    fn new(capacity_sectors: u64) -> impl PinInit<Self, Error> {
        try_pin_init! {
            Self {
                store <- Store::new(),
                capacity_sectors,
            }
        }
    }

    fn transfer(&self, bio: &mut SubmittedBio) -> Result {
        let write = bio.operation() == Operation::Write;
        let flags = if bio.nowait() { GFP_NOWAIT } else { GFP_KERNEL };
        while !bio.is_empty() {
            let sector = bio.sector();
            let index = (sector / PAGE_SECTORS) as usize;
            let offset = ((sector % PAGE_SECTORS) << SECTOR_SHIFT) as usize;
            let page = if write {
                Some(self.store.get_or_insert(index, flags)?)
            } else {
                self.store.lookup(index)
            };
            let count = {
                let mut segment = bio.segment()?;
                let count = segment.len().min(PAGE_SIZE - offset);
                if let Some(page) = page {
                    page.with_page(|backing| {
                        // SAFETY: The backing page belongs only to this Store
                        // slot and is accessed under its exclusive page lock.
                        // It is distinct from the bio's caller-owned pages.
                        // Bounds are capped against both page boundaries.
                        unsafe {
                            if write {
                                segment.copy_to_page(backing, offset, count)
                            } else {
                                segment.copy_from_page(backing, offset, count)
                            }
                        }
                    })?;
                } else {
                    segment.zero(count)?;
                }
                count
            };
            bio.advance(count as u32)?;
        }
        Ok(())
    }
}

// SAFETY: OWNER names this module's generated module descriptor. Device state
// is Arc-owned by the disk until free_disk, and all mutable backing-store state
// is synchronized by Store. Callback code remains resident for the disk owner.
unsafe impl Operations for Device {
    const OWNER: &'static ThisModule = &THIS_MODULE;

    fn submit(&self, mut bio: SubmittedBio) {
        if bio.operation() == Operation::Discard {
            let start = bio.sector();
            let end = start.wrapping_add((bio.len() >> SECTOR_SHIFT) as u64);
            let first = start.wrapping_add(PAGE_SECTORS - 1) / PAGE_SECTORS;
            let last = (end / PAGE_SECTORS).min(self.capacity_sectors / PAGE_SECTORS);
            if first < last {
                self.store.discard(first as usize, last as usize);
            }
            bio.complete(Status::Ok);
            return;
        }
        let status = match self.transfer(&mut bio) {
            Ok(()) => Status::Ok,
            Err(error) if error == ENOMEM && bio.nowait() => Status::WouldBlock,
            Err(_) => Status::IoError,
        };
        bio.complete(status);
    }
}

struct PageCount(Arc<Device>);

impl debugfs::Writer for PageCount {
    fn write(&self, formatter: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        writeln!(formatter, "{}", self.0.store.count())
    }
}

struct Registration {
    // Remove the debugfs callback before releasing our disk registration.
    _counter: Option<Pin<KBox<debugfs::File<PageCount>>>>,
    _disk: BioDisk<Device>,
}

struct Entry {
    number: u32,
    // None reserves the number while add_disk runs without the registry lock.
    registration: Option<Registration>,
}

#[pin_data]
struct Registry {
    #[pin]
    devices: Mutex<KVec<Entry>>,
    debugfs: debugfs::Dir,
    parameters: Parameters,
}

impl Registry {
    fn new(parameters: Parameters) -> impl PinInit<Self, Error> {
        try_pin_init! {
            Self {
                devices <- kernel::new_mutex!(KVec::new()),
                debugfs: debugfs::Dir::new(c_str!("ramdisk_pages")),
                parameters,
            }
        }
    }

    fn register(&self, number: u32) -> Result {
        {
            let mut entries = self.devices.lock();
            if entries.iter().any(|entry| entry.number == number) {
                return Err(EEXIST);
            }
            entries.push(
                Entry {
                    number,
                    registration: None,
                },
                GFP_KERNEL,
            )?;
        }
        let registration = self.build_device(number);
        let mut entries = self.devices.lock();
        // The reserved entry cannot be removed by another registration. Module
        // teardown first unregisters the major and waits for probe callbacks.
        if let Some(index) = entries.iter().position(|entry| entry.number == number) {
            match registration {
                Ok(registration) => entries[index].registration = Some(registration),
                Err(error) => {
                    let _ = entries.remove(index);
                    return Err(error);
                }
            }
            Ok(())
        } else {
            // No registration is leaked even if the reservation is absent.
            drop(registration);
            Err(ENODEV)
        }
    }

    fn build_device(&self, number: u32) -> Result<Registration> {
        let device = Arc::pin_init(Device::new(self.parameters.capacity_sectors), GFP_KERNEL)?;
        let disk = BioDisk::new(
            device.clone(),
            DiskConfig {
                major: RAMDISK_MAJOR,
                first_minor: number.wrapping_mul(self.parameters.minors.get()),
                minors: self.parameters.minors.get(),
                capacity_sectors: self.parameters.capacity_sectors,
                physical_block_size: PAGE_SIZE as u32,
                discard_granularity: PAGE_SIZE as u32,
                max_discard_sectors: u32::MAX,
                max_discard_segments: 1,
                synchronous: true,
                nowait: true,
            },
            fmt!("ram{number}"),
        )?;
        // Debugfs is optional and its allocation failure must not reject a disk.
        let counter = CString::try_from_fmt(fmt!("ram{number}"))
            .ok()
            .and_then(|name| {
                KBox::pin_init(
                    self.debugfs.read_only_file(&name, PageCount(device)),
                    GFP_KERNEL,
                )
                .ok()
            });
        Ok(Registration {
            _counter: counter,
            _disk: disk,
        })
    }

    fn shutdown(&self) {
        // Drop handles outside the registry lock: deletion may wait for I/O or
        // debugfs readers. No probe remains after unregister_blkdev returns.
        let devices = core::mem::take(&mut *self.devices.lock());
        drop(devices);
    }
}

kernel::sync::global_lock! {
    // SAFETY: Initialized once in module init, before registering the major or
    // exposing any callback. The static storage is fresh on each module load.
    unsafe(uninit) static REGISTRY: Mutex<Option<Arc<Registry>>> = None;
}

unsafe extern "C" fn probe(device: bindings::dev_t) {
    let registry = REGISTRY.lock().clone();
    if let Some(registry) = registry {
        let minor = device & MINOR_MASK;
        let number = minor / registry.parameters.minors.get();
        // Like the C probe callback, allocation failures are observed by the
        // caller as failure to instantiate the device, not returned via this ABI.
        let _ = registry.register(number);
    }
}

struct RustBrd {
    registry: Arc<Registry>,
}

impl kernel::Module for RustBrd {
    fn init(_module: &'static ThisModule) -> Result<Self> {
        let parameters = Parameters::read()?;
        let registry = Arc::pin_init(Registry::new(parameters), GFP_KERNEL)?;
        // SAFETY: Module initialization is called once before probe registration.
        unsafe { REGISTRY.init() };
        *REGISTRY.lock() = Some(registry.clone());
        // SAFETY: Strings and callback have module-static lifetime. The callback
        // clones Arc state under REGISTRY; it does not retain borrowed state.
        let status = unsafe {
            bindings::__register_blkdev(RAMDISK_MAJOR, c_str!("ramdisk").as_char_ptr(), Some(probe))
        };
        if status != 0 {
            *REGISTRY.lock() = None;
            // Preserve the C driver's registration-error mapping.
            return Err(EIO);
        }
        // The pinned C initializer deliberately ignores each preallocation
        // failure. On-demand creation remains available for missing devices.
        for number in 0..parameters.preallocate {
            let _ = registry.register(number as u32);
        }
        pr_info!("Rust RAM disk driver loaded\n");
        Ok(Self { registry })
    }
}

impl Drop for RustBrd {
    fn drop(&mut self) {
        // SAFETY: This module successfully registered this major and name.
        // The kernel major_names_lock serializes unregister with probe callbacks;
        // do not hold REGISTRY while waiting for it (probe acquires REGISTRY).
        unsafe { bindings::unregister_blkdev(RAMDISK_MAJOR, c_str!("ramdisk").as_char_ptr()) };
        *REGISTRY.lock() = None;
        self.registry.shutdown();
        pr_info!("Rust RAM disk driver unloaded\n");
    }
}

#[kunit_tests(rusix_brd_policy)]
mod tests {
    use super::*;

    #[test]
    fn minor_count_preserves_defined_normalization() {
        for (input, expected) in [
            (0, 1),
            (1, 1),
            (2, 2),
            (3, 4),
            (7, 8),
            (128, 128),
            (129, 256),
            (256, 256),
            (257, 256),
            (1 << 20, 256),
            ((1 << 30) - 1, 256),
            (1 << 30, 1u32 << 31),
            ((1 << 30) + 1, 1u32 << 31),
            (c_int::MAX, 1u32 << 31),
        ] {
            assert_eq!(normalize_minors(input), Ok(expected));
        }
    }

    #[test]
    fn invalid_minor_normalization_is_rejected() {
        // Negative inputs normalize to zero on the declared 64-bit targets;
        // C's on-demand path then has undefined division-by-zero behavior.
        // This guard does not reject the defined high-positive normalization.
        for input in [-1, -2, c_int::MIN] {
            assert_eq!(normalize_minors(input), Err(EINVAL));
        }
    }

    #[test]
    fn legacy_size_retains_prefix_and_wrapping_semantics() {
        for (input, expected) in [
            (&b""[..], 0),
            (&b"64"[..], 64),
            (&b"010"[..], 8),
            (&b"0x10tail"[..], 16),
            (&b"0Xff"[..], 255),
            (&b"09"[..], 0),
            (&b"0xg"[..], 0),
            (&b"+12"[..], 0),
            (&b" 12"[..], 0),
            (&b"12tail"[..], 12),
            (&b"-1"[..], c_ulong::MAX),
            (&b"18446744073709551616"[..], 0),
            (&b"-18446744073709551615"[..], 1),
        ] {
            assert_eq!(legacy_size(input), expected);
        }
    }
}
