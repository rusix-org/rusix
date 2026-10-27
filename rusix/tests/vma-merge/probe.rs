// SPDX-License-Identifier: GPL-2.0-only
//! Disposable x86-64 guest only. Never execute on the host or in a container.
use std::{
    arch::asm,
    fs::{self, File},
    io,
    os::fd::{AsRawFd, FromRawFd, OwnedFd},
    ptr,
    sync::{
        atomic::{AtomicBool, AtomicUsize, Ordering},
        mpsc, Arc,
    },
    thread,
    time::{Duration, Instant},
};
#[cfg(not(target_arch = "x86_64"))]
compile_error!("This pinned syscall/UAPI fixture requires x86-64");
const PAGE: usize = 4096;
const TOKEN: &str = "rusix.vma_merge_probe=1";
const R: i32 = 1;
const RW: i32 = 3;
const ITER: usize = 256;
unsafe extern "C" {
    fn mmap(addr: *mut u8, len: usize, prot: i32, flags: i32, fd: i32, off: i64) -> *mut u8;
    fn munmap(addr: *mut u8, len: usize) -> i32;
    fn mprotect(addr: *mut u8, len: usize, prot: i32) -> i32;
    fn mremap(addr: *mut u8, old: usize, new: usize, flags: i32, ...) -> *mut u8;
    fn ioctl(fd: i32, request: u64, ...) -> i32;
    fn sysconf(name: i32) -> i64;
    fn getppid() -> i32;
    fn pipe2(fds: *mut i32, flags: i32) -> i32;
    fn read(fd: i32, data: *mut u8, size: usize) -> isize;
    fn write(fd: i32, data: *const u8, size: usize) -> isize;
    fn kill(pid: i32, sig: i32) -> i32;
    fn waitpid(pid: i32, status: *mut i32, options: i32) -> i32;
}
fn require(ok: bool, message: &'static str) -> io::Result<()> {
    if ok {
        Ok(())
    } else {
        Err(io::Error::other(message))
    }
}
fn pattern(i: usize) -> u8 {
    ((i % 251) + 1) as u8
}
struct Mapping {
    base: *mut u8,
    len: usize,
}
impl Mapping {
    fn new(len: usize, prot: i32) -> io::Result<Self> {
        // SAFETY: Anonymous private mapping; no requested address or backing fd.
        let base = unsafe { mmap(ptr::null_mut(), len, prot, 0x22, -1, 0) };
        if base as isize == -1 {
            return Err(io::Error::last_os_error());
        }
        Ok(Self { base, len })
    }
    fn close(mut self) -> io::Result<()> {
        let len = self.len;
        self.len = 0;
        // SAFETY: Sole owning object holds this exact current mapping interval.
        if unsafe { munmap(self.base, len) } != 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }
    fn resize(&mut self, len: usize) -> io::Result<()> {
        // SAFETY: Sole owner; no borrowed slices or concurrent access to this region.
        // MREMAP_MAYMOVE never replaces an unrelated mapping. Old holes are not owned.
        let next = unsafe { mremap(self.base, self.len, len, 1) };
        if next as isize == -1 {
            return Err(io::Error::last_os_error());
        }
        self.base = next;
        self.len = len;
        Ok(())
    }
}
impl Drop for Mapping {
    fn drop(&mut self) {
        if self.len != 0 {
            // SAFETY: Last owner, exact current interval; fallback on failed setup.
            unsafe {
                munmap(self.base, self.len);
            }
            self.len = 0;
        }
    }
}
struct Shared {
    owner: Mapping,
    phase: AtomicUsize,
    cancel: AtomicBool,
}
// SAFETY: The complete payload is initialized before Arc publication. Thereafter
// both threads only READ bytes. mprotect alternates R/RW, never removes read access.
// No Rust references into payload are formed; Arc keeps both guards and payload
// mapped until both callbacks return. The owner pointer/length never change.
unsafe impl Send for Shared {}
unsafe impl Sync for Shared {}
impl Shared {
    fn payload(&self) -> *mut u8 {
        // SAFETY: owner covers fourteen pages; payload begins after first guard.
        unsafe { self.owner.base.add(PAGE) }
    }
    fn center(&self) -> *mut u8 {
        // SAFETY: Four-page center begins within the twelve-page payload.
        unsafe { self.payload().add(4 * PAGE) }
    }
    fn check_deadline(&self, deadline: Instant) -> io::Result<()> {
        require(
            !self.cancel.load(Ordering::Acquire) && Instant::now() < deadline,
            "thread cancelled or deadline",
        )
    }
    fn wait_phase(&self, value: usize, deadline: Instant) -> io::Result<()> {
        while self.phase.load(Ordering::Acquire) != value {
            self.check_deadline(deadline)?;
            thread::yield_now();
        }
        self.check_deadline(deadline)
    }
    fn protect(&self, prot: i32) -> io::Result<()> {
        // SAFETY: Center is always mapped; both permissions include read. No writes
        // occur after publication, including while changing page permissions.
        if unsafe { mprotect(self.center(), 4 * PAGE, prot) } != 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }
    fn scan(&self) -> io::Result<()> {
        for i in 0..12 * PAGE {
            // SAFETY: Live immutable payload; all phases retain read permission.
            require(
                unsafe { ptr::read_volatile(self.payload().add(i)) } == pattern(i),
                "shared payload changed",
            )?;
        }
        Ok(())
    }
}
// Public userspace ABI from pinned include/uapi/linux/fs.h, not a kernel-private
// layout. No optional names/build IDs are requested. _IOWR('f',17,104).
#[repr(C)]
#[derive(Default)]
struct ProcmapQuery {
    size: u64,
    query_flags: u64,
    query_addr: u64,
    vma_start: u64,
    vma_end: u64,
    vma_flags: u64,
    vma_page_size: u64,
    vma_offset: u64,
    inode: u64,
    dev_major: u32,
    dev_minor: u32,
    vma_name_size: u32,
    build_id_size: u32,
    vma_name_addr: u64,
    build_id_addr: u64,
}
const _: () = assert!(size_of::<ProcmapQuery>() == 104);
const _: () = assert!(std::mem::offset_of!(ProcmapQuery, vma_name_addr) == 88);
const PROCMAP_QUERY: u64 = (3 << 30) | (104 << 16) | ((b'f' as u64) << 8) | 17;
fn query(shared: &Shared, maps: &File, expected: Option<u64>) -> io::Result<()> {
    let mut q = ProcmapQuery {
        size: 104,
        query_flags: 1,
        query_addr: shared.center() as u64,
        ..Default::default()
    };
    // SAFETY: Live writable UAPI object of exactly declared size, valid maps fd;
    // optional user buffer pointers/sizes are all zero. Kernel copies a coherent VMA.
    if unsafe { ioctl(maps.as_raw_fd(), PROCMAP_QUERY, &mut q as *mut ProcmapQuery) } != 0 {
        return Err(io::Error::last_os_error());
    }
    require(
        q.size == 104 && q.query_flags == 1 && q.query_addr == shared.center() as u64,
        "query input fields changed",
    )?;
    require(
        q.vma_flags == 1 || q.vma_flags == 3,
        "query permissions differ",
    )?;
    if let Some(flags) = expected {
        require(q.vma_flags == flags, "handshake permissions differ")?;
    }
    let (start, end) = if q.vma_flags == 1 {
        (
            shared.center() as u64,
            shared.center() as u64 + 4 * PAGE as u64,
        )
    } else {
        (
            shared.payload() as u64,
            shared.payload() as u64 + 12 * PAGE as u64,
        )
    };
    require(
        q.vma_start == start
            && q.vma_end == end
            && q.vma_start <= q.query_addr
            && q.query_addr < q.vma_end,
        "query topology differs",
    )?;
    require(
        q.vma_page_size == PAGE as u64
            && q.vma_offset == 0
            && q.inode == 0
            && q.dev_major == 0
            && q.dev_minor == 0,
        "query backing differs",
    )?;
    require(
        q.vma_name_size == 0
            && q.build_id_size == 0
            && q.vma_name_addr == 0
            && q.build_id_addr == 0,
        "unexpected query buffers",
    )
}
#[derive(Default)]
struct Counts {
    transitions: usize,
    queries: usize,
    scans: usize,
}
fn toggler(s: &Shared, deadline: Instant) -> io::Result<Counts> {
    let mut counts = Counts::default();
    s.protect(R)?;
    counts.transitions += 1;
    s.phase.store(1, Ordering::Release);
    s.wait_phase(2, deadline)?;
    s.protect(RW)?;
    counts.transitions += 1;
    s.phase.store(3, Ordering::Release);
    s.wait_phase(4, deadline)?;
    for _ in 0..ITER {
        s.check_deadline(deadline)?;
        s.protect(R)?;
        counts.transitions += 1;
        s.protect(RW)?;
        counts.transitions += 1;
        thread::yield_now();
    }
    Ok(counts)
}
fn reader(s: &Shared, deadline: Instant) -> io::Result<Counts> {
    let mut counts = Counts::default();
    let maps = File::open("/proc/self/maps")?;
    s.wait_phase(1, deadline)?;
    query(s, &maps, Some(1))?;
    counts.queries += 1;
    s.scan()?;
    counts.scans += 1;
    s.phase.store(2, Ordering::Release);
    s.wait_phase(3, deadline)?;
    query(s, &maps, Some(3))?;
    counts.queries += 1;
    s.scan()?;
    counts.scans += 1;
    s.phase.store(4, Ordering::Release);
    for _ in 0..ITER {
        s.check_deadline(deadline)?;
        query(s, &maps, None)?;
        counts.queries += 1;
        s.scan()?;
        counts.scans += 1;
        thread::yield_now();
    }
    Ok(counts)
}
fn concurrent_case() -> io::Result<()> {
    let owner = Mapping::new(14 * PAGE, 0)?;
    // SAFETY: Unique mapping, payload inside guards; no Arc or threads exist yet.
    let payload = unsafe { owner.base.add(PAGE) };
    if unsafe { mprotect(payload, 12 * PAGE, RW) } != 0 {
        return Err(io::Error::last_os_error());
    }
    for i in 0..12 * PAGE {
        // SAFETY: Unique writable mapping initialized before sharing.
        unsafe {
            ptr::write(payload.add(i), pattern(i));
        }
    }
    let shared = Arc::new(Shared {
        owner,
        phase: AtomicUsize::new(0),
        cancel: AtomicBool::new(false),
    });
    let deadline = Instant::now() + Duration::from_secs(20);
    let (tx, rx) = mpsc::channel();
    let mut handles = Vec::new();
    for worker in [
        toggler as fn(&Shared, Instant) -> io::Result<Counts>,
        reader,
    ] {
        let s = Arc::clone(&shared);
        let tx = tx.clone();
        handles.push(thread::spawn(move || {
            let result = worker(&s, deadline);
            if result.is_err() {
                s.cancel.store(true, Ordering::Release);
            }
            let _ = tx.send(result);
        }));
    }
    drop(tx);
    let mut failure = None;
    let mut counts = Counts::default();
    for _ in 0..2 {
        match rx.recv_timeout(deadline.saturating_duration_since(Instant::now())) {
            Ok(Ok(observed)) => {
                counts.transitions += observed.transitions;
                counts.queries += observed.queries;
                counts.scans += observed.scans;
            }
            Ok(Err(e)) => {
                failure = Some(e);
            }
            Err(_) => {
                failure = Some(io::Error::other("worker acknowledgment timeout"));
                break;
            }
        }
    }
    shared.cancel.store(true, Ordering::Release);
    let join_deadline = Instant::now() + Duration::from_secs(2);
    while handles.iter().any(|h| !h.is_finished()) && Instant::now() < join_deadline {
        thread::sleep(Duration::from_millis(1));
    }
    // On timeout, worker Arcs retain the mapping; caller terminates this process.
    // Never fork a process while a worker remains alive or free its address space.
    require(
        handles.iter().all(|h| h.is_finished()),
        "worker did not stop",
    )?;
    for h in handles {
        require(h.join().is_ok(), "worker panicked")?;
    }
    if let Some(error) = failure {
        return Err(error);
    }
    let shared =
        Arc::try_unwrap(shared).map_err(|_| io::Error::other("worker retained mapping"))?;
    shared.owner.close()?;
    require(
        counts.transitions == 514 && counts.queries == 258 && counts.scans == 258,
        "worker operation count",
    )?;
    println!("RUSIX_VMA_MERGE_CASE concurrent_mprotect_procmap PASS controls=2 transitions={} queries={} scans={}", counts.transitions, counts.queries, counts.scans);
    Ok(())
}
// Raw syscalls are used after fork: no allocator, Rust I/O, libc locks, formatting,
// destructors or TLS errno access. The first case has joined every Rust thread.
unsafe fn raw(n: usize, a: usize, b: usize, c: usize, d: usize, e: usize, f: usize) -> isize {
    let result: isize;
    // SAFETY: x86-64 syscall register ABI; memory effects are deliberately NOT
    // declared nomem. Each caller supplies live pointers and appropriate extents.
    unsafe {
        asm!("syscall", inlateout("rax") n => result, in("rdi") a, in("rsi") b, in("rdx") c,
        in("r10") d, in("r8") e, in("r9") f, lateout("rcx") _, lateout("r11") _, options(nostack));
    }
    result
}
unsafe fn child_exit(status: usize) -> ! {
    loop {
        unsafe {
            raw(60, status, 0, 0, 0, 0, 0);
        }
    }
}
#[repr(C)]
struct Timespec {
    sec: i64,
    nsec: i64,
}
unsafe fn child(cow: *mut u8, ready: i32, proceed: i32, close_a: i32, close_b: i32) -> ! {
    // SAFETY throughout: this child owns its private inherited mm. Pointer cow
    // spans two mapped pages; pipes are inherited live descriptors, buffers local.
    unsafe {
        raw(3, close_a as usize, 0, 0, 0, 0, 0);
        raw(3, close_b as usize, 0, 0, 0, 0, 0);
        if raw(10, cow as usize, 2 * PAGE, R as usize, 0, 0, 0) != 0
            || raw(10, cow as usize, 2 * PAGE, RW as usize, 0, 0, 0) != 0
        {
            child_exit(10);
        }
        let mut i = 0;
        while i < 2 * PAGE {
            if ptr::read_volatile(cow.add(i)) != pattern(i) {
                child_exit(11);
            }
            ptr::write_volatile(cow.add(i), 0xa5);
            i += 1;
        }
        let byte = 1u8;
        if raw(1, ready as usize, &byte as *const u8 as usize, 1, 0, 0, 0) != 1 {
            child_exit(12);
        }
        let mut time = Timespec { sec: 0, nsec: 0 };
        if raw(228, 1, &mut time as *mut Timespec as usize, 0, 0, 0, 0) != 0 {
            child_exit(13);
        }
        let end = time.sec.saturating_add(15);
        loop {
            if raw(228, 1, &mut time as *mut Timespec as usize, 0, 0, 0, 0) != 0 || time.sec >= end
            {
                child_exit(14);
            }
            let mut byte = 0u8;
            let count = raw(
                0,
                proceed as usize,
                &mut byte as *mut u8 as usize,
                1,
                0,
                0,
                0,
            );
            if count == 1 {
                if byte != 1 {
                    child_exit(15);
                }
                break;
            }
            if count != -11 && count != -4 {
                child_exit(16);
            }
            raw(24, 0, 0, 0, 0, 0, 0);
        }
        let mut i = 0;
        while i < 2 * PAGE {
            if ptr::read_volatile(cow.add(i)) != 0xa5 {
                child_exit(17);
            }
            i += 1;
        }
        child_exit(0)
    }
}
fn pipe() -> io::Result<(OwnedFd, OwnedFd)> {
    let mut fds = [-1; 2];
    // SAFETY: Two writable fd slots. NONBLOCK bounds both sides' polling; CLOEXEC.
    if unsafe { pipe2(fds.as_mut_ptr(), 0x800 | 0x80000) } != 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: Successful pipe2 returned two fresh owned descriptors exactly once.
    Ok(unsafe { (OwnedFd::from_raw_fd(fds[0]), OwnedFd::from_raw_fd(fds[1])) })
}
struct Child {
    pid: i32,
}
impl Child {
    fn wait(&mut self, deadline: Instant) -> io::Result<()> {
        loop {
            require(Instant::now() < deadline, "child wait timeout")?;
            let mut status = 0;
            // SAFETY: Exact owned child, no other waiter, writable local status.
            let ret = unsafe { waitpid(self.pid, &mut status, 1) };
            if ret == self.pid {
                self.pid = 0;
                return require(status == 0, "child exit status");
            }
            if ret < 0 {
                let error = io::Error::last_os_error();
                if error.raw_os_error() == Some(10) {
                    self.pid = 0;
                }
                if error.raw_os_error() != Some(4) {
                    return Err(error);
                }
            }
            thread::sleep(Duration::from_millis(1));
        }
    }
}
impl Drop for Child {
    fn drop(&mut self) {
        if self.pid > 0 {
            // SAFETY: No prior consuming wait succeeded, so PID remains our live
            // child or unreaped zombie; kill cannot target a recycled PID.
            unsafe {
                kill(self.pid, 9);
            }
            let _ = self.wait(Instant::now() + Duration::from_secs(2));
            // A stuck kernel child is ultimately contained by PID1 and VM timeout.
        }
    }
}
fn receive(fd: i32, deadline: Instant) -> io::Result<()> {
    loop {
        require(Instant::now() < deadline, "pipe handshake timeout")?;
        let mut byte = 0u8;
        // SAFETY: Live pipe fd and one-byte writable buffer.
        let n = unsafe { read(fd, &mut byte, 1) };
        if n == 1 {
            return require(byte == 1, "pipe handshake byte");
        }
        if n < 0 && matches!(io::Error::last_os_error().raw_os_error(), Some(4 | 11)) {
            thread::yield_now();
            continue;
        }
        return Err(io::Error::other("pipe handshake closed/failed"));
    }
}
fn fork_remap_case() -> io::Result<()> {
    let cow = Mapping::new(4 * PAGE, 0)?;
    // SAFETY: The middle two pages are enclosed in owned PROT_NONE guards.
    let payload = unsafe { cow.base.add(PAGE) };
    if unsafe { mprotect(payload, 2 * PAGE, RW) } != 0 {
        return Err(io::Error::last_os_error());
    }
    let mut moved = Mapping::new(2 * PAGE, RW)?;
    for i in 0..2 * PAGE {
        // SAFETY: Unique writable mappings before fork, separate non-overlapping allocations.
        unsafe {
            ptr::write(payload.add(i), pattern(i));
            ptr::write(moved.base.add(i), pattern(i));
        }
    }
    let (ready_r, ready_w) = pipe()?;
    let (go_r, go_w) = pipe()?;
    // SAFETY: All prior threads are joined; child follows raw-only path and _exit.
    let pid = unsafe { raw(57, 0, 0, 0, 0, 0, 0) };
    if pid < 0 {
        return Err(io::Error::from_raw_os_error((-pid) as i32));
    }
    if pid == 0 {
        unsafe {
            child(
                payload,
                ready_w.as_raw_fd(),
                go_r.as_raw_fd(),
                ready_r.as_raw_fd(),
                go_w.as_raw_fd(),
            );
        }
    }
    let mut child = Child { pid: pid as i32 };
    drop(ready_w);
    drop(go_r);
    let deadline = Instant::now() + Duration::from_secs(12);
    receive(ready_r.as_raw_fd(), deadline)?;
    let (mut grows, mut shrinks, mut zero_extensions) = (0, 0, 0);
    for _ in 0..64 {
        require(Instant::now() < deadline, "mremap loop timeout")?;
        moved.resize(3 * PAGE)?;
        grows += 1;
        require(
            moved.base as usize + moved.len <= cow.base as usize
                || moved.base as usize >= cow.base as usize + cow.len,
            "mremap overlapped private mapping",
        )?;
        for i in 0..3 * PAGE {
            let expected = if i < 2 * PAGE { pattern(i) } else { 0 };
            // SAFETY: Exclusive current returned mapping; no pointers to old holes.
            require(
                unsafe { ptr::read_volatile(moved.base.add(i)) } == expected,
                "mremap payload/zero extension",
            )?;
        }
        zero_extensions += 1;
        moved.resize(2 * PAGE)?;
        shrinks += 1;
        for i in 0..2 * PAGE {
            // SAFETY: Parent private mapping unaffected by child writes; retained
            // remap prefix also readable, no cross-thread references exist.
            require(
                unsafe { ptr::read_volatile(payload.add(i)) } == pattern(i),
                "parent COW changed",
            )?;
            require(
                unsafe { ptr::read_volatile(moved.base.add(i)) } == pattern(i),
                "shrink changed prefix",
            )?;
        }
    }
    let byte = 1u8;
    // SAFETY: Live empty pipe, one initialized byte. Reject short/failing writes.
    require(
        unsafe { write(go_w.as_raw_fd(), &byte, 1) } == 1,
        "child release pipe",
    )?;
    child.wait(deadline)?;
    moved.close()?;
    cow.close()?;
    println!("RUSIX_VMA_MERGE_CASE fork_cow_mremap_lifetime PASS cow_children=1 grows={grows} shrinks={shrinks} zero_extensions={zero_extensions}");
    Ok(())
}
fn run() -> io::Result<()> {
    let tokens = fs::read_to_string("/proc/cmdline")?;
    require(
        tokens
            .split_whitespace()
            .filter(|s| s.starts_with("rusix.vma_merge_probe="))
            .collect::<Vec<_>>()
            == [TOKEN],
        "guest token",
    )?;
    require(
        fs::read_to_string("/proc/1/comm")? == "rusix-mrg-init\n",
        "guest init identity",
    )?;
    // SAFETY: Read-only process/system queries; no mapping or process mutation.
    require(
        unsafe { getppid() } == 1 && unsafe { sysconf(30) } == PAGE as i64,
        "guest parent/page size",
    )?;
    concurrent_case()?;
    fork_remap_case()
}
fn main() {
    if let Err(error) = run() {
        eprintln!("RUSIX_VMA_MERGE_FAIL probe: {error}");
        std::process::exit(1);
    }
}
