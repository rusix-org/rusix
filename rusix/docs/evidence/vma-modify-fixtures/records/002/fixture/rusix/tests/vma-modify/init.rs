// SPDX-License-Identifier: GPL-2.0-only
//! Guest-only x86-64 PID 1; never execute on the host or in a container.
use std::{
    fs,
    io::{self, Write},
    os::unix::process::CommandExt,
    process::{self, Command},
    thread,
    time::{Duration, Instant},
};
const TOKEN: &str = "rusix.vma_modify_probe=1";
unsafe extern "C" {
    fn mount(
        source: *const u8,
        target: *const u8,
        kind: *const u8,
        flags: usize,
        data: *const u8,
    ) -> i32;
    fn prctl(option: i32, ...) -> i32;
    fn waitid(kind: i32, pid: u32, info: *mut u64, options: i32) -> i32;
    fn waitpid(pid: i32, status: *mut i32, options: i32) -> i32;
    fn kill(pid: i32, signal: i32) -> i32;
    fn sync();
    fn reboot(command: i32) -> i32;
}
fn authorized() -> bool {
    fs::read_to_string("/proc/cmdline").is_ok_and(|s| {
        let tokens: Vec<_> = s
            .split_whitespace()
            .filter(|v| v.starts_with("rusix.vma_modify_probe="))
            .collect();
        tokens == [TOKEN]
    })
}
fn run() -> io::Result<()> {
    // SAFETY: Static NUL-terminated strings; null optional data; PID 1 checked.
    if unsafe {
        mount(
            b"proc\0".as_ptr(),
            b"/proc\0".as_ptr(),
            b"proc\0".as_ptr(),
            14,
            std::ptr::null(),
        )
    } != 0
    {
        return Err(io::Error::last_os_error());
    }
    if !authorized() {
        return Err(io::Error::other("guest token missing or ambiguous"));
    }
    // SAFETY: PR_SET_NAME reads a live 16-byte-or-shorter terminated string.
    if unsafe { prctl(15, b"rusix-vma-init\0".as_ptr(), 0usize, 0usize, 0usize) } != 0 {
        return Err(io::Error::last_os_error());
    }
    println!("RUSIX_VMA_MODIFY_BEGIN");
    io::stdout().flush()?;
    let mut child = Command::new("/probe")
        .arg("-r")
        .arg("merge.mprotect_unfaulted_left")
        .arg("-r")
        .arg("merge.mprotect_unfaulted_right")
        .arg("-r")
        .arg("merge.mprotect_unfaulted_both")
        .arg("-r")
        .arg("merge.mprotect_faulted_left_unfaulted_right")
        .arg("-r")
        .arg("merge.mprotect_unfaulted_left_faulted_right")
        .env_clear()
        .env("LC_ALL", "C")
        .env("PATH", "/")
        .env("TZ", "UTC")
        .process_group(0)
        .spawn()?;
    let pid = child.id();
    let deadline = Instant::now() + Duration::from_secs(60);
    let observed = loop {
        if Instant::now() >= deadline {
            break Err(io::Error::other("native test timeout"));
        }
        // x86-64 siginfo_t: 128 bytes aligned to 8, si_pid at byte 16.
        // SAFETY: Full writable siginfo storage; waitid observes our child and
        // WNOWAIT preserves its PID/PGID against reuse until cleanup below.
        let mut info = [0u64; 16];
        let ret = unsafe { waitid(1, pid, info.as_mut_ptr(), 4 | 1 | 0x01000000) };
        if ret < 0 {
            let error = io::Error::last_os_error();
            if error.raw_os_error() == Some(4) {
                continue;
            }
            break Err(error);
        }
        if info[2] as u32 == pid {
            break Ok(());
        }
        if Instant::now() >= deadline {
            break Err(io::Error::other("native test timeout"));
        }
        thread::sleep(Duration::from_millis(10));
    };
    // SAFETY: Child is still live or an unreaped zombie; its PGID cannot be
    // recycled. Even an unexpected waitid error does not consume the child:
    // this PID1 is its sole waiter and never enables SIGCHLD auto-reaping.
    // Kill any descendants before reaping that group leader.
    let killed = unsafe { kill(-(pid as i32), 9) };
    let kill_error = if killed < 0 {
        Some(io::Error::last_os_error())
    } else {
        None
    };
    let status = child.wait();
    // The native harness uses additional child process groups. PID 1 adopts
    // those orphaned descendants; a live survivor makes cleanup fail closed.
    // Bound reaping; no new guest work starts
    // if cleanup cannot finish. Kernel breakage is bounded by external VM timeout.
    let cleanup = Instant::now() + Duration::from_secs(3);
    let reaped = loop {
        if Instant::now() >= cleanup {
            break Err(io::Error::other("descendant cleanup timeout"));
        }
        let mut status = 0;
        // SAFETY: Valid writable status; WNOHANG never waits for a live child.
        let ret = unsafe { waitpid(-1, &mut status, 1) };
        if ret > 0 {
            continue;
        }
        if ret < 0 {
            let error = io::Error::last_os_error();
            if error.raw_os_error() == Some(10) {
                break Ok(());
            }
            if error.raw_os_error() != Some(4) {
                break Err(error);
            }
        }
        if Instant::now() >= cleanup {
            break Err(io::Error::other("descendant cleanup timeout"));
        }
        thread::sleep(Duration::from_millis(10));
    };
    observed?;
    if let Some(error) = kill_error {
        if error.raw_os_error() != Some(3) {
            return Err(error);
        }
    }
    reaped?;
    if !status?.success() {
        return Err(io::Error::other("native test exit failure"));
    }
    println!("RUSIX_VMA_MODIFY_END");
    println!("RUSIX_VMA_MODIFY_PASS");
    Ok(())
}
fn main() {
    if process::id() != 1 {
        eprintln!("RUSIX_VMA_MODIFY_FAIL guest PID 1 required");
        process::exit(125);
    }
    if let Err(error) = run() {
        eprintln!("RUSIX_VMA_MODIFY_FAIL init: {error}");
    }
    let _ = io::stdout().flush();
    let _ = io::stderr().flush();
    if authorized() {
        // SAFETY: PID 1 plus exact guest-only token; powers off disposable VM.
        unsafe {
            sync();
            reboot(0x4321fedc);
        }
    }
    loop {
        thread::sleep(Duration::from_secs(1));
    }
}
