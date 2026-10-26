// SPDX-License-Identifier: BSD-2-Clause
//! VM-only x86_64 initramfs driver for the integer-square-root module ABI probe.
#![no_std]
#![no_main]

#[cfg(not(target_arch = "x86_64"))]
compile_error!("The module smoke init currently supports x86_64 only");

use core::arch::{asm, global_asm};
use core::panic::PanicInfo;

// x86_64 numbers: linux/arch/x86/entry/syscalls/syscall_64.tbl.
const SYS_WRITE: usize = 1;
const SYS_CLOSE: usize = 3;
const SYS_PAUSE: usize = 34;
const SYS_GETPID: usize = 39;
const SYS_EXIT: usize = 60;
const SYS_REBOOT: usize = 169;
const SYS_DELETE_MODULE: usize = 176;
const SYS_OPENAT: usize = 257;
const SYS_FINIT_MODULE: usize = 313;
const AT_FDCWD: usize = (-100isize) as usize;
const O_NONBLOCK: usize = 1 << 11;

// The ELF entry stack is not a C function call frame. Align it and call Rust
// using the SysV AMD64 ABI rather than exposing an ordinary Rust function as
// the ELF entry point directly. No arguments/environment are needed.
global_asm!(
    ".global _start",
    ".type _start,@function",
    "_start:",
    "xor rbp, rbp",
    "and rsp, -16",
    "call rusix_init",
    "ud2",
    ".size _start, .-_start",
);

/// Execute an x86_64 Linux syscall with at most four arguments.
///
/// # Safety
/// The caller must supply valid userspace pointer arguments, where applicable,
/// for the selected syscall and keep their pointees live for its duration.
unsafe fn syscall4(number: usize, a: usize, b: usize, c: usize, d: usize) -> isize {
    let result: isize;
    // SAFETY: The wrapper contract covers argument validity. Register bindings
    // follow the Linux x86_64 syscall ABI; syscall clobbers rcx and r11. Memory
    // is not marked readonly/nomem because the kernel may read/write arguments.
    unsafe {
        asm!(
            "syscall",
            inlateout("rax") number => result,
            in("rdi") a,
            in("rsi") b,
            in("rdx") c,
            in("r10") d,
            lateout("rcx") _,
            lateout("r11") _,
            options(nostack),
        );
    }
    result
}

fn write(fd: usize, bytes: &[u8]) {
    let mut remaining = bytes;
    while !remaining.is_empty() {
        // SAFETY: remaining is a live readable slice; write cannot outlive this
        // syscall. No mutable Rust alias to its memory is exposed.
        let result = unsafe {
            syscall4(
                SYS_WRITE,
                fd,
                remaining.as_ptr() as usize,
                remaining.len(),
                0,
            )
        };
        if result == -4 {
            continue; // EINTR: retry the same bytes.
        }
        if result <= 0 || result as usize > remaining.len() {
            return;
        }
        remaining = &remaining[result as usize..];
    }
}

fn fail(fd: usize, stage: &[u8], error: isize) -> ! {
    write(fd, b"RUSIX_INIT_FAIL stage=");
    write(fd, stage);
    write(fd, b" errno_hex=");
    let magnitude = error.unsigned_abs();
    for shift in (0..16).rev() {
        let digit = ((magnitude >> (shift * 4)) & 15) as u8;
        let byte = if digit < 10 {
            b'0' + digit
        } else {
            b'a' + digit - 10
        };
        write(fd, &[byte]);
    }
    write(fd, b"\n");
    reboot(fd)
}

fn reboot(fd: usize) -> ! {
    // SAFETY: reboot uses scalar constants from include/uapi/linux/reboot.h;
    // RESTART does not dereference its null fourth argument. Only PID 1 reaches
    // this function through rusix_init's guard (or the guarded panic handler).
    let result = unsafe { syscall4(SYS_REBOOT, 0xfee1dead, 672274793, 0x01234567, 0) };
    if result < 0 {
        write(fd, b"RUSIX_INIT_FAIL stage=reboot\n");
    }
    // Never return from PID 1 or busy-spin if a reboot is unavailable. The host
    // VM runner must impose its own timeout and require every success marker.
    loop {
        // SAFETY: pause takes no arguments and exposes no memory.
        unsafe { syscall4(SYS_PAUSE, 0, 0, 0, 0) };
    }
}

fn exit_non_init() -> ! {
    // SAFETY: exit takes a scalar status and terminates only this process.
    unsafe { syscall4(SYS_EXIT, 125, 0, 0, 0) };
    loop {
        core::hint::spin_loop();
    }
}

// SAFETY: _start is the only caller of this uniquely named entry symbol and
// establishes the required C ABI stack alignment. The function never returns.
#[unsafe(no_mangle)]
pub extern "C" fn rusix_init() -> ! {
    // SAFETY: getpid takes no arguments and exposes no memory.
    if unsafe { syscall4(SYS_GETPID, 0, 0, 0, 0) } != 1 {
        write(2, b"RUSIX_INIT_REFUSED: VM PID 1 only\n");
        exit_non_init();
    }

    // SAFETY: the path is a static NUL-terminated string; O_WRONLY needs no mode.
    let console = unsafe {
        syscall4(
            SYS_OPENAT,
            AT_FDCWD,
            b"/dev/console\0".as_ptr() as usize,
            1,
            0,
        )
    };
    if console < 0 {
        fail(1, b"open-console", console);
    }
    let console = console as usize;
    write(console, b"RUSIX_INIT_START\n");

    // SAFETY: the path is static and NUL-terminated; O_RDONLY needs no mode.
    let module = unsafe {
        syscall4(
            SYS_OPENAT,
            AT_FDCWD,
            b"/int_sqrt_probe.ko\0".as_ptr() as usize,
            0,
            0,
        )
    };
    if module < 0 {
        fail(console, b"open-module", module);
    }
    // SAFETY: module is an open readable fd, the parameter string is static and
    // NUL-terminated, and flags=0 enforces normal vermagic/version checks.
    let loaded = unsafe {
        syscall4(
            SYS_FINIT_MODULE,
            module as usize,
            b"\0".as_ptr() as usize,
            0,
            0,
        )
    };
    // SAFETY: close takes the owned file descriptor and exposes no memory.
    let closed = unsafe { syscall4(SYS_CLOSE, module as usize, 0, 0, 0) };
    if loaded != 0 {
        fail(console, b"finit-module", loaded);
    }
    if closed != 0 {
        fail(console, b"close-module", closed);
    }
    write(console, b"RUSIX_INIT_LOAD_PASS\n");

    // SAFETY: the module name is static and NUL-terminated. O_NONBLOCK requests
    // failure if busy, not forced removal; no force-unload flag is supplied.
    let unloaded = unsafe {
        syscall4(
            SYS_DELETE_MODULE,
            b"int_sqrt_probe\0".as_ptr() as usize,
            O_NONBLOCK,
            0,
            0,
        )
    };
    if unloaded != 0 {
        fail(console, b"delete-module", unloaded);
    }
    write(console, b"RUSIX_INIT_UNLOAD_PASS\n");
    write(console, b"RUSIX_MODULE_SMOKE_PASS\n");
    reboot(console)
}

#[panic_handler]
fn panic(_info: &PanicInfo<'_>) -> ! {
    write(2, b"RUSIX_INIT_FAIL stage=panic\n");
    // SAFETY: getpid has no arguments; keep accidental non-init execution from
    // ever reaching the VM-only reboot path even on panic.
    if unsafe { syscall4(SYS_GETPID, 0, 0, 0, 0) } != 1 {
        exit_non_init();
    }
    reboot(2)
}
