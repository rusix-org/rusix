#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Run a static BRD partition fixture in one fresh, bounded VM boot."""
import argparse
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

spec = importlib.util.spec_from_file_location("brd_common", Path(__file__).with_name("test-brd-vm.py"))
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
digest = common.digest
check_hashes = common.check_hashes
source_state = common.source_state
first_line = common.first_line
CASES = ("discovery", "geometry", "translation", "boundaries", "independent_disk")


def validate_selection(profile, selection, config, core_selection=None):
    mapped = {"brd": "brd", "brd-rust": "brd-rust",
              "brd-ext4-c": "brd", "brd-ext4-rust": "brd-rust",
              "core-ext4-c": "core-ext4-c", "core-ext4-rust": "core-ext4-rust"}.get(profile)
    if mapped is None:
        raise ValueError("A C or Rust BRD contract/ext4 profile is required")
    implementation = common.validate_selection(mapped, selection, config, core_selection)
    for name in ("SYSFS", "MSDOS_PARTITION"):
        if f"CONFIG_{name}=y" not in config.splitlines():
            raise ValueError(f"Partition contract requires CONFIG_{name}=y")
    return implementation


def accept_console(console, qemu_exit):
    if qemu_exit != 0:
        raise ValueError(f"QEMU failed or timed out: exit {qemu_exit}")
    if re.search(r"(?i:\bwarning\b)|\bBUG\b|Oops:|Kernel panic|CPU feature dependency check failure|ACPI (?:BIOS )?(?:Error|Exception|Warning)|ACPI: Unable to load|Buffer I/O error|I/O error, dev", console):
        raise ValueError("Kernel diagnostic in partition guest")
    expected = ["RUSIX_BRD_PARTITIONS_START"]
    expected += [f"RUSIX_BRD_PARTITIONS_PASS {case}" for case in CASES]
    expected += ["RUSIX_BRD_PARTITIONS_SUCCESS cases=5"]
    markers = [line for line in console.splitlines() if "RUSIX_BRD_PARTITIONS_" in line]
    if markers != expected:
        raise ValueError(f"Partition inventory/order mismatch: {markers!r}")
    return {"status": "PASS", "cases": list(CASES), "qemu_exit": qemu_exit}


def variants(config):
    return [{"name": "primary_partition", "rd_nr": 2, "rd_size": 4096, "max_part": 4}]


def command_line(variant):
    return ("console=ttyS0 rdinit=/init rusix.brd_partitions=1 panic=-1 kunit.enable=0 printk.devkmsg=on printk.time=0 loglevel=7 "
            "brd.rd_nr=2 brd.rd_size=4096 brd.max_part=4")


def make_initramfs(init):
    return common.newc([
        ("dev", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("proc", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("sys", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("dev/console", stat.S_IFCHR | 0o600, b"", 5, 1),
        ("dev/kmsg", stat.S_IFCHR | 0o600, b"", 1, 11),
        ("init", stat.S_IFREG | 0o755, init, 0, 0),
        ("TRAILER!!!", 0, b"", 0, 0),
    ])


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
        profile, first_line(build_evidence / "selection.log"), config.read_text(),
        first_line(build_evidence / "completion-selection.log")
        if profile.startswith("core-ext4-") else None)
    check_hashes(build_evidence / "build.sha256", [kernel, config])
    if (build_evidence / "config").read_bytes() != config.read_bytes():
        raise ValueError("Resolved configuration differs from build evidence")

    artifacts = paths.output / "builds" / f"brd-partitions-vm-{args.label}"
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
    probe = paths.project / "tests/brd-partitions/init.rs"
    init = artifacts / "init"
    compile_command = wrapper + ["rustc", "--edition=2021", "--target", "x86_64-unknown-linux-gnu",
                                 "-C", "target-feature=+crt-static", "-C", "panic=abort",
                                 "-C", "opt-level=2", "-D", "warnings", str(probe), "-o", str(init)]
    (evidence / "compile-command.sh").write_text(shlex.join(compile_command) + "\n")
    with (evidence / "compiler-version.log").open("w") as log:
        subprocess.run(wrapper + ["rustc", "--version", "--verbose"], stdout=log,
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
                    paths.project / "scripts/test-brd-vm.py",
                    paths.project / "scripts/with-local-tools.sh",
                    paths.project / "scripts/repo-paths.sh"]
    metadata = {
        "source_revision": revision, "implementation": implementation, "profile": profile,
        "scope": "One primary DOS partition geometry/translation/boundary contract",
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
                "-initrd", str(initramfs)]
    with (evidence / "qemu-version.log").open("w") as log:
        subprocess.run(wrapper + ["qemu-system-x86_64", "--version"],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    results = []
    for variant in variants((evidence / "config").read_text()):
        attempt = evidence / variant["name"]
        attempt.mkdir()
        cmdline = command_line(variant)
        invocation = command + ["-append", cmdline]
        (attempt / "command.sh").write_text(shlex.join(invocation) + "\n")
        (attempt / "expectations.json").write_text(json.dumps(variant, indent=2) + "\n")
        with (attempt / "console.log").open("wb") as log:
            guest = subprocess.run(invocation, stdout=log, stderr=subprocess.STDOUT)
        (attempt / "qemu.exit").write_text(f"{guest.returncode}\n")
        try:
            result = accept_console((attempt / "console.log").read_text(errors="replace"),
                                    guest.returncode)
        except ValueError as error:
            (attempt / "result.json").write_text(json.dumps({
                "status": "FAIL", "variant": variant["name"],
                "qemu_exit": guest.returncode, "error": str(error)}, indent=2) + "\n")
            raise
        result["variant"] = variant["name"]
        (attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        results.append(result)
    check_hashes(build_evidence / "build.sha256", [kernel, config])
    if digest(evidence / "config") != metadata["config_sha256"]:
        raise ValueError("Configuration snapshot changed during verification")
    if source_state(paths.source) != revision:
        raise ValueError("Source changed during VM verification")
    for path, expected in metadata["artifacts"].items():
        if digest(Path(path)) != expected:
            raise ValueError(f"Artifact changed during VM verification: {path}")
    (evidence / "result.json").write_text(json.dumps({"status": "PASS", "variants": results}, indent=2) + "\n")
    print(f"{implementation} partitions: {len(results)} variants passed; evidence {evidence}")


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
    evidence = logs / f"{args.label}-brd-partitions.run"
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
