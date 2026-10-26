// SPDX-License-Identifier: GPL-2.0-only
//! Guest-only PID 1. Never run this executable on the host or in a container.
use std::{
    fs,
    io::{self, Write},
    process::{self, Command},
    thread,
    time::Duration,
};

const TOKEN: &str = "rusix.mm_dup_mmap_probe=1";
unsafe extern "C" {
    fn mount(
        source: *const u8,
        target: *const u8,
        filesystem: *const u8,
        flags: usize,
        data: *const u8,
    ) -> i32;
    fn prctl(option: i32, ...) -> i32;
    fn sync();
    fn reboot(command: i32) -> i32;
}

fn run() -> io::Result<()> {
    // SAFETY: NUL-terminated static strings, valid null optional data, and the
    // caller is PID 1. The guest token is checked immediately after proc mounts.
    if unsafe {
        mount(
            b"proc\0".as_ptr(),
            b"/proc\0".as_ptr(),
            b"proc\0".as_ptr(),
            2 | 4 | 8,
            std::ptr::null(),
        )
    } != 0
    {
        return Err(io::Error::last_os_error());
    }
    if fs::read_to_string("/proc/cmdline")?
        .split_whitespace()
        .filter(|s| *s == TOKEN)
        .count()
        != 1
    {
        return Err(io::Error::other(
            "missing or repeated guest authorization token",
        ));
    }
    // SAFETY: PR_SET_NAME reads at most 16 bytes from this live static string.
    if unsafe { prctl(15, b"rusix-dup-init\0".as_ptr(), 0usize, 0usize, 0usize) } != 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: Exact guest token and PID1 identity have been checked. /work
    // is supplied by the initramfs; mount only this guest-private tmpfs.
    if unsafe {
        mount(
            b"tmpfs\0".as_ptr(),
            b"/work\0".as_ptr(),
            b"tmpfs\0".as_ptr(),
            2 | 4 | 8,
            b"size=4m,mode=0700\0".as_ptr(),
        )
    } != 0
    {
        return Err(io::Error::last_os_error());
    }
    let status = Command::new("/probe")
        .env_clear()
        .env("PATH", "/")
        .env("LC_ALL", "C")
        .env("TZ", "UTC")
        .status()?;
    if !status.success() {
        return Err(io::Error::other(format!("probe exited {status}")));
    }
    Ok(())
}

fn main() {
    if process::id() != 1 {
        eprintln!("RUSIX_MM_DUP_MMAP_FAIL init requires guest PID 1");
        process::exit(125);
    }
    // Mounting proc is the sole operation before checking the cmdline token.
    // If authorization fails, never reboot an accidentally invoked container.
    let result = run();
    let authorized = fs::read_to_string("/proc/cmdline")
        .is_ok_and(|s| s.split_whitespace().filter(|word| *word == TOKEN).count() == 1);
    if let Err(error) = result {
        eprintln!("RUSIX_MM_DUP_MMAP_FAIL init: {error}");
    }
    let _ = io::stdout().flush();
    let _ = io::stderr().flush();
    if authorized {
        // SAFETY: Both process identity and exact guest token were checked.
        // Reboot powers off this isolated VM after the probe has been reaped.
        unsafe {
            sync();
            reboot(0x4321fedc);
        }
    }
    // PID 1 must not exit (which would panic the kernel). External QEMU timeout
    // is the final bound if authorization, probe execution or shutdown fails.
    loop {
        thread::sleep(Duration::from_secs(1));
    }
}
