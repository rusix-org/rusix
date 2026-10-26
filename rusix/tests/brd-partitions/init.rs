// SPDX-License-Identifier: GPL-2.0-only
//! VM-only PID 1 DOS partition contract. Never execute on the host.
use core::ffi::{c_char, c_int, c_uint, c_ulong, c_void, CStr};
use std::{
    fs::{self, File, OpenOptions},
    io::{self, Write},
    os::{
        fd::AsRawFd,
        unix::fs::{FileExt, FileTypeExt, MetadataExt, OpenOptionsExt},
    },
    process, thread,
    time::Duration,
};

unsafe extern "C" {
    fn mount(
        source: *const c_char,
        target: *const c_char,
        kind: *const c_char,
        flags: c_ulong,
        data: *const c_void,
    ) -> c_int;
    fn mknod(path: *const c_char, mode: c_uint, device: c_ulong) -> c_int;
    fn ioctl(fd: c_int, request: c_ulong, ...) -> c_int;
    fn sync();
    fn reboot(command: c_int) -> c_int;
}

#[repr(align(4096))]
struct Buffer([u8; 1024]);

fn check(ok: bool, reason: &str) -> io::Result<()> {
    if ok {
        Ok(())
    } else {
        Err(io::Error::other(reason))
    }
}

fn mount_fs(name: &CStr, target: &CStr) -> io::Result<()> {
    // SAFETY: CStr provides live NUL-terminated strings for the call. Null
    // data is accepted for these pseudo-filesystems. PID1 was checked first.
    let result = unsafe {
        mount(
            name.as_ptr(),
            target.as_ptr(),
            name.as_ptr(),
            14,
            std::ptr::null(),
        )
    };
    if result == 0 {
        Ok(())
    } else {
        Err(io::Error::last_os_error())
    }
}

fn sys_number(path: &str) -> io::Result<u64> {
    fs::read_to_string(path)?
        .trim()
        .parse()
        .map_err(io::Error::other)
}

fn open_node(name: &str, minor: u64, capacity: u64) -> io::Result<File> {
    let device = 256 | (minor & 255) | ((minor & !255) << 12);
    let path = format!("/dev/{name}");
    let cpath = std::ffi::CString::new(path.as_str()).map_err(io::Error::other)?;
    // SAFETY: A valid NUL-terminated path; creates a guest block node only after
    // exact VM authorization. dev_t encoding is Linux x86_64 major1/minorN.
    if unsafe { mknod(cpath.as_ptr(), 0o60600, device) } != 0 {
        return Err(io::Error::last_os_error());
    }
    let meta = fs::metadata(&path)?;
    check(
        meta.file_type().is_block_device() && meta.rdev() == device,
        "wrong device node",
    )?;
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .custom_flags(0o40000)
        .open(path)?;
    let mut bytes = 0u64;
    // SAFETY: BLKGETSIZE64 writes one u64 to valid writable storage; fd is live.
    if unsafe { ioctl(file.as_raw_fd(), 0x80081272, &mut bytes as *mut u64) } != 0 {
        return Err(io::Error::last_os_error());
    }
    check(bytes == capacity, "capacity ioctl mismatch")?;
    check(
        fs::read_to_string(format!("/sys/class/block/{name}/dev"))?.trim() == format!("1:{minor}"),
        "minor spacing mismatch",
    )?;
    check(
        sys_number(&format!("/sys/class/block/{name}/size"))? == capacity / 512,
        "sysfs capacity mismatch",
    )?;
    Ok(file)
}

fn read_sector(file: &File, offset: u64, value: u8) -> io::Result<()> {
    let mut buffer = Buffer([0xcc; 1024]);
    check(
        file.read_at(&mut buffer.0[..512], offset)? == 512,
        "short sector read",
    )?;
    check(
        buffer.0[..512].iter().all(|b| *b == value),
        "sector contents mismatch",
    )
}

fn write_sector(file: &File, offset: u64, value: u8) -> io::Result<()> {
    let buffer = Buffer([value; 1024]);
    check(
        file.write_at(&buffer.0[..512], offset)? == 512,
        "short sector write",
    )
}

fn run() -> io::Result<()> {
    mount_fs(c"sysfs", c"/sys")?;
    for (name, value) in [("rd_nr", 2), ("rd_size", 4096), ("max_part", 4)] {
        check(
            sys_number(&format!("/sys/module/brd/parameters/{name}"))? == value,
            "unexpected BRD parameters",
        )?;
    }
    let ram0 = open_node("ram0", 0, 4 * 1024 * 1024)?;
    let ram1 = open_node("ram1", 4, 4 * 1024 * 1024)?;
    check(
        !std::path::Path::new("/sys/class/block/ram0p1").exists(),
        "unexpected initial partition",
    )?;
    const START: u64 = 2048 * 512;
    const LENGTH: u64 = 2048 * 512;
    let mut mbr = Buffer([0; 1024]);
    // One primary Linux partition. LBA fields are authoritative in the pinned
    // MSDOS parser; remaining entries and the inactive boot flag stay zero.
    mbr.0[446 + 4] = 0x83;
    mbr.0[446 + 8..446 + 12].copy_from_slice(&2048u32.to_le_bytes());
    mbr.0[446 + 12..446 + 16].copy_from_slice(&2048u32.to_le_bytes());
    mbr.0[510..512].copy_from_slice(&[0x55, 0xaa]);
    check(ram0.write_at(&mbr.0[..512], 0)? == 512, "short MBR write")?;
    ram0.sync_all()?;
    // SAFETY: BLKRRPART takes no pointer argument. This live whole-disk fd
    // belongs to the authorized guest; no partition fd has been opened yet.
    if unsafe { ioctl(ram0.as_raw_fd(), 0x125f) } != 0 {
        return Err(io::Error::last_os_error());
    }
    println!("RUSIX_BRD_PARTITIONS_PASS discovery");
    let partition = open_node("ram0p1", 1, LENGTH)?;
    check(
        sys_number("/sys/class/block/ram0p1/start")? == START / 512,
        "partition start mismatch",
    )?;
    check(
        sys_number("/sys/class/block/ram0p1/partition")? == 1,
        "partition number mismatch",
    )?;
    println!("RUSIX_BRD_PARTITIONS_PASS geometry");
    write_sector(&ram0, START - 512, 0x29)?;
    write_sector(&ram0, START + LENGTH, 0x91)?;
    write_sector(&partition, 0, 0x36)?;
    write_sector(&partition, LENGTH - 512, 0x72)?;
    read_sector(&ram0, START, 0x36)?;
    read_sector(&ram0, START + LENGTH - 512, 0x72)?;
    write_sector(&ram0, START + 4096, 0xa5)?;
    read_sector(&partition, 4096, 0xa5)?;
    read_sector(&ram0, START - 512, 0x29)?;
    read_sector(&ram0, START + LENGTH, 0x91)?;
    println!("RUSIX_BRD_PARTITIONS_PASS translation");
    let mut buffer = Buffer([0xcc; 1024]);
    check(
        partition.read_at(&mut buffer.0, LENGTH - 512)? == 512,
        "cross-end read length",
    )?;
    check(
        buffer.0[..512].iter().all(|b| *b == 0x72) && buffer.0[512..].iter().all(|b| *b == 0xcc),
        "cross-end read contents",
    )?;
    for offset in [LENGTH, LENGTH + 512] {
        check(
            partition.read_at(&mut buffer.0[..512], offset)? == 0,
            "partition EOF",
        )?;
        let error = partition
            .write_at(&buffer.0[..512], offset)
            .err()
            .ok_or_else(|| io::Error::other("partition boundary write succeeded"))?;
        check(error.raw_os_error() == Some(28), "partition boundary errno")?;
    }
    read_sector(&ram0, START - 512, 0x29)?;
    read_sector(&ram0, START + LENGTH, 0x91)?;
    read_sector(&partition, LENGTH - 512, 0x72)?;
    println!("RUSIX_BRD_PARTITIONS_PASS boundaries");
    for offset in [
        0,
        START - 512,
        START,
        START + 4096,
        START + LENGTH - 512,
        START + LENGTH,
    ] {
        read_sector(&ram1, offset, 0)?;
    }
    write_sector(&ram1, START, 0xee)?;
    read_sector(&ram1, START, 0xee)?;
    read_sector(&partition, 0, 0x36)?;
    let mut observed = Buffer([0; 1024]);
    check(
        ram0.read_at(&mut observed.0[..512], 0)? == 512 && observed.0[..512] == mbr.0[..512],
        "MBR changed during partition I/O",
    )?;
    println!("RUSIX_BRD_PARTITIONS_PASS independent_disk");
    Ok(())
}

fn main() {
    if process::id() != 1 {
        eprintln!("RUSIX_BRD_PARTITIONS_FAIL requires VM PID1");
        process::exit(2);
    }
    if let Err(error) = mount_fs(c"proc", c"/proc") {
        eprintln!("RUSIX_BRD_PARTITIONS_FAIL proc {error}");
        process::exit(2);
    }
    let cmdline = fs::read_to_string("/proc/cmdline").unwrap_or_default();
    if cmdline
        .split_ascii_whitespace()
        .filter(|s| *s == "rusix.brd_partitions=1")
        .count()
        != 1
    {
        eprintln!("RUSIX_BRD_PARTITIONS_FAIL missing exact VM authorization");
        process::exit(2);
    }
    println!("RUSIX_BRD_PARTITIONS_START");
    match run() {
        Ok(()) => println!("RUSIX_BRD_PARTITIONS_SUCCESS cases=5"),
        Err(error) => eprintln!("RUSIX_BRD_PARTITIONS_FAIL {error}"),
    }
    let _ = io::stdout().flush();
    let _ = io::stderr().flush();
    // SAFETY: Only authorized guest PID1 reaches sync/reboot; no pointer args.
    unsafe {
        sync();
        reboot(0x01234567);
    }
    eprintln!("RUSIX_BRD_PARTITIONS_FAIL reboot returned");
    loop {
        thread::sleep(Duration::from_secs(60));
    }
}
