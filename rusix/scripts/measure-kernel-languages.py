#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Measure retained linked kernel bytes by compilation-unit language.

Requires an LLD linker map for the measured ELF, original Kbuild .cmd files,
and successful build evidence. Currently accepts the x86_64 bzImage build layout. This does not count source files/lines or unlinked object sizes.
"""
import argparse
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shlex
import struct
import subprocess
import sys

from rusix_paths import resolve_paths

CATEGORIES = ("c", "rust", "assembly", "generated", "unknown",
              "padding_or_linker_script")


@dataclass(frozen=True)
class Section:
    name: str
    address: int
    size: int
    flags: int
    kind: int
    content_sha256: str | None


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def elf_sections(path):
    """Read section identities directly, without depending on readelf formatting."""
    data = path.read_bytes()
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01":
        raise ValueError("Only ELF64 little-endian kernels are currently supported")
    header = struct.unpack_from("<16sHHIQQQIHHHHHH", data)
    if header[2] != 62:
        raise ValueError("Only x86_64 kernel measurement is currently supported")
    offset, entry_size, count, strings_index = header[6], header[11], header[12], header[13]
    if entry_size != 64 or not count or not 0 < strings_index < count:
        raise ValueError("Unsupported ELF section table (including extended numbering)")
    if offset + entry_size * count > len(data):
        raise ValueError("Truncated ELF section table")
    headers = [struct.unpack_from("<IIQQQQIIQQ", data, offset + 64 * i)
               for i in range(count)]
    strings_header = headers[strings_index]
    strings = data[strings_header[4]:strings_header[4] + strings_header[5]]
    sections = {}
    for name_index, kind, flags, address, file_offset, size, *_ in headers[1:]:
        if name_index >= len(strings) or b"\0" not in strings[name_index:]:
            raise ValueError("Invalid ELF section name")
        name = strings[name_index:strings.index(b"\0", name_index)].decode()
        if name in sections:
            raise ValueError(f"Duplicate ELF section name: {name}")
        content_hash = None
        if kind != 8:  # SHT_NOBITS consumes memory, but has no file payload.
            if file_offset + size > len(data):
                raise ValueError(f"Truncated section: {name}")
            content_hash = hashlib.sha256(data[file_offset:file_offset + size]).hexdigest()
        sections[name] = Section(name, address, size, flags, kind, content_hash)
    return sections


def parse_map(text, sections):
    """Return allocated input intervals; validate map/ELF section layout exactly."""
    if not re.search(r"VMA\s+LMA\s+Size\s+Align\s+Out\s+In\s+Symbol", text):
        raise ValueError("Expected an LLD linker map with VMA/LMA/Size/Align columns")
    row = re.compile(r"^\s*([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+"
                     r"([0-9a-fA-F]+)\s+(\d+)([ \t]+)(.*)$")
    input_row = re.compile(r"(.+):\(([^)]*)\)$")
    current = None
    seen = set()
    intervals = defaultdict(list)
    for line in text.splitlines():
        match = row.match(line)
        if not match:
            continue
        address, _, size = (int(match[i], 16) for i in (1, 2, 3))
        body = match[6].strip()
        # LLD puts output sections at Out, inputs one indentation level later.
        # Some output sections (e.g. .modinfo) may be stripped after the link.
        if len(match[5]) == 1 and body not in sections:
            current = None
            continue
        if len(match[5]) == 1 and body in sections:
            current = sections[body]
            if body in seen:
                raise ValueError(f"Duplicate map output section: {body}")
            seen.add(body)
            if current.flags & 2 and (address, size) != (current.address, current.size):
                raise ValueError(f"Map/ELF layout mismatch for {body}")
            continue
        contribution = input_row.fullmatch(body)
        if not contribution or not current or not current.flags & 2 or not size:
            continue
        if address < current.address or address + size > current.address + current.size:
            raise ValueError(f"Input contribution outside {current.name}: {body}")
        intervals[current.name].append((address, address + size,
                                        contribution[1], contribution[2]))
    missing = [s.name for s in sections.values() if s.flags & 2 and s.size and s.name not in seen]
    if missing:
        raise ValueError(f"Allocated ELF sections absent from map: {missing}")
    if not intervals:
        raise ValueError("Map contains no allocated input-section contributions")
    for name, entries in intervals.items():
        end = sections[name].address
        for start, stop, *_ in sorted(entries):
            if start < end:
                raise ValueError(f"Overlapping input contributions in {name}")
            end = stop
    return intervals


def object_path(label, build):
    if label == "<internal>":
        return None
    archive = re.fullmatch(r".+\((.+)\)", label)
    member = archive[1] if archive else label
    path = Path(member)
    return path.resolve() if path.is_absolute() else (build / path).resolve()


def classify(label, build, source, visited=frozenset()):
    """Classify provenance from Kbuild records; never execute .cmd contents."""
    obj = object_path(label, build)
    if obj is None:
        return "generated", {"reason": "linker internal contribution"}
    try:
        relative = obj.relative_to(build)
    except ValueError:
        return "unknown", {"reason": "object outside supplied build directory", "object": str(obj)}
    if obj in visited:
        return "unknown", {"reason": "cyclic object provenance", "object": str(relative)}
    if not obj.is_file():
        return "unknown", {"reason": "missing linked object", "object": str(relative)}
    visited = visited | {obj}
    cmd = obj.parent / f".{obj.name}.cmd"
    if not cmd.is_file():
        if obj.name == ".vmlinux.export.o" or re.fullmatch(r"\.tmp_vmlinux\d+\.kallsyms.o", obj.name):
            return "generated", {"reason": "Kbuild generated export/kallsyms object", "object": str(relative), "object_sha256": sha256(obj)}
        return "unknown", {"reason": "missing Kbuild command record", "object": str(relative)}
    text = cmd.read_text()
    record = re.search(r"^source_" + re.escape(str(relative)) + r"\s*:=\s*(.+)$", text, re.M)
    command = re.search(r"^savedcmd_" + re.escape(str(relative)) + r"\s*:=\s*(.+)$", text, re.M)
    detail = {"object": str(relative), "command_file": str(cmd.relative_to(build)),
              "command_sha256": sha256(cmd), "object_sha256": sha256(obj)}
    if not record and command:
        # x86 PI copies retain compiled code while prefixing its symbols. Trace
        # only this narrow, auditable transform; never infer arbitrary ld output.
        tokens = shlex.split(command[1])
        if (len(tokens) == 4 and Path(tokens[0]).name in ("llvm-objcopy", "objcopy")
                and tokens[1].startswith("--prefix-symbols=")
                and (build / tokens[3]).resolve() == obj):
            language, original = classify(tokens[2], build, source, visited)
            return language, dict(detail, reason="symbol-prefix-only object copy",
                                  original=original)
    if not record or not command:
        return "unknown", dict(detail, reason="missing source or compile command")
    source_path = Path(record[1].strip())
    if not source_path.is_absolute():
        source_path = build / source_path
    source_path = source_path.resolve()
    detail["source"] = str(source_path)
    if source_path.is_relative_to(build):
        return "generated", dict(detail, reason="build-generated source")
    detail["source_origin"] = "repository" if source_path.is_relative_to(source) else "external"
    suffix = source_path.suffix
    compiler = command[1].split(";", 1)[0]
    if suffix == ".rs" and re.search(r"(?:^|\s)(?:[^\s;]*/)?rustc(?:\s|$)", compiler):
        return "rust", detail
    if suffix in (".c", ".S", ".s") and re.search(
            r"(?:^|\s)(?:[^\s;]*/)?(?:[\w-]*gcc|clang|as)(?:-\d+)?(?:\s|$)", compiler):
        return "c" if suffix == ".c" else "assembly", detail
    return "unknown", dict(detail, reason="unrecognized compile language")


def measure(sections, intervals, build, source):
    totals = {metric: dict.fromkeys(CATEGORIES, 0) for metric in
              ("executable", "file_backed_allocated", "zero_fill", "allocated_memory")}
    objects = {}
    per_section = []
    for section in sections.values():
        if not section.flags & 2 or not section.size:
            continue
        counts = dict.fromkeys(CATEGORIES, 0)
        for start, end, label, input_section in intervals.get(section.name, []):
            if label not in objects:
                language, detail = classify(label, build, source)
                objects[label] = dict(detail, language=language, retained_bytes=0,
                                      executable_bytes=0)
            entry = objects[label]
            size = end - start
            entry["retained_bytes"] += size
            if section.flags & 4:
                entry["executable_bytes"] += size
            counts[entry["language"]] += size
        counts["padding_or_linker_script"] = section.size - sum(counts.values())
        metrics = ["allocated_memory", "zero_fill" if section.kind == 8 else "file_backed_allocated"]
        if section.flags & 4:
            metrics.append("executable")
        for metric in metrics:
            for language, size in counts.items():
                totals[metric][language] += size
        per_section.append({"name": section.name, "address": hex(section.address),
                            "size": section.size, "bytes": counts,
                            "content_sha256": section.content_sha256})
    distributions = {}
    for metric, counts in totals.items():
        total = sum(counts.values())
        distributions[metric] = {"total_bytes": total, "bytes": counts,
                                 "percent": {k: round(v * 100 / total, 6) if total else 0
                                             for k, v in counts.items()}}
    return distributions, per_section, objects



def build_identity(build, evidence, measured_elf, measured_map):
    """Bind the measurement to a completed recorded build and its current image."""
    if (evidence / "build.exit").read_text().strip() != "0":
        raise ValueError("Build evidence does not record a successful build")
    environment = (evidence / "environment.log").read_text().splitlines()
    revision = environment[0] if environment else ""
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid build source revision")
    if (evidence / "source-after.commit").read_text().strip() != revision:
        raise ValueError("Build source revision changed")
    if (evidence / "source-after.status").read_bytes():
        raise ValueError("Build source was dirty")
    records = {}
    for line in (evidence / "build.sha256").read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        if not match or not Path(match[2]).is_absolute():
            raise ValueError("Unsupported build hash record")
        path = Path(match[2]).resolve()
        if path in records:
            raise ValueError("Duplicate build hash record")
        records[path] = match[1]
    for path in (build / ".config", build / "arch/x86/boot/bzImage",
                 build / "vmlinux", build / "vmlinux.map"):
        if records.get(path.resolve()) != sha256(path):
            raise ValueError(f"Build evidence mismatch: {path}")
    if (evidence / "config").read_bytes() != (build / ".config").read_bytes():
        raise ValueError("Build configuration snapshot differs")
    if sha256(measured_elf) != sha256(build / "vmlinux"):
        raise ValueError("Measured ELF differs from the build's final vmlinux")
    if sha256(measured_map) != sha256(build / "vmlinux.map"):
        raise ValueError("Measured map differs from the build's recorded vmlinux.map")
    return {"source_revision": revision, "evidence": str(evidence.resolve()),
            "bzImage_sha256": sha256(build / "arch/x86/boot/bzImage"),
            "vmlinux_sha256": sha256(measured_elf),
            "map_sha256": sha256(measured_map),
            "config_sha256": sha256(build / ".config")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("--build-evidence", type=Path, required=True)
    parser.add_argument("--map", type=Path, required=True, dest="link_map")
    parser.add_argument("--vmlinux", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-unknown", action="store_true",
                        help="Write an explicitly incomplete report instead of rejecting unknown object provenance")
    args = parser.parse_args()
    paths = resolve_paths()
    build = args.build.resolve()
    config = build / ".config"
    identity = build_identity(build, args.build_evidence.resolve(), args.vmlinux, args.link_map)
    sections = elf_sections(args.vmlinux)
    intervals = parse_map(args.link_map.read_text(), sections)
    distributions, per_section, objects = measure(sections, intervals, build, paths.source)
    unknown = distributions["allocated_memory"]["bytes"]["unknown"]
    if unknown and not args.allow_unknown:
        missing = [name for name, detail in objects.items() if detail["language"] == "unknown"]
        raise ValueError(f"Unresolved compilation provenance ({unknown} bytes): {missing}")
    source_revision = subprocess.check_output(
        ["git", "-C", str(paths.source), "rev-parse", "HEAD"], text=True).strip()
    report = {
        "schema": 1,
        "measurement_script_sha256": sha256(Path(__file__)),
        "scope": "Retained allocated ELF input sections, attributed by Kbuild compilation unit",
        "build": identity,
        "source_checkout_revision": source_revision,
        "source_checkout_dirty": bool(subprocess.check_output(
            ["git", "-C", str(paths.source), "status", "--porcelain"], text=True)),
        "identities": {"vmlinux_sha256": sha256(args.vmlinux),
                       "config_sha256": sha256(config), "map_sha256": sha256(args.link_map)},
        "paths": {"build": str(build), "vmlinux": str(args.vmlinux.resolve()),
                  "map": str(args.link_map.resolve())},
        "provenance_complete": not unknown,
        "distributions": distributions,
        "sections": per_section,
        "objects": objects,
        "limitations": [
            "The map layout is checked against the final build ELF, and recorded build evidence binds source revision/config/bzImage/vmlinux/map. These records are provenance, not cryptographic third-party attestation.",
            "Unit attribution includes inline assembly, macros, and compiler/objtool metadata emitted for that unit; it is not a per-instruction source-language census.",
            "padding_or_linker_script includes unassigned section bytes, alignment and linker-script emissions; it is never credited to C or Rust.",
            "Generated units and linker-internal merged data are reported separately. A merged contribution cannot be apportioned among its original languages.",
            "Debug/nonallocated sections, ELF headers, file gaps, bzImage decompressor/compression, loadable modules and unbuilt configurations are excluded.",
            "Zero-fill/BSS bytes consume runtime memory but no ELF payload; executable bytes and file-backed allocated bytes are separate metrics.",
            "Linked size is not feature coverage, test coverage, performance, Rust safety, or percentage completion of the rewrite.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(distributions["executable"], indent=2))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        sys.exit(f"Measurement failed: {exc}")
