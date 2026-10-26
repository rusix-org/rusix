// SPDX-License-Identifier: GPL-2.0-only
//! VM-only PID 1 parameter/on-demand contract. Never execute on the host.
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

fn expected(cmdline: &str, key: &str) -> io::Result<u64> {
    let prefix = format!("rusix.expect_{key}=");
    let values: Vec<_> = cmdline
        .split_ascii_whitespace()
        .filter_map(|s| s.strip_prefix(&prefix))
        .collect();
    check(values.len() == 1, "missing or duplicate expected parameter")?;
    check(
        !values[0].is_empty() && values[0].bytes().all(|b| b.is_ascii_digit()),
        "expected parameter is not decimal",
    )?;
    values[0].parse().map_err(io::Error::other)
}

fn sys_number(path: &str) -> io::Result<u64> {
    fs::read_to_string(path)?
        .trim()
        .parse()
        .map_err(io::Error::other)
}

fn devices() -> io::Result<Vec<u64>> {
    let mut ids = Vec::new();
    for entry in fs::read_dir("/sys/class/block")? {
        let name = entry?.file_name();
        let name = name.to_string_lossy();
        if let Some(id) = name.strip_prefix("ram") {
            if !id.is_empty() && id.bytes().all(|b| b.is_ascii_digit()) {
                ids.push(id.parse().map_err(io::Error::other)?);
            }
        }
    }
    ids.sort_unstable();
    Ok(ids)
}

fn open_ram(index: u64, spacing: u64, capacity: u64) -> io::Result<File> {
    let minor = index * spacing;
    let device = 256 | (minor & 255) | ((minor & !255) << 12);
    let path = format!("/dev/ram{index}");
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
        fs::read_to_string(format!("/sys/class/block/ram{index}/dev"))?.trim()
            == format!("1:{minor}"),
        "minor spacing mismatch",
    )?;
    check(
        sys_number(&format!("/sys/class/block/ram{index}/size"))? == capacity / 512,
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

fn high_positive(cmdline: &str) -> io::Result<()> {
    check(
        expected(cmdline, "rd_nr")? == 0,
        "high-positive requires rd_nr=0",
    )?;
    check(
        expected(cmdline, "rd_size")? == 4096,
        "high-positive requires 4096 KiB",
    )?;
    let expected_max: Vec<_> = cmdline
        .split_ascii_whitespace()
        .filter_map(|word| word.strip_prefix("rusix.expect_max_part="))
        .collect();
    check(
        expected_max == ["-2147483648"],
        "wrong high-positive expectation",
    )?;
    check(
        sys_number("/sys/module/brd/parameters/rd_nr")? == 0,
        "rd_nr mismatch",
    )?;
    check(
        sys_number("/sys/module/brd/parameters/rd_size")? == 4096,
        "rd_size mismatch",
    )?;
    let normalized: i32 = fs::read_to_string("/sys/module/brd/parameters/max_part")?
        .trim()
        .parse()
        .map_err(io::Error::other)?;
    check(normalized == i32::MIN, "signed normalization mismatch")?;
    println!("RUSIX_BRD_PARAMETERS_PASS parameters");
    let listing = fs::read_to_string("/proc/devices")?;
    let block = listing
        .split_once("Block devices:\n")
        .ok_or_else(|| io::Error::other("missing block major inventory"))?
        .1;
    check(
        block
            .lines()
            .filter(|line| line.split_ascii_whitespace().collect::<Vec<_>>() == ["1", "ramdisk"])
            .count()
            == 1,
        "RAM disk major not registered",
    )?;
    println!("RUSIX_BRD_PARAMETERS_PASS major_registered");
    check(devices()?.is_empty(), "high-positive precreated a disk")?;
    println!("RUSIX_BRD_PARAMETERS_PASS initial_devices");
    // SAFETY: The caller has verified PID1 and the exact VM authorization;
    // this is a guest-only block node with Linux major1/minor0 encoding.
    if unsafe { mknod(c"/dev/ram0".as_ptr(), 0o60600, 256) } != 0 {
        return Err(io::Error::last_os_error());
    }
    let node = fs::metadata("/dev/ram0")?;
    check(
        node.file_type().is_block_device() && node.rdev() == 256,
        "wrong ram0 node",
    )?;
    let error = OpenOptions::new()
        .read(true)
        .write(true)
        .open("/dev/ram0")
        .err()
        .ok_or_else(|| io::Error::other("high-positive open succeeded"))?;
    check(
        error.raw_os_error() == Some(6),
        "high-positive open did not return ENXIO",
    )?;
    println!("RUSIX_BRD_PARAMETERS_PASS open_enxio");
    check(
        devices()?.is_empty(),
        "failed creation left a published disk",
    )?;
    println!("RUSIX_BRD_PARAMETERS_PASS final_devices");
    // Never mount or read debugfs here: the pinned C allocation-error path can
    // leave a count file pointing to its freed brd_device. Observe only sysfs,
    // major registration and one failed open, then reboot the isolated guest.
    Ok(())
}

fn run(cmdline: &str) -> io::Result<()> {
    mount_fs(c"sysfs", c"/sys")?;
    let modes: Vec<_> = cmdline
        .split_ascii_whitespace()
        .filter_map(|word| word.strip_prefix("rusix.parameters_mode="))
        .collect();
    if modes == ["high_positive"] {
        return high_positive(cmdline);
    }
    check(
        modes == ["normal"],
        "missing or invalid parameter test mode",
    )?;
    let count = expected(cmdline, "rd_nr")?;
    let size = expected(cmdline, "rd_size")?;
    let spacing = expected(cmdline, "max_part")?;
    check(
        count <= 32 && (4096..=65536).contains(&size) && [1, 4, 256].contains(&spacing),
        "unsupported fixture expectations",
    )?;
    for (name, value) in [("rd_nr", count), ("rd_size", size), ("max_part", spacing)] {
        check(
            sys_number(&format!("/sys/module/brd/parameters/{name}"))? == value,
            "module parameter mismatch",
        )?;
    }
    println!("RUSIX_BRD_PARAMETERS_PASS parameters");
    check(
        devices()? == (0..count).collect::<Vec<_>>(),
        "initial device inventory mismatch",
    )?;
    println!("RUSIX_BRD_PARAMETERS_PASS initial_devices");
    let capacity = size * 1024;
    let ram0 = open_ram(0, spacing, capacity)?;
    let ram1 = open_ram(1, spacing, capacity)?;
    // If defaults precreate more than two disks, also force a genuinely absent
    // disk through the same open-time probe rather than claiming ram1 was new.
    let extra = if count > 1 {
        Some(open_ram(count, spacing, capacity)?)
    } else {
        None
    };
    let final_count = if count > 1 { count + 1 } else { 2 };
    check(
        devices()? == (0..final_count).collect::<Vec<_>>(),
        "on-demand inventory mismatch",
    )?;
    println!("RUSIX_BRD_PARAMETERS_PASS on_demand");
    for file in [&ram0, &ram1] {
        for offset in [0, 4096, capacity - 512] {
            read_sector(file, offset, 0)?;
        }
    }
    write_sector(&ram0, 0, 0x31)?;
    write_sector(&ram0, capacity - 512, 0x73)?;
    read_sector(&ram1, 0, 0)?;
    read_sector(&ram1, capacity - 512, 0)?;
    write_sector(&ram1, 0, 0xa6)?;
    write_sector(&ram1, capacity - 512, 0xd9)?;
    for (file, first, last) in [(&ram0, 0x31, 0x73), (&ram1, 0xa6, 0xd9)] {
        read_sector(file, 0, first)?;
        read_sector(file, capacity - 512, last)?;
        read_sector(file, 4096, 0)?;
    }
    println!("RUSIX_BRD_PARAMETERS_PASS independent_io");
    // LTS block/fops.c truncates reads at capacity, returns EOF at/beyond it,
    // and rejects nonempty writes starting there with ENOSPC before driver IO.
    for (file, last) in [(&ram0, 0x73), (&ram1, 0xd9)] {
        let mut buffer = Buffer([0xcc; 1024]);
        check(
            file.read_at(&mut buffer.0, capacity - 512)? == 512,
            "cross-end read was not shortened",
        )?;
        check(
            buffer.0[..512].iter().all(|b| *b == last)
                && buffer.0[512..].iter().all(|b| *b == 0xcc),
            "cross-end read modified wrong bytes",
        )?;
        for offset in [capacity, capacity + 512] {
            check(
                file.read_at(&mut buffer.0[..512], offset)? == 0,
                "missing capacity EOF",
            )?;
            let error = file
                .write_at(&buffer.0[..512], offset)
                .err()
                .ok_or_else(|| io::Error::other("write beyond capacity succeeded"))?;
            check(
                error.raw_os_error() == Some(28),
                "write beyond capacity did not return ENOSPC",
            )?;
        }
        read_sector(file, capacity - 512, last)?;
    }
    drop(extra);
    println!("RUSIX_BRD_PARAMETERS_PASS capacity");
    Ok(())
}

fn main() {
    if process::id() != 1 {
        eprintln!("RUSIX_BRD_PARAMETERS_FAIL requires VM PID1");
        process::exit(2);
    }
    if let Err(error) = mount_fs(c"proc", c"/proc") {
        eprintln!("RUSIX_BRD_PARAMETERS_FAIL proc {error}");
        process::exit(2);
    }
    let cmdline = fs::read_to_string("/proc/cmdline").unwrap_or_default();
    if cmdline
        .split_ascii_whitespace()
        .filter(|s| *s == "rusix.brd_parameters=1")
        .count()
        != 1
    {
        eprintln!("RUSIX_BRD_PARAMETERS_FAIL missing exact VM authorization");
        process::exit(2);
    }
    println!("RUSIX_BRD_PARAMETERS_START");
    match run(&cmdline) {
        Ok(()) => println!("RUSIX_BRD_PARAMETERS_SUCCESS cases=5"),
        Err(error) => eprintln!("RUSIX_BRD_PARAMETERS_FAIL {error}"),
    }
    let _ = io::stdout().flush();
    let _ = io::stderr().flush();
    // SAFETY: Only authorized guest PID1 reaches sync/reboot; no pointer args.
    unsafe {
        sync();
        reboot(0x01234567);
    }
    eprintln!("RUSIX_BRD_PARAMETERS_FAIL reboot returned");
    loop {
        thread::sleep(Duration::from_secs(60));
    }
}
