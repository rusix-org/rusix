// SPDX-License-Identifier: GPL-2.0-only
//! Guest-only acquisition harness. Capture completion is NOT a test PASS.
use std::{
    collections::BTreeMap,
    fs,
    io::{self, BufRead, Write},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::mpsc,
    thread,
    time::{Duration, Instant},
};
const TRACE: &str = "/sys/kernel/tracing/instances/rusix_task_faults";
const DEBUG: &str = "/sys/kernel/debug";
unsafe extern "C" {
    fn getppid() -> i32;
    fn kill(pid: i32, sig: i32) -> i32;
    fn prctl(option: i32, ...) -> i32;
    fn waitpid(pid: i32, status: *mut i32, options: i32) -> i32;
}
fn fail(s: &str) -> io::Error {
    io::Error::other(s)
}
fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}
fn emit(name: &str, bytes: &[u8]) {
    println!("RUSIX_TASK_FAULT_ARTIFACT {name} {}", hex(bytes));
}
fn put(path: impl AsRef<Path>, value: impl AsRef<[u8]>) -> io::Result<()> {
    fs::write(path, value)
}
fn load_calibration() -> io::Result<BTreeMap<String, String>> {
    let raw = fs::read_to_string("/calibration.tsv")?;
    let mut map = BTreeMap::new();
    for line in raw.lines() {
        let (key, value) = line
            .split_once('\t')
            .ok_or_else(|| fail("bad calibration row"))?;
        if map.insert(key.into(), value.into()).is_some() {
            return Err(fail("duplicate calibration key"));
        }
    }
    let required = [
        "schema",
        "policy_base",
        "build_source",
        "implementation",
        "notes_hex",
        "range_symbol",
        "range_start",
        "range_end",
        "slab_frame",
        "stack_frame",
    ];
    if map.len() != required.len()
        || required.iter().any(|k| !map.contains_key(*k))
        || map["schema"] != "1"
        || map["policy_base"] != "8fd3defabb841083192cd1d9c4eb1cde83027579"
        || map["build_source"].len() != 40
        || !map["build_source"].bytes().all(|b| b.is_ascii_hexdigit())
        || !["c", "rust"].contains(&map["implementation"].as_str())
    {
        return Err(fail("unreviewed calibration identity"));
    }
    if hex(&fs::read("/sys/kernel/notes")?) != map["notes_hex"] {
        return Err(fail("running kernel notes mismatch"));
    }
    let start = u64::from_str_radix(map["range_start"].trim_start_matches("0x"), 16)
        .map_err(|_| fail("bad range"))?;
    let end = u64::from_str_radix(map["range_end"].trim_start_matches("0x"), 16)
        .map_err(|_| fail("bad range"))?;
    if start == 0 || end <= start || end - start > 1048576 {
        return Err(fail("invalid required range"));
    }
    let symbols = fs::read_to_string("/proc/kallsyms")?;
    let found: Vec<_> = symbols
        .lines()
        .filter_map(|l| {
            let p: Vec<_> = l.split_whitespace().collect();
            if p.len() == 3 && p[2] == map["range_symbol"] {
                Some(p[0])
            } else {
                None
            }
        })
        .collect();
    if found.len() != 1 || u64::from_str_radix(found[0], 16).ok() != Some(start) {
        return Err(fail("symbol/running-address mismatch"));
    }
    for key in ["slab_frame", "stack_frame"] {
        if map[key].is_empty() || map[key].contains('\n') {
            return Err(fail("missing attributed frame"));
        }
    }
    // Exact end address and allocation-return-PC attribution must be reviewed
    // against actual linked disassembly before supplying this packet.
    emit("calibration.tsv", raw.as_bytes());
    Ok(map)
}
fn equivalent(a: &str, b: &str) -> bool {
    fn number(v: &str) -> Option<u64> {
        match v.trim() {
            "Y" => Some(1),
            "N" => Some(0),
            v => {
                if let Some(h) = v.strip_prefix("0x") {
                    u64::from_str_radix(h, 16).ok()
                } else {
                    v.parse().ok()
                }
            }
        }
    }
    a.trim() == b.trim() || number(a).is_some_and(|n| Some(n) == number(b))
}
struct Restore(Vec<(PathBuf, Vec<u8>)>);
impl Restore {
    fn set(&mut self, path: impl AsRef<Path>, value: &str) -> io::Result<()> {
        let path = path.as_ref();
        if !self.0.iter().any(|(p, _)| p == path) {
            self.0.push((path.into(), fs::read(path)?));
        }
        put(path, value)?;
        if !equivalent(&fs::read_to_string(path)?, value) {
            return Err(fail("knob readback mismatch"));
        }
        Ok(())
    }
    fn restore(&mut self) -> io::Result<()> {
        let mut error = None;
        while let Some((p, v)) = self.0.pop() {
            if let Err(e) = put(&p, &v).and_then(|_| {
                if equivalent(&fs::read_to_string(&p)?, &String::from_utf8_lossy(&v)) {
                    Ok(())
                } else {
                    Err(fail("restore readback mismatch"))
                }
            }) {
                error = Some(e);
            }
        }
        error.map_or(Ok(()), Err)
    }
}
impl Drop for Restore {
    fn drop(&mut self) {
        let _ = self.restore();
    }
}
struct Events {
    names: Vec<&'static str>,
}
impl Events {
    fn close(&mut self) -> io::Result<()> {
        if Path::new(TRACE).exists() {
            put(format!("{TRACE}/tracing_on"), "0")?;
            put(format!("{TRACE}/events/enable"), "0")?;
            for name in ["page_decision", "slab_decision"] {
                let path = format!("{TRACE}/events/rusix_fail/{name}/trigger");
                if Path::new(&path).exists() {
                    put(path, "!stacktrace")?;
                }
            }
            fs::remove_dir(TRACE)?;
        }
        while let Some(name) = self.names.last() {
            let mut f = fs::OpenOptions::new()
                .append(true)
                .open("/sys/kernel/tracing/kprobe_events")?;
            writeln!(f, "-:rusix_fail/{name}")?;
            self.names.pop();
        }
        Ok(())
    }
}
impl Drop for Events {
    fn drop(&mut self) {
        let _ = self.close();
    }
}
fn collect_attempt(label: &str, nth: u32, events: &Events) -> io::Result<()> {
    let mut worker = Command::new("/fault-worker")
        .arg(nth.to_string())
        .env_clear()
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()?;
    let pid = worker.id();
    let stdout = worker.stdout.take().ok_or_else(|| fail("no worker pipe"))?;
    let (tx, rx) = mpsc::channel();
    thread::spawn(move || {
        for line in io::BufReader::new(stdout).lines() {
            if tx.send(line).is_err() {
                break;
            }
        }
    });
    let mut reaped = false;
    let operation = (|| {
        let ready = rx
            .recv_timeout(Duration::from_secs(2))
            .map_err(|_| fail("worker readiness timeout"))??;
        if ready != format!("READY {pid}") {
            return Err(fail("worker PID mismatch"));
        }
        put(format!("{TRACE}/tracing_on"), "0")?;
        put(format!("{TRACE}/trace"), "")?;
        for name in &events.names {
            put(
                format!("{TRACE}/events/rusix_fail/{name}/filter"),
                format!("common_pid == {pid}"),
            )?;
        }
        for name in ["kmem_cache_alloc", "kmem_cache_free"] {
            put(
                format!("{TRACE}/events/kmem/{name}/filter"),
                format!("common_pid == {pid}"),
            )?;
        }
        put(
            format!("{TRACE}/events/sched/sched_process_fork/filter"),
            format!("common_pid == {pid}"),
        )?;
        for (event, condition) in [
            (
                "page_decision",
                if nth == 0 {
                    "injected == 0"
                } else {
                    "injected == 1"
                },
            ),
            (
                "slab_decision",
                if nth == 0 {
                    "result == 0"
                } else {
                    "result == -12"
                },
            ),
        ] {
            put(
                format!("{TRACE}/events/rusix_fail/{event}/trigger"),
                "!stacktrace",
            )?;
            put(
                format!("{TRACE}/events/rusix_fail/{event}/trigger"),
                format!("stacktrace if common_pid == {pid} && {condition}"),
            )?;
        }
        put(format!("{TRACE}/tracing_on"), "1")?;
        worker
            .stdin
            .as_mut()
            .ok_or_else(|| fail("no worker input"))?
            .write_all(b"G")?;
        let result = rx
            .recv_timeout(Duration::from_secs(6))
            .map_err(|_| fail("worker result timeout"))??;
        if !result.ends_with("child_status=0 retry_status=0") {
            return Err(fail("worker child/retry failed"));
        }
        put(format!("{TRACE}/tracing_on"), "0")?;
        emit(&format!("{label}.worker"), result.as_bytes());
        emit(
            &format!("{label}.trace"),
            &fs::read(format!("{TRACE}/trace"))?,
        );
        emit(
            &format!("{label}.probes"),
            &fs::read("/sys/kernel/tracing/kprobe_profile")?,
        );
        for cpu in [0, 1] {
            emit(
                &format!("{label}.cpu{cpu}"),
                &fs::read(format!("{TRACE}/per_cpu/cpu{cpu}/stats"))?,
            );
        }
        worker
            .stdin
            .as_mut()
            .ok_or_else(|| fail("no worker acknowledgment"))?
            .write_all(b"A")?;
        let until = Instant::now() + Duration::from_secs(1);
        loop {
            if let Some(status) = worker.try_wait()? {
                reaped = true;
                if !status.success() {
                    return Err(fail("worker failure"));
                }
                break;
            }
            if Instant::now() >= until {
                return Err(fail("worker exit timeout"));
            }
            thread::sleep(Duration::from_millis(5));
        }
        Ok(())
    })();
    if operation.is_err() && !reaped {
        // SAFETY: Worker sets its own group before READY/fork; PID kill also
        // covers failure before group setup. No PID has been reaped on timeout.
        unsafe {
            kill(-(pid as i32), 9);
            kill(pid as i32, 9);
        }
        let until = Instant::now() + Duration::from_secs(1);
        while Instant::now() < until {
            let mut status = 0;
            // SAFETY: Only owned process group children; WNOHANG is bounded.
            let got = unsafe { waitpid(-(pid as i32), &mut status, 1) };
            if got < 0 {
                break;
            }
            thread::sleep(Duration::from_millis(5));
        }
    }
    operation
}
fn run() -> io::Result<()> {
    // SAFETY: getppid takes no pointers and only reads process identity.
    if unsafe { getppid() } != 1
        || fs::read_to_string("/proc/1/comm")? != "rusix-fault-init\n"
        || fs::read_to_string("/proc/cmdline")?
            .split_whitespace()
            .filter(|x| *x == "rusix.task_faults=1")
            .count()
            != 1
    {
        return Err(fail("guest guard"));
    }
    // SAFETY: Exact guest identity/token checks passed. PR_SET_CHILD_SUBREAPER
    // changes only this controller; scalar varargs require no borrowed storage.
    if unsafe { prctl(36, 1usize, 0usize, 0usize, 0usize) } != 0 {
        return Err(io::Error::last_os_error());
    }
    let cal = load_calibration()?;
    if Path::new(TRACE).exists()
        || fs::read_to_string("/sys/kernel/tracing/kprobe_events")?
            .lines()
            .any(|line| {
                [
                    "rusix_fail/",
                    "page_decision",
                    "slab_decision",
                    "pages_result",
                ]
                .iter()
                .any(|name| line.contains(name))
            })
    {
        return Err(fail("owned tracing namespace already exists"));
    }
    // Every knob is read before replacement and restored on ordinary failure.
    let mut restore = Restore(Vec::new());
    for cap in ["failslab", "fail_page_alloc"] {
        for (key, value) in [
            ("probability", "0"),
            ("verbose", "0"),
            ("ignore-gfp-wait", "N"),
            ("stacktrace-depth", "32"),
            ("reject-start", "0"),
            ("reject-end", "0"),
        ] {
            restore.set(format!("{DEBUG}/{cap}/{key}"), value)?;
        }
        restore.set(format!("{DEBUG}/{cap}/require-start"), &cal["range_start"])?;
        restore.set(format!("{DEBUG}/{cap}/require-end"), &cal["range_end"])?;
    }
    restore.set(format!("{DEBUG}/failslab/cache-filter"), "Y")?;
    restore.set(format!("{DEBUG}/fail_page_alloc/ignore-gfp-highmem"), "Y")?;
    let cache = "/sys/kernel/slab/task_struct/failslab";
    for entry in fs::read_dir("/sys/kernel/slab")? {
        let p = entry?.path().join("failslab");
        if p.exists() && fs::read_to_string(&p)?.trim() != "0" {
            return Err(fail("preexisting enabled slab cache"));
        }
    }
    fs::create_dir(TRACE)?;
    let mut events = Events { names: Vec::new() };
    for (name,definition) in [("page_decision","r32:rusix_fail/page_decision should_fail_alloc_page order=$arg2:u32 injected=$retval:u8"),("slab_decision","r32:rusix_fail/slab_decision should_failslab result=$retval:s32"),("pages_result","r32:rusix_fail/pages_result __alloc_pages_noprof order=$arg2:u32 result=$retval:x64")] {
        let mut f=fs::OpenOptions::new().append(true).open("/sys/kernel/tracing/kprobe_events")?;writeln!(f,"{definition}")?;events.names.push(name);
        emit(&format!("{name}.format"),&fs::read(format!("{TRACE}/events/rusix_fail/{name}/format"))?);
        put(format!("{TRACE}/events/rusix_fail/{name}/enable"),"1")?;
    }
    put(format!("{TRACE}/options/sym-offset"), "1")?;
    put(format!("{TRACE}/buffer_size_kb"), "256")?;
    for (event, condition) in [
        ("page_decision", "injected == 1"),
        ("slab_decision", "result == -12"),
    ] {
        put(
            format!("{TRACE}/events/rusix_fail/{event}/trigger"),
            format!("stacktrace if {condition}"),
        )?;
    }
    for event in [
        "kmem/kmem_cache_alloc",
        "kmem/kmem_cache_free",
        "sched/sched_process_fork",
    ] {
        put(format!("{TRACE}/events/{event}/enable"), "1")?;
        emit(
            &format!("{}.format", event.replace('/', "_")),
            &fs::read(format!("{TRACE}/events/{event}/format"))?,
        );
    }
    restore.set(cache, "0")?;
    restore.set(format!("{DEBUG}/fail_page_alloc/min-order"), "4294967295")?;
    collect_attempt("calibration", 0, &events)?;
    restore.set(cache, "1")?;
    if fs::read_to_string(cache)?.trim() != "1" {
        return Err(fail("slab flag rejected"));
    }
    collect_attempt("slab-1", 1, &events)?;
    restore.set(cache, "0")?;
    restore.set(format!("{DEBUG}/fail_page_alloc/min-order"), "2")?;
    for nth in 1..=16 {
        collect_attempt(&format!("stack-{nth}"), nth, &events)?;
    }
    events.close()?;
    restore.restore()?;
    println!("RUSIX_TASK_FAULT_CAPTURE_COMPLETE");
    Ok(())
}
fn main() {
    if let Err(e) = run() {
        eprintln!("RUSIX_TASK_FAULT_CAPTURE_FAIL {e}");
        std::process::exit(1);
    }
}
