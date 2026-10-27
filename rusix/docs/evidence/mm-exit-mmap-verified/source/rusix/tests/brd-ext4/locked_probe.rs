// SPDX-License-Identifier: GPL-2.0-only
//! Guest-only blocking consumers of the locked interruptible wait paths.
//! Call only after PID 1, command-line token and guest-device authorization.

#[cfg(not(all(target_os = "linux", target_arch = "x86_64")))]
compile_error!("locked_probe requires the declared Linux x86_64 guest ABI");

use std::{
    ffi::c_void,
    fs, io,
    os::fd::{AsRawFd, FromRawFd, OwnedFd},
    ptr::null_mut,
    sync::{mpsc, Arc},
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};

const CLOEXEC: i32 = 0x80000;
const CLOCK_MONOTONIC: i32 = 1;
const WAIT: Duration = Duration::from_secs(5);
const CLEANUP: Duration = Duration::from_secs(2);
const SAMPLE: Duration = Duration::from_millis(2);

#[repr(C)]
struct Timespec {
    seconds: i64,
    nanoseconds: i64,
}
#[repr(C)]
struct Itimerspec {
    interval: Timespec,
    value: Timespec,
}
const _: () = assert!(size_of::<Itimerspec>() == 32);

unsafe extern "C" {
    fn eventfd(initial: u32, flags: i32) -> i32;
    fn timerfd_create(clock: i32, flags: i32) -> i32;
    fn timerfd_settime(fd: i32, flags: i32, new: *const Itimerspec, old: *mut Itimerspec) -> i32;
    fn gettid() -> i32;
    fn read(fd: i32, buffer: *mut c_void, count: usize) -> isize;
    fn write(fd: i32, buffer: *const c_void, count: usize) -> isize;
}

#[derive(Clone, Copy)]
enum Kind {
    Event,
    Timer,
}

impl Kind {
    fn create(self) -> io::Result<Arc<OwnedFd>> {
        // SAFETY: scalar libc calls create a new blocking descriptor. Fresh
        // eventfd is empty; fresh timerfd is disarmed, with no external producer.
        let raw = unsafe {
            match self {
                Self::Event => eventfd(0, CLOEXEC),
                Self::Timer => timerfd_create(CLOCK_MONOTONIC, CLOEXEC),
            }
        };
        if raw < 0 {
            return Err(io::Error::last_os_error());
        }
        // SAFETY: newly returned descriptor is wrapped exactly once. Arc keeps
        // it live even if a failing controller must detach an unfinished reader.
        Ok(Arc::new(unsafe { OwnedFd::from_raw_fd(raw) }))
    }

    fn release(self, fd: &OwnedFd) -> io::Result<()> {
        match self {
            Self::Event => {
                let value = 23u64.to_ne_bytes();
                // SAFETY: eight readable bytes and retained eventfd. Only this
                // controller writes; at most two writes of 23 cannot fill it.
                let ret = unsafe { write(fd.as_raw_fd(), value.as_ptr().cast(), value.len()) };
                if ret < 0 {
                    return Err(io::Error::last_os_error());
                }
                require(ret == 8, "short eventfd producer write")
            }
            Self::Timer => {
                let timer = Itimerspec {
                    interval: Timespec {
                        seconds: 0,
                        nanoseconds: 0,
                    },
                    value: Timespec {
                        seconds: 0,
                        nanoseconds: 100_000_000,
                    },
                };
                // SAFETY: exact x86_64 timespec ABI and live FD; one-shot relative
                // timer. This also releases a blocked reader during failure cleanup.
                if unsafe { timerfd_settime(fd.as_raw_fd(), 0, &timer, null_mut()) } < 0 {
                    return Err(io::Error::last_os_error());
                }
                Ok(())
            }
        }
    }

    fn expected(self) -> u64 {
        match self {
            Self::Event => 23,
            Self::Timer => 1,
        }
    }
}

fn require(condition: bool, message: &str) -> io::Result<()> {
    if condition {
        Ok(())
    } else {
        Err(io::Error::other(message))
    }
}

// An acknowledgment is not a join. Retain the result while waiting for actual
// thread completion; never join an unacknowledged or unfinished thread.
struct Job<T> {
    receiver: mpsc::Receiver<io::Result<T>>,
    handle: Option<JoinHandle<()>>,
    result: Option<io::Result<T>>,
}
impl<T: Send + 'static> Job<T> {
    fn spawn(
        name: &str,
        operation: impl FnOnce() -> io::Result<T> + Send + 'static,
    ) -> io::Result<Self> {
        let (sender, receiver) = mpsc::channel();
        let handle = thread::Builder::new()
            .name(name.to_owned())
            .spawn(move || {
                let _ = sender.send(operation());
            })?;
        Ok(Self {
            receiver,
            handle: Some(handle),
            result: None,
        })
    }

    fn finish(&mut self, limit: Duration) -> io::Result<T> {
        let deadline = Instant::now() + limit;
        if self.result.is_none() {
            self.result = Some(
                self.receiver
                    .recv_timeout(limit)
                    .map_err(|error| io::Error::other(format!("worker result: {error}")))?,
            );
        }
        let handle = self
            .handle
            .as_ref()
            .ok_or_else(|| io::Error::other("worker already joined"))?;
        while !handle.is_finished() {
            if Instant::now() >= deadline {
                return Err(io::Error::other("worker acknowledged but did not finish"));
            }
            thread::sleep(SAMPLE);
        }
        // Completion was observed separately from the result; only now join.
        self.handle
            .take()
            .unwrap()
            .join()
            .map_err(|_| io::Error::other("worker panicked"))?;
        self.result.take().unwrap()
    }

    fn unfinished(&self) -> bool {
        self.handle.is_some()
    }
}

fn sleeping(tid: i32) -> io::Result<bool> {
    let stat = fs::read_to_string(format!("/proc/self/task/{tid}/stat"))?;
    // comm may contain spaces/parentheses; the final ')' precedes state field 3.
    let (_, tail) = stat
        .rsplit_once(')')
        .ok_or_else(|| io::Error::other("malformed task stat"))?;
    Ok(tail.split_ascii_whitespace().next() == Some("S"))
}

fn read_snapshot(tid: i32, fd: i32) -> io::Result<Option<String>> {
    if !sleeping(tid)? {
        return Ok(None);
    }
    let syscall = fs::read_to_string(format!("/proc/self/task/{tid}/syscall"))?;
    let fields: Vec<_> = syscall.split_ascii_whitespace().collect();
    let hex = |field: &str| u64::from_str_radix(field.strip_prefix("0x").unwrap_or(field), 16).ok();
    // x86_64 read=0, arg0=FD, arg2=count. A running/futex/other syscall does not
    // establish the intended blocked read, even when task state is sleeping.
    let matches = fields.len() == 9
        && fields[0] == "0"
        && hex(fields[1]) == Some(fd as u64)
        && hex(fields[3]) == Some(8);
    if matches && sleeping(tid)? {
        Ok(Some(syscall))
    } else {
        Ok(None)
    }
}

fn observe_read(tid: i32, fd: Arc<OwnedFd>) -> io::Result<()> {
    let deadline = Instant::now() + WAIT;
    let mut previous = None;
    loop {
        let current = read_snapshot(tid, fd.as_raw_fd())?;
        if current.is_some() && current == previous {
            return Ok(());
        }
        previous = current;
        if Instant::now() >= deadline {
            return Err(io::Error::other(
                "read syscall with matching FD/count did not remain asleep",
            ));
        }
        thread::sleep(SAMPLE);
    }
}

fn blocking_read(kind: Kind) -> io::Result<()> {
    let fd = kind.create()?;
    let (tid_sender, tid_receiver) = mpsc::channel();
    let reader_fd = Arc::clone(&fd);
    let mut reader = Job::spawn("locked-reader", move || {
        // SAFETY: gettid has no pointer arguments and identifies this live thread.
        let tid = unsafe { gettid() };
        require(tid > 0, "invalid worker TID")?;
        tid_sender
            .send(tid)
            .map_err(|_| io::Error::other("TID receiver disappeared"))?;
        let mut value = 0u64;
        // SAFETY: eight writable bytes, descriptor retained by this worker Arc.
        // Intentionally blocking; controller publishes only after proc evidence.
        let ret = unsafe { read(reader_fd.as_raw_fd(), (&mut value as *mut u64).cast(), 8) };
        if ret < 0 {
            return Err(io::Error::last_os_error());
        }
        require(ret == 8, "short blocking read")?;
        Ok(value)
    })?;
    let mut observer = None;
    let outcome = (|| {
        let tid = tid_receiver
            .recv_timeout(WAIT)
            .map_err(|error| io::Error::other(format!("worker TID: {error}")))?;
        let observer_fd = Arc::clone(&fd);
        // /proc syscall observation itself can wait inside the kernel. Isolate
        // it so the controller still has a deadline and can release the reader.
        observer = Some(Job::spawn("locked-observer", move || {
            observe_read(tid, observer_fd)
        })?);
        observer.as_mut().unwrap().finish(WAIT + SAMPLE)?;
        kind.release(&fd)?;
        let value = reader.finish(WAIT)?;
        require(
            value == kind.expected(),
            "blocking read payload/expiration count mismatch",
        )
    })();
    if let Err(error) = outcome {
        let mut failures = Vec::new();
        if let Err(cleanup) = kind.release(&fd) {
            failures.push(format!("release: {cleanup}"));
        }
        if reader.unfinished() {
            if let Err(cleanup) = reader.finish(CLEANUP) {
                failures.push(format!("reader: {cleanup}"));
            }
        }
        if let Some(observer) = &mut observer {
            if observer.unfinished() {
                if let Err(cleanup) = observer.finish(CLEANUP) {
                    failures.push(format!("observer: {cleanup}"));
                }
            }
        }
        // Unfinished handles detach on drop; their Arcs retain FDs. The error
        // prevents PASS and init reboots. VM timeout is final kernel containment.
        return Err(io::Error::other(format!(
            "{error}; cleanup [{}]",
            failures.join("; ")
        )));
    }
    Ok(())
}

pub fn run() -> io::Result<()> {
    for (name, kind) in [
        ("eventfd_blocking_read", Kind::Event),
        ("timerfd_blocking_read", Kind::Timer),
    ] {
        blocking_read(kind)
            .map_err(|error| io::Error::other(format!("locked probe {name}: {error}")))?;
        super::marker(&format!("RUSIX_LOCKED_PASS {name}"))?;
    }
    Ok(())
}
