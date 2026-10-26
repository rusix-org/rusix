// SPDX-License-Identifier: GPL-2.0-only
//! Builtin BRD parameter storage and metadata over the original C parameter ops.
//! Parsing/getting and mutex primitives remain C; normalization remains in BRD.

use core::ptr::{addr_of, null_mut};
use kernel::{
    bindings,
    ffi::{c_int, c_ulong},
    types::Opaque,
};

#[cfg(MODULE)]
compile_error!("BRD parameter storage currently supports builtin BRD only");

#[repr(transparent)]
struct ParameterValue<T>(Opaque<T>);
// SAFETY: these private statics have permanent addresses. Boot setters and
// runtime readers/normalization use the global C parameter mutex. Legacy boot
// setup has exclusive access before concurrent publication. No safe reference
// to the mutable scalar is exposed; supported types have no destruction.
unsafe impl<T> Sync for ParameterValue<T> {}

// SAFETY: preserve externally named C scalar objects, exact width/alignment.
#[unsafe(no_mangle)]
static rusix_brd_rd_nr: ParameterValue<c_int> =
    ParameterValue(Opaque::new(bindings::CONFIG_BLK_DEV_RAM_COUNT as c_int));
// SAFETY: include/linux/initrd.h names this writable unsigned-long object.
#[unsafe(no_mangle)]
static rd_size: ParameterValue<c_ulong> =
    ParameterValue(Opaque::new(bindings::CONFIG_BLK_DEV_RAM_SIZE as c_ulong));
// SAFETY: unchanged scalar ABI; only its allocation owner changes.
#[unsafe(no_mangle)]
static rusix_brd_max_part: ParameterValue<c_int> = ParameterValue(Opaque::new(1));

// Metadata is immutable on the supported target; pointers address permanent
// scalars/ops/strings. Its safe constructor is deliberately not public.
#[repr(transparent)]
struct Parameter(bindings::kernel_param);
// SAFETY: record itself is never mutated; pointed-to arguments have the
// synchronization above. No safe parameter-value borrowing is exposed.
unsafe impl Sync for Parameter {}

// SAFETY: retain exactly three naturally aligned records for linker scanning.
#[used]
#[unsafe(link_section = "__param")]
static PARAMETERS: [Parameter; 3] = [
    Parameter(bindings::kernel_param {
        name: c"brd.rd_nr".as_ptr().cast(),
        mod_: null_mut(),
        // SAFETY: existing permanent C operations, matched to c_int storage.
        ops: unsafe { addr_of!(bindings::param_ops_int) },
        perm: 0o444,
        level: -1,
        flags: 0,
        __bindgen_anon_1: bindings::kernel_param__bindgen_ty_1 {
            arg: rusix_brd_rd_nr.0.get().cast(),
        },
    }),
    Parameter(bindings::kernel_param {
        name: c"brd.rd_size".as_ptr().cast(),
        mod_: null_mut(),
        // SAFETY: existing permanent C operations, matched to c_ulong storage.
        ops: unsafe { addr_of!(bindings::param_ops_ulong) },
        perm: 0o444,
        level: -1,
        flags: 0,
        __bindgen_anon_1: bindings::kernel_param__bindgen_ty_1 {
            arg: rd_size.0.get().cast(),
        },
    }),
    Parameter(bindings::kernel_param {
        name: c"brd.max_part".as_ptr().cast(),
        mod_: null_mut(),
        // SAFETY: existing permanent C operations, matched to c_int storage.
        ops: unsafe { addr_of!(bindings::param_ops_int) },
        perm: 0o444,
        level: -1,
        flags: 0,
        __bindgen_anon_1: bindings::kernel_param__bindgen_ty_1 {
            arg: rusix_brd_max_part.0.get().cast(),
        },
    }),
];

macro_rules! info {
    ($name:ident, $bytes:literal) => {
        // SAFETY: permanent immutable byte-aligned NUL-terminated modinfo.
        #[used]
        #[unsafe(link_section = ".modinfo")]
        static $name: [u8; $bytes.len()] = *$bytes;
    };
}
info!(RD_NR_TYPE, b"brd.parmtype=rd_nr:int\0");
info!(
    RD_NR_DESC,
    b"brd.parm=rd_nr:Maximum number of brd devices\0"
);
info!(RD_SIZE_TYPE, b"brd.parmtype=rd_size:ulong\0");
info!(
    RD_SIZE_DESC,
    b"brd.parm=rd_size:Size of each RAM disk in kbytes.\0"
);
info!(MAX_PART_TYPE, b"brd.parmtype=max_part:int\0");
info!(
    MAX_PART_DESC,
    b"brd.parm=max_part:Num Minors to reserve between devices\0"
);

// SAFETY: string referenced only by the init-only setup record, byte alignment.
#[used]
#[unsafe(link_section = ".init.rodata")]
static LEGACY_NAME: [u8; 14] = *b"ramdisk_size=\0";

#[repr(transparent)]
struct Setup(Opaque<bindings::builtin_init::obs_kernel_param>);
// SAFETY: kernel boot scans this permanent-address init record before freeing
// init memory. No concurrent mutation or access after init; no safe API exposed.
unsafe impl Sync for Setup {}

// SAFETY: exact original mutable C init setup section and natural record alignment;
// callback stays in its EXISTING section, string/record die together after boot.
#[used]
#[unsafe(link_section = ".init.setup")]
static LEGACY_SETUP: Setup = Setup(Opaque::new(bindings::builtin_init::obs_kernel_param {
    str: LEGACY_NAME.as_ptr().cast(),
    setup_func: Some(super::rusix_brd_legacy_size),
    early: 0,
}));

// These assertions express transparent ABI, not fixed host sizes.
const _: () =
    assert!(core::mem::size_of::<ParameterValue<c_ulong>>() == core::mem::size_of::<c_ulong>());
const _: () =
    assert!(core::mem::align_of::<ParameterValue<c_ulong>>() == core::mem::align_of::<c_ulong>());
const _: () =
    assert!(core::mem::size_of::<ParameterValue<c_int>>() == core::mem::size_of::<c_int>());
const _: () =
    assert!(core::mem::align_of::<ParameterValue<c_int>>() == core::mem::align_of::<c_int>());
const _: () =
    assert!(core::mem::size_of::<Parameter>() == core::mem::size_of::<bindings::kernel_param>());
const _: () =
    assert!(core::mem::align_of::<Parameter>() == core::mem::align_of::<bindings::kernel_param>());
const _: () = assert!(
    core::mem::size_of::<Setup>()
        == core::mem::size_of::<bindings::builtin_init::obs_kernel_param>()
);
const _: () = assert!(
    core::mem::align_of::<Setup>()
        == core::mem::align_of::<bindings::builtin_init::obs_kernel_param>()
);

/// Owns the original builtin global parameter mutex, not a new Rust lock.
/// Keep private to the BRD module and do not transfer across tasks.
pub(super) struct Guard(core::marker::PhantomData<*mut ()>);
impl Guard {
    /// # Safety
    /// Sleepable BRD init context only; SYSFS=n additionally requires exclusive
    /// access after boot parsing, before publication (the original no-op case).
    pub(super) unsafe fn lock() -> Self {
        #[cfg(CONFIG_SYSFS)]
        // SAFETY: builtin NULL selects global param_lock; sleepable init caller.
        unsafe {
            bindings::kernel_param_lock(null_mut())
        };
        Self(core::marker::PhantomData)
    }

    pub(super) fn snapshot(&self) -> (c_int, c_ulong, c_int) {
        // SAFETY: this guard holds the same mutex as C parse/sysfs accesses.
        // SYSFS=n follows original no-op lock under exclusive init use.
        unsafe {
            (
                rusix_brd_rd_nr.0.get().read(),
                rd_size.0.get().read(),
                rusix_brd_max_part.0.get().read(),
            )
        }
    }

    pub(super) fn set_max_part(&self, value: c_int) {
        // SAFETY: same mutex excludes C readers; unchanged init-only normalization.
        unsafe { rusix_brd_max_part.0.get().write(value) };
    }
}
impl Drop for Guard {
    fn drop(&mut self) {
        #[cfg(CONFIG_SYSFS)]
        // SAFETY: guard owns the exact builtin parameter mutex on this task.
        unsafe {
            bindings::kernel_param_unlock(null_mut())
        };
    }
}

/// # Safety
/// Only the existing legacy setup callback during exclusive boot parsing may
/// call this; no published sysfs/driver access or concurrent parser may exist.
pub(super) unsafe fn legacy_write_size(value: c_ulong) {
    // SAFETY: caller guarantees exclusive boot access, preserving C setup policy.
    unsafe { rd_size.0.get().write(value) };
}
