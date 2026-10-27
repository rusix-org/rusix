// SPDX-License-Identifier: GPL-2.0-only
//! Guest-only x86_64 Linux poll/epoll consumers; call after init authorization.
//! Epoll registration precedes writes, so its poll callbacks are installed. These
//! synchronous probes do not claim a thread was blocked during notification.

#[cfg(not(all(target_os = "linux", target_arch = "x86_64")))]
compile_error!("wake_probe requires the declared Linux x86_64 guest ABI");

use std::{
    ffi::c_void,
    io,
    mem::{align_of, size_of},
    os::fd::{AsRawFd, FromRawFd, OwnedFd},
    ptr::{addr_of, null_mut},
};

const NONBLOCK: i32 = 0x800;
const CLOEXEC: i32 = 0x80000;
const POLLIN: i16 = 1;
const EPOLLIN: u32 = 1;
const EPOLLONESHOT: u32 = 1 << 30;
const ADD: i32 = 1;
const DEL: i32 = 2;
const MOD: i32 = 3;
const READY_MS: i32 = 1000;
const EMPTY_MS: i32 = 20;

#[repr(C)]
struct PollFd {
    fd: i32,
    events: i16,
    revents: i16,
}

// Linux x86_64 epoll_event is packed, including its 64-bit data field.
#[repr(C, packed)]
#[derive(Clone, Copy)]
struct EpollEvent {
    events: u32,
    data: u64,
}
const _: () = assert!(size_of::<EpollEvent>() == 12 && align_of::<EpollEvent>() == 1);
const _: () = assert!(size_of::<PollFd>() == 8);

unsafe extern "C" {
    fn pipe2(pipefd: *mut i32, flags: i32) -> i32;
    fn poll(fds: *mut PollFd, nfds: usize, timeout: i32) -> i32;
    fn eventfd(initval: u32, flags: i32) -> i32;
    fn epoll_create1(flags: i32) -> i32;
    fn epoll_ctl(epfd: i32, op: i32, fd: i32, event: *mut EpollEvent) -> i32;
    fn epoll_wait(epfd: i32, events: *mut EpollEvent, maxevents: i32, timeout: i32) -> i32;
    fn read(fd: i32, buf: *mut c_void, count: usize) -> isize;
    fn write(fd: i32, buf: *const c_void, count: usize) -> isize;
}

fn require(ok: bool, why: &str) -> io::Result<()> {
    if ok {
        Ok(())
    } else {
        Err(io::Error::other(why))
    }
}

fn checked(ret: i32) -> io::Result<i32> {
    if ret < 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(ret)
    }
}

fn pipe() -> io::Result<(OwnedFd, OwnedFd)> {
    let mut pair = [-1; 2];
    // SAFETY: pipe2 writes two integers; flags request nonblocking owned FDs.
    checked(unsafe { pipe2(pair.as_mut_ptr(), NONBLOCK | CLOEXEC) })?;
    // SAFETY: success returned two newly owned descriptors, each wrapped once.
    Ok(unsafe { (OwnedFd::from_raw_fd(pair[0]), OwnedFd::from_raw_fd(pair[1])) })
}

fn counter() -> io::Result<OwnedFd> {
    // SAFETY: eventfd takes only scalar arguments and returns a new descriptor.
    let fd = checked(unsafe { eventfd(0, NONBLOCK | CLOEXEC) })?;
    // SAFETY: this is the sole owner of the newly returned descriptor.
    Ok(unsafe { OwnedFd::from_raw_fd(fd) })
}

fn epoll() -> io::Result<OwnedFd> {
    // SAFETY: epoll_create1 takes scalar flags and returns a new descriptor.
    let fd = checked(unsafe { epoll_create1(CLOEXEC) })?;
    // SAFETY: this is the sole owner of the newly returned descriptor.
    Ok(unsafe { OwnedFd::from_raw_fd(fd) })
}

fn control(ep: &OwnedFd, op: i32, fd: &OwnedFd, events: u32, tag: u64) -> io::Result<()> {
    let mut event = EpollEvent { events, data: tag };
    // SAFETY: both FDs remain owned; event has the exact x86_64 packed ABI.
    // Linux ignores the event pointer for DEL, so pass null only for that op.
    checked(unsafe {
        epoll_ctl(
            ep.as_raw_fd(),
            op,
            fd.as_raw_fd(),
            if op == DEL { null_mut() } else { &mut event },
        )
    })?;
    Ok(())
}

fn events(ep: &OwnedFd, timeout: i32) -> io::Result<Vec<(u32, u64)>> {
    let mut result = [EpollEvent { events: 0, data: 0 }; 4];
    // SAFETY: four writable ABI entries live for the call; timeout is finite.
    let count = checked(unsafe {
        epoll_wait(
            ep.as_raw_fd(),
            result.as_mut_ptr(),
            result.len() as i32,
            timeout,
        )
    })? as usize;
    require(count <= result.len(), "epoll returned too many events")?;
    Ok(result[..count]
        .iter()
        .map(|event| {
            // SAFETY: initialized packed fields may be unaligned. Raw projections
            // and read_unaligned avoid creating a reference to either field.
            unsafe {
                (
                    addr_of!(event.events).read_unaligned(),
                    addr_of!(event.data).read_unaligned(),
                )
            }
        })
        .collect())
}

fn one_event(ep: &OwnedFd, tag: u64) -> io::Result<()> {
    require(
        events(ep, READY_MS)? == [(EPOLLIN, tag)],
        "unexpected epoll event/tag",
    )
}

fn empty(ep: &OwnedFd) -> io::Result<()> {
    require(
        events(ep, EMPTY_MS)?.is_empty(),
        "unexpected epoll readiness",
    )
}

fn send(fd: &OwnedFd, bytes: &[u8]) -> io::Result<()> {
    // SAFETY: borrowed bytes remain valid for the synchronous write. Every data
    // FD is nonblocking; no retries can extend this operation indefinitely.
    let ret = unsafe { write(fd.as_raw_fd(), bytes.as_ptr().cast(), bytes.len()) };
    if ret < 0 {
        return Err(io::Error::last_os_error());
    }
    require(ret as usize == bytes.len(), "short probe write")
}

fn receive(fd: &OwnedFd, expected: &[u8]) -> io::Result<()> {
    let mut data = vec![0; expected.len()];
    // SAFETY: data is writable for its length and FD remains live/nonblocking.
    let ret = unsafe { read(fd.as_raw_fd(), data.as_mut_ptr().cast(), data.len()) };
    if ret < 0 {
        return Err(io::Error::last_os_error());
    }
    require(
        ret as usize == expected.len() && data == expected,
        "probe read mismatch",
    )
}

fn drained(fd: &OwnedFd) -> io::Result<()> {
    let mut bytes = [0u8; 8];
    // SAFETY: buffer is writable; eight bytes also satisfies eventfd read ABI.
    let ret = unsafe { read(fd.as_raw_fd(), bytes.as_mut_ptr().cast(), bytes.len()) };
    if ret < 0 {
        let error = io::Error::last_os_error();
        require(
            error.kind() == io::ErrorKind::WouldBlock,
            "drain did not return EAGAIN",
        )
    } else {
        Err(io::Error::other(
            "drained FD unexpectedly readable or closed",
        ))
    }
}

fn poll_pipe() -> io::Result<()> {
    let (reader, writer) = pipe()?;
    let mut state = PollFd {
        fd: reader.as_raw_fd(),
        events: POLLIN,
        revents: 0,
    };
    // SAFETY: one initialized pollfd is writable and the timeout is bounded.
    let count = checked(unsafe { poll(&mut state, 1, EMPTY_MS) })?;
    require(
        count == 0 && state.revents == 0,
        "empty pipe poll did not time out",
    )?;
    send(&writer, b"rusix-poll-payload")?;
    // SAFETY: same live pollfd and finite wait as above.
    let count = checked(unsafe { poll(&mut state, 1, READY_MS) })?;
    require(
        count == 1 && state.revents == POLLIN,
        "pipe poll readiness mismatch",
    )?;
    receive(&reader, b"rusix-poll-payload")?;
    drained(&reader)
}

fn mixed_epoll() -> io::Result<()> {
    let ep = epoll()?;
    let (reader, writer) = pipe()?;
    let count = counter()?;
    const PIPE_TAG: u64 = 0x1234_5678_8765_4321;
    const COUNT_TAG: u64 = 0xfedc_ba98_7654_3210;
    control(&ep, ADD, &reader, EPOLLIN, PIPE_TAG)?;
    control(&ep, ADD, &count, EPOLLIN, COUNT_TAG)?;
    empty(&ep)?;
    send(&writer, b"epoll-pipe")?;
    send(&count, &2u64.to_ne_bytes())?;
    send(&count, &5u64.to_ne_bytes())?;
    // Both sources are ready before the syscall; order is intentionally ignored.
    let mut ready = events(&ep, READY_MS)?;
    ready.sort_unstable();
    let mut expected = vec![(EPOLLIN, PIPE_TAG), (EPOLLIN, COUNT_TAG)];
    expected.sort_unstable();
    require(
        ready == expected,
        "epoll lost/duplicated/mistagged mixed readiness",
    )?;
    receive(&reader, b"epoll-pipe")?;
    receive(&count, &7u64.to_ne_bytes())?;
    drained(&reader)?;
    drained(&count)?;
    empty(&ep)
}

fn oneshot() -> io::Result<()> {
    let ep = epoll()?;
    let count = counter()?;
    const TAG: u64 = 0xaaaa_bbbb_cccc_dddd;
    control(&ep, ADD, &count, EPOLLIN | EPOLLONESHOT, TAG)?;
    send(&count, &1u64.to_ne_bytes())?;
    one_event(&ep, TAG)?;
    receive(&count, &1u64.to_ne_bytes())?;
    // A fresh write invokes the installed callback, but one-shot remains disabled.
    send(&count, &3u64.to_ne_bytes())?;
    empty(&ep)?;
    control(&ep, MOD, &count, EPOLLIN | EPOLLONESHOT, TAG)?;
    one_event(&ep, TAG)?;
    receive(&count, &3u64.to_ne_bytes())?;
    drained(&count)?;
    empty(&ep)
}

fn teardown() -> io::Result<()> {
    let ep = epoll()?;
    let (reader, writer) = pipe()?;
    let closed = counter()?;
    let survivor = counter()?;
    control(&ep, ADD, &reader, EPOLLIN, 1)?;
    control(&ep, ADD, &closed, EPOLLIN, 2)?;
    control(&ep, ADD, &survivor, EPOLLIN, 3)?;
    // Remove a ready registration explicitly, then close its descriptors.
    send(&writer, b"removed")?;
    control(&ep, DEL, &reader, 0, 0)?;
    drop(reader);
    drop(writer);
    // Closing the last descriptor removes this ready registration without DEL.
    send(&closed, &1u64.to_ne_bytes())?;
    drop(closed);
    send(&survivor, &9u64.to_ne_bytes())?;
    one_event(&ep, 3)?;
    receive(&survivor, &9u64.to_ne_bytes())?;
    drained(&survivor)?;
    empty(&ep)
}

/// Invoked by the VM init only after its PID/token/device authorization checks.
pub fn run() -> io::Result<()> {
    for (name, case) in [
        ("pipe_poll", poll_pipe as fn() -> io::Result<()>),
        ("epoll_pipe_eventfd", mixed_epoll),
        ("epoll_oneshot_rearm", oneshot),
        ("epoll_del_close", teardown),
    ] {
        case().map_err(|error| io::Error::other(format!("wake probe {name}: {error}")))?;
        super::marker(&format!("RUSIX_WAKE_PASS {name}"))?;
    }
    Ok(())
}
