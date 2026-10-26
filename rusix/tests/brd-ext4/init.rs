// SPDX-License-Identifier: GPL-2.0-only
//! VM-only PID 1: run ordinary shell/ext4 tools, then reboot the guest.
//! Never execute this fixture on the host or as container PID 1.
use std::{
    env, fs,
    io::{self, Write},
    os::unix::fs::{FileTypeExt, MetadataExt},
    process::{self, Command},
    thread,
    time::Duration,
};

mod wake_probe;

const TOKEN: &str = "rusix.brd_ext4=1";
const PAYLOAD_BYTES: usize = 1_048_576;

unsafe extern "C" {
    fn tcdrain(fd: i32) -> i32;
    fn sync();
    fn reboot(command: i32) -> i32;
}

// One write becomes one printk record; never retry a short write as a second
// record. Called only after guest authorization, before/after the workload.
fn marker(text: &str) -> io::Result<()> {
    let mut file = fs::OpenOptions::new().write(true).open("/dev/kmsg")?;
    let metadata = file.metadata()?;
    if !metadata.file_type().is_char_device() || metadata.rdev() != 267 {
        return Err(io::Error::other("/dev/kmsg is not character device 1:11"));
    }
    let record = format!("<5>{text}\n");
    if file.write(record.as_bytes())? != record.len() {
        return Err(io::Error::other("short marker write"));
    }
    Ok(())
}

fn command(path: &str, args: &[&str]) -> io::Result<()> {
    let status = Command::new(path)
        .args(args)
        .env_clear()
        .env("PATH", "/usr/sbin:/usr/bin:/sbin:/bin")
        .env("LC_ALL", "C")
        .env("TZ", "UTC")
        .status()?;
    if status.success() {
        Ok(())
    } else {
        Err(io::Error::other(format!("{path} exited {status}")))
    }
}

fn run() -> io::Result<()> {
    let device = fs::metadata("/dev/ram0")?;
    // Linux dev_t encoding for major 1, minor 0. Refuse an ordinary image file
    // or a different device even inside the authorized guest.
    if !device.file_type().is_block_device() || device.rdev() != 256 {
        return Err(io::Error::other("/dev/ram0 is not block device 1:0"));
    }
    fs::create_dir_all("/expected")?;
    fs::create_dir_all("/mnt/test")?;
    let payload: Vec<u8> = (0..PAYLOAD_BYTES)
        .map(|i| (((i * 73 + (i >> 8) * 19) ^ 0xa5) & 255) as u8)
        .collect();
    let mut sparse = vec![0; PAYLOAD_BYTES];
    sparse[32768..49152].copy_from_slice(&payload[..16384]);
    fs::write("/expected/payload", payload)?;
    fs::write("/expected/sparse", sparse)?;
    let status = Command::new("/bin/sh")
        .arg("/ext4-workload.sh")
        .env_clear()
        .env("PATH", "/usr/sbin:/usr/bin:/sbin:/bin")
        .env("LC_ALL", "C")
        .env("TZ", "UTC")
        .env("RUSIX_BRD_EXT4_GUEST", "1")
        .status()?;
    if !status.success() {
        return Err(io::Error::other(format!("workload exited {status}")));
    }
    Ok(())
}

fn main() {
    // Check before executing any utility, creating files, mounting or rebooting.
    if process::id() != 1 {
        eprintln!("RUSIX_EXT4_FAIL authorization requires VM PID 1");
        process::exit(2);
    }
    // The initramfs must contain /proc and /dev/console; the kernel connects
    // descriptors 0..2 to that console. Only proc is mounted before token check.
    if let Err(error) = command(
        "/usr/bin/mount",
        &[
            "-n",
            "-t",
            "proc",
            "-o",
            "nosuid,nodev,noexec",
            "proc",
            "/proc",
        ],
    ) {
        eprintln!("RUSIX_EXT4_FAIL bootstrap {error}");
        process::exit(2);
    }
    let authorized = fs::read_to_string("/proc/cmdline")
        .map(|s| s.split_ascii_whitespace().any(|word| word == TOKEN))
        .unwrap_or(false);
    if !authorized {
        eprintln!("RUSIX_EXT4_FAIL authorization missing exact command-line token");
        process::exit(2);
    }
    // Avoid inheriting loader overrides from any unexpected init environment.
    env::remove_var("LD_PRELOAD");
    if let Err(error) = marker("RUSIX_EXT4_START")
        .and_then(|()| run())
        .and_then(|()| wake_probe::run())
        .and_then(|()| marker("RUSIX_EXT4_SUCCESS cases=6"))
    {
        eprintln!("RUSIX_EXT4_FAIL init {error}");
    }
    let _ = io::stdout().flush();
    let _ = io::stderr().flush();
    // SAFETY: Authorized guest PID1 inherited the live console descriptors.
    // Flush only drains Rust buffering; tcdrain also waits for the serial TX
    // queue for ordinary utility logs before shutdown printk messages.
    if unsafe { tcdrain(1) } != 0 || unsafe { tcdrain(2) } != 0 {
        eprintln!(
            "RUSIX_EXT4_FAIL console drain {}",
            io::Error::last_os_error()
        );
        process::exit(2);
    }
    // SAFETY: We are the authorized VM's PID 1. These libc functions take no
    // pointers; RB_AUTOBOOT is Linux's restart command. No host path reaches it.
    unsafe {
        sync();
        reboot(0x0123_4567);
    }
    eprintln!("RUSIX_EXT4_FAIL reboot returned");
    // The external runner must bound execution and reject timeout/fail markers.
    loop {
        thread::sleep(Duration::from_secs(60));
    }
}
