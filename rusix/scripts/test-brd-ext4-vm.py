#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Stage pinned ordinary utilities and run ext4 and wake consumers only in a bounded QEMU guest."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
from rusix_paths import resolve_paths
import server_target

# Share hash/provenance and newc primitives with the existing six-case runner;
# its guest workload and acceptance gate are not changed or reused as ext4 proof.
_spec = importlib.util.spec_from_file_location("brd_common", Path(__file__).with_name("test-brd-vm.py"))
_common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_common)
digest = _common.digest
check_hashes = _common.check_hashes
source_state = _common.source_state
first_line = _common.first_line

LOCKED_CASES = ("eventfd_blocking_read", "timerfd_blocking_read")
CASES = ("mkfs", "initial_write", "remount_read", "mutate", "final_read", "fsck")
WAKE_CASES = ("pipe_poll", "epoll_pipe_eventfd", "epoll_oneshot_rearm", "epoll_del_close")
REQUIRED_CONFIG = ("64BIT", "BLOCK", "BLK_DEV_RAM", "EXT4_FS", "PROC_FS", "SMP",
                   "FUTEX", "MULTIUSER", "BINFMT_ELF", "BINFMT_SCRIPT", "EPOLL", "EVENTFD",
                   "BLK_DEV_INITRD", "SERIAL_8250_CONSOLE", "TIMERFD", "HAVE_ARCH_TRACEHOOK")
TOOLS = ("mount", "umount", "blockdev", "cat", "cp", "chmod", "ln", "truncate",
         "dd", "sync", "sha256sum", "stat", "cmp", "mv", "rm")
TOOL_PATH = "/usr/sbin:/usr/bin:/sbin:/bin"


def accept_console(console, qemu_exit):
    if qemu_exit != 0:
        raise ValueError(f"QEMU failed or timed out: exit {qemu_exit}")
    if re.search(r"(?i:\bwarning\b)|\bBUG\b|Oops:|Kernel panic|CPU feature dependency check failure|ACPI (?:BIOS )?(?:Error|Exception|Warning)|ACPI: Unable to load|EXT4-fs error|Buffer I/O error|I/O error, dev", console):
        raise ValueError("Kernel warning, oops, BUG, or panic in console")
    expected = ["RUSIX_EXT4_START"] + [f"RUSIX_EXT4_PASS {case}" for case in CASES]
    expected += [f"RUSIX_WAKE_PASS {case}" for case in WAKE_CASES]
    expected += [f"RUSIX_LOCKED_PASS {case}" for case in LOCKED_CASES]
    expected += ["RUSIX_EXT4_SUCCESS cases=6"]
    markers = [line for line in console.splitlines()
               if any(prefix in line for prefix in ("RUSIX_EXT4_", "RUSIX_WAKE_", "RUSIX_LOCKED_"))]
    if markers != expected:
        raise ValueError(f"Ext4/wake/locked inventory/order mismatch: {markers!r}")
    return {"status": "PASS", "cases": list(CASES), "wake_cases": list(WAKE_CASES),
            "locked_cases": list(LOCKED_CASES), "qemu_exit": qemu_exit}


def validate_selection(profile, selection, config, core_selection=None):
    expected = {"brd-ext4-fixed-c": "brd-c-parameter-fix", "brd-ext4-c": "brd-c", "brd-ext4-rust": "brd-rust",
                "core-ext4-c": "brd-rust", "core-ext4-rust": "brd-rust",
                "server": "brd-rust", "server-c": "brd-rust"}.get(profile)
    if expected is None or selection != f"implementation={expected}":
        raise ValueError("Ext4 build profile and BRD selection proof must agree")
    settings = set(config.splitlines())
    for name in REQUIRED_CONFIG:
        if f"CONFIG_{name}=y" not in settings:
            raise ValueError(f"Missing required CONFIG_{name}=y")
    _common.validate_brd_choice(expected, config)
    if "CONFIG_KUNIT=y" in settings:
        raise ValueError("Ext4 guests must disable KUnit")
    _common.validate_core_selection(profile, config, core_selection)
    if profile in server_target.PROFILES:
        source = Path(__file__).resolve().parents[1] / "configs/x86_64-server.config"
        server_target.validate_resolved(source.read_text(), profile, config)
    return expected


def parse_elf(output):
    if "Advanced Micro Devices X86-64" not in output:
        raise ValueError("Rootfs ELF must target x86_64")
    interpreters = re.findall(r"Requesting program interpreter:\s*([^\]]+)\]", output)
    if len(interpreters) > 1:
        raise ValueError("Multiple ELF interpreters")
    needed = re.findall(r"\(NEEDED\).*Shared library: \[([^\]]+)\]", output)
    return interpreters[0] if interpreters else None, needed


def parse_ldd(output, needed):
    """Parse only trusted installed Debian objects; never execute guest inputs."""
    found = {}
    for line in output.splitlines():
        if "not found" in line:
            raise ValueError(f"Unresolved dynamic dependency: {line}")
        match = re.fullmatch(r"\s*(\S+)\s+=>\s+(/\S+)\s+\(0x[0-9a-fA-F]+\)\s*", line)
        if match:
            soname, path = match.groups()
            if soname in found and found[soname] != path:
                raise ValueError(f"Ambiguous dependency: {soname}")
            found[soname] = path
        elif re.fullmatch(r"\s*/\S+\s+\(0x[0-9a-fA-F]+\)\s*", line):
            # libc may list its loader as DT_NEEDED, while ldd prints that
            # loader directly rather than as a soname => path mapping.
            path = line.split()[0]
            name = Path(path).name
            if name in found and found[name] != path:
                raise ValueError(f"Ambiguous direct dependency: {name}")
            found[name] = path
        elif re.fullmatch(r"\s*linux-vdso\.so\.\d+\s+\(0x[0-9a-fA-F]+\)\s*", line):
            pass
        elif line.strip():
            raise ValueError(f"Unexpected ldd record: {line}")
    if any(name not in found for name in needed):
        raise ValueError("ldd did not resolve every DT_NEEDED entry")
    return [Path(found[name]) for name in needed]


def trusted_path(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Dependency path must be absolute without traversal: {path}")
    resolved = path.resolve(strict=True)
    roots = tuple(Path(root) for root in ("/usr/bin", "/usr/sbin", "/usr/lib", "/lib", "/lib64"))
    if not resolved.is_file() or not any(resolved.is_relative_to(root) for root in roots):
        raise ValueError(f"Dependency outside installed system paths: {path}")
    return resolved


def guest_path(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or path == Path("/"):
        raise ValueError(f"Invalid guest file path: {path}")
    return path.as_posix().lstrip("/")


class Rootfs:
    """In-memory staging; device nodes exist only as cpio metadata."""
    def __init__(self):
        self.files = {}
        self.sources = {}
        self.elf_records = {}

    def add(self, guest, source, mode=0o755):
        name = guest_path(guest)
        source = Path(source).resolve(strict=True)
        data = source.read_bytes()
        entry = (stat.S_IFREG | mode, data, 0, 0)
        if name in self.files and self.files[name] != entry:
            raise ValueError(f"Conflicting rootfs destination: {guest}")
        self.files[name] = entry
        self.sources[name] = {"source": str(source), "sha256": hashlib.sha256(data).hexdigest(),
                              "mode": oct(mode)}

    def elf(self, guest, source):
        name = guest_path(guest)
        source = trusted_path(source)
        if name in self.files:
            if self.sources[name]["source"] != str(source):
                raise ValueError(f"Conflicting ELF dependency: {guest}")
            return
        self.add(guest, source)
        output = subprocess.check_output(["/usr/bin/readelf", "-W", "-h", "-l", "-d", str(source)], text=True)
        interpreter, needed = parse_elf(output)
        record = {"readelf": output}
        self.elf_records[name] = record
        if interpreter:
            self.elf(interpreter, interpreter)
        if needed:
            # These are official installed utilities/libraries from the pinned
            # fixture image. ldd is not used on /init or arbitrary source files.
            output = subprocess.check_output(["/usr/bin/ldd", str(source)], text=True,
                                             stderr=subprocess.STDOUT,
                                             env={"PATH": TOOL_PATH, "LC_ALL": "C"})
            record["ldd"] = output
            for dependency in parse_ldd(output, needed):
                self.elf(str(dependency), dependency)

    def archive(self):
        entries = dict(self.files)
        for name, major, minor, kind in (
            ("console", 5, 1, stat.S_IFCHR), ("kmsg", 1, 11, stat.S_IFCHR), ("ram0", 1, 0, stat.S_IFBLK),
            ("null", 1, 3, stat.S_IFCHR), ("zero", 1, 5, stat.S_IFCHR),
            ("random", 1, 8, stat.S_IFCHR), ("urandom", 1, 9, stat.S_IFCHR),
        ):
            entries[f"dev/{name}"] = (kind | 0o600, b"", major, minor)
        directories = {"proc", "sys", "mnt", "mnt/test", "expected", "dev", "etc", "run", "tmp"}
        for name in entries:
            directories.update(str(parent) for parent in Path(name).parents if str(parent) != ".")
        if directories & entries.keys():
            raise ValueError("Rootfs file/directory collision")
        ordered = [(name, stat.S_IFDIR | (0o1777 if name == "tmp" else 0o755), b"", 0, 0)
                   for name in sorted(directories, key=lambda name: (name.count("/"), name))]
        ordered += [(name, *entry) for name, entry in sorted(entries.items())]
        return _common.newc(ordered + [("TRAILER!!!", 0, b"", 0, 0)])

    def verify_sources(self):
        for entry in self.sources.values():
            if digest(Path(entry["source"])) != entry["sha256"]:
                raise ValueError(f"Staged input changed: {entry['source']}")


def validate_inventory(installed, image_lock, tracked_lock):
    if not tracked_lock or installed != image_lock or installed != tracked_lock:
        raise ValueError("Installed/image/tracked fixture package inventories differ")


def fixture_identity(evidence, expected_lock):
    image = os.environ.get("RUSIX_EXT4_IMAGE_ID", "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("Supply inspected fixture image ID in RUSIX_EXT4_IMAGE_ID")
    lock = Path("/opt/rusix/ext4-packages.lock")
    inventory = subprocess.check_output(["/usr/bin/dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\n"], text=True)
    inventory = "\n".join(sorted(inventory.splitlines())) + "\n"
    validate_inventory(inventory, lock.read_text(), expected_lock.read_text())
    shutil.copy2(lock, evidence / "rootfs-packages.lock")
    (evidence / "container-image-id.txt").write_text(image + "\n")
    return image


def run(args, paths, evidence):
    image_id = fixture_identity(evidence, paths.project / "tests/brd-ext4/ext4-packages.lock")
    accel = os.environ.get("RUSIX_QEMU_ACCEL", "tcg")
    if accel not in ("tcg", "kvm"):
        raise ValueError("RUSIX_QEMU_ACCEL must be tcg or kvm")
    revision = source_state(paths.source)
    build, proof = args.build.resolve(), args.build_evidence.resolve()
    kernel, config = build / "arch/x86/boot/bzImage", build / ".config"
    if (proof / "build.exit").read_text().strip() != "0":
        raise ValueError("Kernel build did not pass")
    if first_line(proof / "environment.log") != revision or first_line(proof / "source-after.commit") != revision:
        raise ValueError("Kernel source revision mismatch")
    if (proof / "source-after.status").read_bytes():
        raise ValueError("Kernel source changed during build")
    profile = first_line(proof / "profile.txt")
    implementation = validate_selection(profile, first_line(proof / "selection.log"),
                                        config.read_text(),
                                        first_line(proof / "completion-selection.log")
                                        if profile.startswith("core-ext4-") or profile in server_target.PROFILES else None)
    if profile in server_target.PROFILES:
        server_target.verify(paths.project / "configs/x86_64-server.config", profile, proof, config)
    check_hashes(proof / "build.sha256", [kernel, config])
    if config.read_bytes() != (proof / "config").read_bytes():
        raise ValueError("Resolved configuration differs from build evidence")
    artifacts = paths.output / "builds" / f"ext4-vm-{args.label}"
    artifacts.mkdir(parents=True, exist_ok=False)
    shutil.copytree(proof, evidence / "kernel-build")
    image = artifacts / "bzImage"
    shutil.copy2(kernel, image)
    check_hashes(proof / "build.sha256", [kernel, config])
    if digest(image) != digest(kernel):
        raise ValueError("Kernel changed while copying")
    fixture = paths.project / "tests/brd-ext4"
    init = artifacts / "init"
    command = ["/usr/bin/rustc", "--edition", "2021", "--target", "x86_64-unknown-linux-gnu",
               "-C", "target-feature=+crt-static", "-C", "panic=abort", "-C", "opt-level=2",
               str(fixture / "init.rs"), "-o", str(init)]
    (evidence / "compile-command.sh").write_text(shlex.join(command) + "\n")
    (evidence / "rustc-version.log").write_text(subprocess.check_output(["/usr/bin/rustc", "--version", "--verbose"], text=True))
    with (evidence / "compile.log").open("w") as log:
        compiled = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    (evidence / "compile.exit").write_text(f"{compiled.returncode}\n")
    compiled.check_returncode()
    elf = subprocess.check_output(["/usr/bin/readelf", "-W", "-h", "-l", "-d", str(init)], text=True)
    (evidence / "init-elf.log").write_text(elf)
    interpreter, needed = parse_elf(elf)
    if interpreter or needed:
        raise ValueError("Guest init must be static without interpreter or dependencies")
    rootfs = Rootfs()
    rootfs.add("/init", init)
    rootfs.add("/ext4-workload.sh", fixture / "workload.sh", 0o644)
    for name in ("SHA256SUMS", "FINAL.sha256"):
        rootfs.add(f"/expected/{name}", fixture / name, 0o644)
    rootfs.add("/etc/mke2fs.conf", "/etc/mke2fs.conf", 0o644)
    rootfs.elf("/bin/sh", "/usr/bin/dash")
    for name in TOOLS + ("mkfs.ext4", "e2fsck"):
        source = shutil.which(name, path=TOOL_PATH)
        if source is None:
            raise ValueError(f"Fixture image lacks {name}")
        destination = f"/usr/sbin/{name}" if name in ("mkfs.ext4", "e2fsck") else f"/usr/bin/{name}"
        rootfs.elf(destination, source)
    rootfs.verify_sources()
    archive = artifacts / "initramfs.cpio"
    archive.write_bytes(rootfs.archive())
    (evidence / "rootfs-files.json").write_text(json.dumps(rootfs.sources, indent=2, sort_keys=True) + "\n")
    (evidence / "rootfs-elf.json").write_text(json.dumps(rootfs.elf_records, indent=2, sort_keys=True) + "\n")
    sources = [Path(__file__).resolve(), Path(_common.__file__), Path(server_target.__file__),
               paths.project / "scripts/rusix_paths.py"]
    sources += [path for path in fixture.iterdir() if path.is_file()]
    metadata = {"source_revision": revision, "implementation": implementation, "profile": profile,
                "container_image": image_id, "config_sha256": digest(config),
                "sources": {str(path.relative_to(paths.source)): digest(path) for path in sources},
                "artifacts": {str(path): digest(path) for path in (image, init, archive)}}
    (evidence / "inputs.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    command = ["/usr/bin/timeout", "--kill-after=5s", "240s", "/usr/bin/qemu-system-x86_64",
               "-machine", "q35", "-accel", accel, "-cpu", "qemu64" if accel == "kvm" else "max",
               "-m", "512M", "-smp", "2", "-display", "none", "-serial", "stdio",
               "-monitor", "none", "-nic", "none", "-no-reboot", "-kernel", str(image),
               "-initrd", str(archive), "-append", "console=ttyS0 rdinit=/init rusix.brd_ext4=1 "
               "brd.rd_nr=1 brd.rd_size=65536 brd.max_part=1 panic=-1 kunit.enable=0 printk.time=0 printk.devkmsg=on loglevel=7"]
    (evidence / "command.sh").write_text(shlex.join(command) + "\n")
    (evidence / "qemu-version.log").write_text(subprocess.check_output(["/usr/bin/qemu-system-x86_64", "--version"], text=True))
    with (evidence / "console.log").open("wb") as log:
        guest = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    (evidence / "qemu.exit").write_text(f"{guest.returncode}\n")
    result = accept_console((evidence / "console.log").read_text(errors="replace"), guest.returncode)
    if source_state(paths.source) != revision:
        raise ValueError("Source changed during verification")
    rootfs.verify_sources()
    for path, expected in metadata["artifacts"].items():
        if digest(Path(path)) != expected:
            raise ValueError(f"Artifact changed: {path}")
    result["implementation"] = implementation
    (evidence / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Ext4 {implementation}: six ext4, four wake and two locked cases passed; evidence {evidence}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("label")
    parser.add_argument("--build-evidence", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.label):
        parser.error("Use only letters, numbers, underscore and hyphen in labels")
    paths = resolve_paths()
    evidence = paths.output / "logs" / f"{args.label}-ext4.run"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    try:
        evidence.mkdir()
    except FileExistsError:
        parser.error("Evidence label already used")
    status = 1
    try:
        run(args, paths, evidence)
        status = 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        (evidence / "error.log").write_text(str(error) + "\n")
        print(f"Ext4 verification failed: {error}; evidence {evidence}", file=sys.stderr)
    finally:
        (evidence / "runner.exit").write_text(f"{status}\n")
    return status


if __name__ == "__main__":
    sys.exit(main())
