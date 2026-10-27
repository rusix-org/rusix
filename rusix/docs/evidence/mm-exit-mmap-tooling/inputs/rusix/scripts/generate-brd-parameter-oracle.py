#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Generate only the approved, hash-pinned BRD C parameter oracle."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

HUNK = re.compile(rb"@@ -(\d+),(\d+) \+(\d+),(\d+) @@[^\n]*\n")
BASELINE = "2926d88bb7fc4608fd942453d929c39e4e5ec006"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_hash(data, expected, name):
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError(f"Invalid {name} SHA256")
    if digest(data) != expected:
        raise ValueError(f"{name} SHA256 mismatch")


def adapt_coordinates(original):
    """The proposal's context starts one line earlier than the pinned release.

    This fixed recorded adaptation changes hunk coordinates only. No runtime
    context search, fuzz, whitespace rewriting or inferred offset is permitted.
    """
    def move(match):
        old, old_count, new, new_count = map(int, match.groups())
        old_header = f"@@ -{old},{old_count} +{new},{new_count} @@".encode()
        new_header = f"@@ -{old + 1},{old_count} +{new + 1},{new_count} @@".encode()
        return match.group().replace(old_header, new_header, 1)
    adapted, count = HUNK.subn(move, original)
    if count != 2:
        raise ValueError("Expected exactly two original proposal hunks")
    return adapted


def apply_exact(source, patch):
    """Strict single-file textual unified diff, with exact positions and bytes."""
    lines = patch.splitlines(keepends=True)
    if len(lines) < 5 or lines[0] != b"diff --git a/drivers/block/brd.c b/drivers/block/brd.c\n":
        raise ValueError("Oracle patch must name only drivers/block/brd.c")
    if not re.fullmatch(rb"index [0-9a-f]+\.\.[0-9a-f]+ 100644\n", lines[1]):
        raise ValueError("Unsupported index/mode header")
    if lines[2:4] != [b"--- a/drivers/block/brd.c\n", b"+++ b/drivers/block/brd.c\n"]:
        raise ValueError("Unexpected file headers, rename or new file")
    if not source.endswith(b"\n") or not patch.endswith(b"\n"):
        raise ValueError("Source and patch require terminal newline")
    old = source.splitlines(keepends=True)
    result = []
    cursor = 0
    position = 4
    hunks = 0
    while position < len(lines):
        header = HUNK.fullmatch(lines[position])
        if header is None:
            raise ValueError("Unexpected hunk header or additional file")
        old_start, old_count, new_start, new_count = map(int, header.groups())
        old_start -= 1
        new_start -= 1
        if old_start < cursor or old_start > len(old):
            raise ValueError("Overlapping or out-of-range hunk")
        result.extend(old[cursor:old_start])
        if len(result) != new_start:
            raise ValueError("New hunk position mismatch")
        cursor = old_start
        consumed = produced = 0
        position += 1
        while position < len(lines) and not lines[position].startswith(b"@@ "):
            line = lines[position]
            kind, content = line[:1], line[1:]
            if kind not in (b" ", b"-", b"+"):
                raise ValueError("Unsupported hunk line, binary patch or extra file")
            if kind in (b" ", b"-"):
                if cursor >= len(old) or old[cursor] != content:
                    raise ValueError("Exact source context mismatch (no fuzz/offset)")
                cursor += 1
                consumed += 1
            if kind in (b" ", b"+"):
                result.append(content)
                produced += 1
            position += 1
        if (consumed, produced) != (old_count, new_count):
            raise ValueError("Hunk line count mismatch")
        hunks += 1
    if hunks != 2:
        raise ValueError("Expected exactly two baseline patch hunks")
    result.extend(old[cursor:])
    return b"".join(result)


def materialize(source_path, manifest_path):
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != 1 or manifest.get("baseline_commit") != BASELINE:
        raise ValueError("Unexpected oracle manifest version or baseline")
    expected = {"contract": "adr-0003", "hunk_line_offset": 1,
                "baseline_path": "drivers/block/brd.c",
                "output_name": "brd_parameter_fixed.c",
                "implementation": "brd-c-parameter-fix"}
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError("Unexpected oracle identity or coordinate adaptation")
    source = source_path.read_bytes()
    original = (manifest_path.parent / "upstream-proposal.patch").read_bytes()
    patch = (manifest_path.parent / "baseline.patch").read_bytes()
    # Verify every input before parsing or applying any patch instructions.
    verify_hash(source, manifest.get("baseline_sha256"), "baseline")
    verify_hash(original, manifest.get("proposal_sha256"), "proposal")
    verify_hash(patch, manifest.get("patch_sha256"), "adapted patch")
    if adapt_coordinates(original) != patch:
        raise ValueError("Adaptation changes more than recorded hunk coordinates")
    output = apply_exact(source, patch)
    verify_hash(output, manifest.get("output_sha256"), "generated source")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--check", action="store_true", help="verify existing output without writing")
    args = parser.parse_args()
    output = args.output
    protected = [args.source, args.manifest, args.manifest.parent / "baseline.patch",
                 args.manifest.parent / "upstream-proposal.patch"]
    if output.name != "brd_parameter_fixed.c" or output.resolve() in [p.resolve() for p in protected]:
        raise ValueError("Output must be a separate brd_parameter_fixed.c")
    data = materialize(args.source, args.manifest)
    if args.check:
        if output.read_bytes() != data:
            raise ValueError("Existing generated source differs from verified oracle")
        return
    # Build directory exists. Write on the same filesystem and replace only
    # after all validation; a failed validation leaves the old output untouched.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=output.name + ".", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit(f"BRD oracle generation failed: {error}")
