#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Run the C BRD contract probe only inside a bounded x86_64 QEMU guest."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys

from rusix_paths import resolve_paths

CASES = ("geometry", "sparse_read", "crossing_write", "discard_edges",
         "concurrent_insert", "accounting")
REQUIRED_CONFIG = ("64BIT", "BLOCK", "BLK_DEV_RAM", "PROC_FS", "DEBUG_FS",
                   "SMP", "FUTEX", "BINFMT_ELF", "BLK_DEV_INITRD",
                   "SERIAL_8250_CONSOLE")


def accept_console(console, qemu_exit):
    """Require the exact ordered inventory and completion, without kernel faults."""
    if qemu_exit != 0:
        raise ValueError(f"QEMU failed or timed out: exit {qemu_exit}")
    if re.search(r"\b(?:WARNING|BUG)\b|Oops:|Kernel panic|CPU feature dependency check failure", console):
        raise ValueError("Kernel warning, oops, BUG, or panic in console")
    markers = [line for line in console.splitlines() if "RUSIX_BRD_" in line]
    expected = [f"RUSIX_BRD_PASS {name}" for name in CASES]
    expected.append(f"RUSIX_BRD_SUCCESS cases={len(CASES)}")
    if markers != expected:
        raise ValueError(f"BRD case inventory/order mismatch: {markers!r}")
    return {"status": "PASS", "cases": list(CASES), "qemu_exit": qemu_exit}


def validate_selection(profile, selection, config):
    """Bind the requested implementation to its build proof and resolved config."""
    implementation = {"brd": "brd-c", "brd-rust": "brd-rust",
                      "brd-ext4-c": "brd-c", "brd-ext4-rust": "brd-rust"}.get(profile)
    if implementation is None:
        raise ValueError("A BRD or ext4 build profile is required")
    if selection != f"implementation={implementation}":
        raise ValueError("Build evidence does not identify the selected BRD implementation")
    settings = set(config.splitlines())
    if ("CONFIG_RUSIX_BRD_RUST=y" in settings) != (implementation == "brd-rust"):
        raise ValueError("Resolved configuration contradicts BRD selection")
    for name in REQUIRED_CONFIG:
        if f"CONFIG_{name}=y" not in settings:
            raise ValueError(f"Missing required CONFIG_{name}=y")
    if "CONFIG_KUNIT=y" in settings:
        raise ValueError("BRD profile must disable KUnit to isolate contract execution")
    return implementation


def first_line(path):
    lines = path.read_text().splitlines()
    return lines[0] if lines else ""


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_hashes(manifest, files):
    """Read sha256sum records without evaluating their paths as shell text."""
    records = {}
    for line in manifest.read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        if not match:
            raise ValueError("Malformed or escaped build.sha256 record")
        path = Path(match[2])
        if not path.is_absolute():
            raise ValueError("Build hash paths must be absolute")
        path = path.resolve()
        if path in records:
            raise ValueError(f"Duplicate build hash record: {path}")
        records[path] = match[1]
    for path in files:
        if records.get(path.resolve()) != digest(path):
            raise ValueError(f"Build evidence does not match: {path}")


def newc(entries):
    """Make an uncompressed deterministic initramfs, including device nodes."""
    result = bytearray()
    for inode, (name, mode, data, major, minor) in enumerate(entries, 1):
        encoded = name.encode() + b"\0"
        fields = (inode, mode, 0, 0, 2 if stat.S_ISDIR(mode) else 1, 0,
                  len(data), 0, 0, major, minor, len(encoded), 0)
        result.extend(b"070701" + b"".join(f"{x:08x}".encode() for x in fields))
        result.extend(encoded)
        result.extend(b"\0" * (-len(result) % 4))
        result.extend(data)
        result.extend(b"\0" * (-len(result) % 4))
    result.extend(b"\0" * (-len(result) % 512))
    return bytes(result)


def make_initramfs(init):
    return newc([
        ("dev", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("proc", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("debug", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("dev/console", stat.S_IFCHR | 0o600, b"", 5, 1),
        ("dev/ram0", stat.S_IFBLK | 0o600, b"", 1, 0),
        ("init", stat.S_IFREG | 0o755, init, 0, 0),
        ("TRAILER!!!", 0, b"", 0, 0),
    ])


def source_state(source):
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(
        ["git", "-C", str(source), "status", "--porcelain"], text=True)
    if dirty:
        raise ValueError("Commit or resolve source changes before recorded verification")
    return revision


def run(args, paths, evidence):
    accel = os.environ.get("RUSIX_QEMU_ACCEL", "tcg")
    if accel not in ("tcg", "kvm"):
        raise ValueError("RUSIX_QEMU_ACCEL must be tcg or kvm")
    revision = source_state(paths.source)
    build = args.build.resolve()
    build_evidence = args.build_evidence.resolve()
    kernel = build / "arch/x86/boot/bzImage"
    config = build / ".config"
    if (build_evidence / "build.exit").read_text().strip() != "0":
        raise ValueError("Build evidence records failure")
    if first_line(build_evidence / "environment.log") != revision:
        raise ValueError("Build source revision differs from the current checkout")
    if (build_evidence / "source-after.commit").read_text().strip() != revision:
        raise ValueError("Source changed during the kernel build")
    if (build_evidence / "source-after.status").read_bytes():
        raise ValueError("Source was dirty after the kernel build")
    profile = (build_evidence / "profile.txt").read_text().strip()
    implementation = validate_selection(
        profile, first_line(build_evidence / "selection.log"), config.read_text())
    check_hashes(build_evidence / "build.sha256", [kernel, config])
    if (build_evidence / "config").read_bytes() != config.read_bytes():
        raise ValueError("Resolved configuration differs from build evidence")

    artifacts = paths.output / "builds" / f"brd-vm-{args.label}"
    artifacts.mkdir(parents=True, exist_ok=False)
    shutil.copytree(build_evidence, evidence / "kernel-build")
    shutil.copy2(config, evidence / "config")
    # Boot an immutable per-attempt copy, never a build image that make may replace.
    image = artifacts / "bzImage"
    shutil.copy2(kernel, image)
    if digest(image) != digest(kernel):
        raise ValueError("Kernel changed while copying it")
    check_hashes(build_evidence / "build.sha256", [kernel, config])
    wrapper = ["bash", str(paths.project / "scripts/with-local-tools.sh")]
    probe = paths.project / "tests/brd-contract/probe.c"
    init = artifacts / "init"
    compile_command = wrapper + ["gcc", "-static", "-pthread", "-O2", "-Wall", "-Wextra",
                                 "-Werror", str(probe), "-o", str(init)]
    (evidence / "compile-command.sh").write_text(shlex.join(compile_command) + "\n")
    with (evidence / "compiler-version.log").open("w") as log:
        subprocess.run(wrapper + ["gcc", "--version"], stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    with (evidence / "compile.log").open("w") as log:
        compiled = subprocess.run(compile_command, stdout=log, stderr=subprocess.STDOUT)
    (evidence / "compile.exit").write_text(f"{compiled.returncode}\n")
    compiled.check_returncode()
    elf = subprocess.check_output(wrapper + ["readelf", "-h", "-l", "-d", str(init)], text=True)
    (evidence / "init-elf.log").write_text(elf)
    if "INTERP" in elf or "(NEEDED)" in elf or "Advanced Micro Devices X86-64" not in elf:
        raise ValueError("Probe must be a static x86_64 ELF without an interpreter")
    initramfs = artifacts / "initramfs.cpio"
    initramfs.write_bytes(make_initramfs(init.read_bytes()))
    source_files = [probe, Path(__file__).resolve(), paths.project / "scripts/rusix_paths.py",
                    paths.project / "scripts/with-local-tools.sh",
                    paths.project / "scripts/repo-paths.sh"]
    metadata = {
        "source_revision": revision, "implementation": implementation,
        "scope": "Six-case userspace block contract",
        "sources": {str(p.relative_to(paths.source)): digest(p) for p in source_files},
        "artifacts": {str(p): digest(p) for p in (image, init, initramfs)},
        "config_sha256": digest(config),
    }
    (evidence / "inputs.json").write_text(json.dumps(metadata, indent=2) + "\n")
    command = wrapper + ["timeout", "--kill-after=5s", "180s", "qemu-system-x86_64",
                         "-machine", "q35", "-accel", accel, "-cpu", "qemu64" if accel == "kvm" else "max",
                         "-m", "512M", "-smp", "2"]
    firmware = paths.tools / "usr/share/qemu"
    if (firmware / "qboot.rom").is_file():
        command += ["-L", str(firmware), "-bios", "qboot.rom"]
    command += ["-display", "none", "-serial", "stdio", "-monitor", "none",
                "-nic", "none", "-no-reboot", "-kernel", str(image),
                "-initrd", str(initramfs), "-append",
                "console=ttyS0 rdinit=/init rusix.brd_contract=1 brd.rd_nr=1 "
                "brd.rd_size=65536 brd.max_part=1 panic=-1 kunit.enable=0"]
    (evidence / "command.sh").write_text(shlex.join(command) + "\n")
    with (evidence / "qemu-version.log").open("w") as log:
        subprocess.run(wrapper + ["qemu-system-x86_64", "--version"],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    with (evidence / "console.log").open("wb") as log:
        guest = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    (evidence / "qemu.exit").write_text(f"{guest.returncode}\n")
    result = accept_console((evidence / "console.log").read_text(errors="replace"),
                            guest.returncode)
    if source_state(paths.source) != revision:
        raise ValueError("Source changed during VM verification")
    for path, expected in metadata["artifacts"].items():
        if digest(Path(path)) != expected:
            raise ValueError(f"Artifact changed during VM verification: {path}")
    (evidence / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"{implementation} contract: {len(CASES)} cases passed; evidence {evidence}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("label")
    parser.add_argument("--build-evidence", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.label):
        parser.error("Evidence label may contain only letters, numbers, underscore and hyphen")
    paths = resolve_paths()
    logs = paths.output / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    evidence = logs / f"{args.label}-brd.run"
    try:
        evidence.mkdir()
    except FileExistsError:
        parser.error("Evidence label already used; choose a new label")
    status = 1
    try:
        run(args, paths, evidence)
        status = 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        (evidence / "error.log").write_text(str(exc) + "\n")
        print(f"BRD verification failed: {exc}; evidence {evidence}", file=sys.stderr)
    finally:
        (evidence / "runner.exit").write_text(f"{status}\n")
    return status


if __name__ == "__main__":
    sys.exit(main())
