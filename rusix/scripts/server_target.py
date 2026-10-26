#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Derive the C-core comparison from the declared server target and bind inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import re

CORE = "CONFIG_RUSIX_COMPLETION_RUST"
RCU = "CONFIG_RUSIX_RCU_LIST_RUST"
PROFILES = {"server": "y", "server-c": "n",
            "rcu-list-server-c": "y", "rcu-list-server-rust": "y"}
RCU_PROFILES = {"rcu-list-server-c": "n", "rcu-list-server-rust": "y"}


def settings(text):
    result = {}
    for line in text.splitlines():
        enabled = re.fullmatch(r"(CONFIG_[A-Z0-9_]+)=(.+)", line)
        disabled = re.fullmatch(r"# (CONFIG_[A-Z0-9_]+) is not set", line)
        if not enabled and not disabled:
            continue
        name, value = enabled.groups() if enabled else (disabled[1], "n")
        if name in result:
            raise ValueError(f"Duplicate configuration setting: {name}")
        result[name] = value
    return result


def derive(source, profile):
    if profile not in PROFILES:
        raise ValueError("Expected server or server-c profile")
    values = settings(source)
    required = {CORE: "y", "CONFIG_RUST": "y", "CONFIG_RUSIX_BRD_RUST": "y",
                "CONFIG_KUNIT": "n", "CONFIG_MODULES": "n", "CONFIG_DEBUG_FS": "n"}
    for name, value in required.items():
        if values.get(name) != value:
            raise ValueError(f"Declared server must explicitly request {name}={value}")
    if profile in RCU_PROFILES:
        # An explicit experimental derivation; leave the declared source intact.
        if values.get(RCU, 'n') != 'n' or values.get('CONFIG_RUSIX_RCU_LIST_TEST', 'n') != 'n':
            raise ValueError('Declared server already changes the experimental RCU axis')
        lines = [line for line in source.splitlines() if not re.match(
            r'^(?:# )?CONFIG_RUSIX_RCU_LIST_(?:RUST|TEST)(?:=| is not set)', line)]
        lines += [f'{RCU}=y' if RCU_PROFILES[profile] == 'y' else f'# {RCU} is not set',
                  '# CONFIG_RUSIX_RCU_LIST_TEST is not set']
        return '\n'.join(lines) + '\n'
    if profile == "server":
        return source
    return re.sub(rf"^{CORE}=y$", f"# {CORE} is not set", source, count=1, flags=re.MULTILINE)


def validate_resolved(source, profile, config):
    requested = settings(derive(source, profile))
    resolved = settings(config)
    if resolved.get(CORE) != PROFILES[profile]:
        raise ValueError("Resolved server must explicitly identify its core selection")
    for name, value in requested.items():
        if resolved.get(name, "n") != value:
            raise ValueError(f"Resolved server changed requested {name}={value}")
    # These exclusion guards also matter for the C comparison: keep both targets
    # within the Rust core's supported caller configuration.
    for name in ("MTD_ONENAND", "MT7601U", "SCSI_IPR", "SGI_GRU"):
        if resolved.get(f"CONFIG_{name}", "n") != "n":
            raise ValueError(f"Unsupported plain completion counter caller: {name}")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(source_path, source, profile, generated):
    return {"schema": 1, "profile": profile,
            "source_fragment": str(source_path.resolve()),
            "source_fragment_sha256": sha(source.encode()),
            "config_input_sha256": sha(generated.encode()),
            "derivation_script_sha256": sha(Path(__file__).read_bytes()),
            "override": ({RCU: RCU_PROFILES[profile]} if profile in RCU_PROFILES else
                         {} if profile == "server" else {CORE: "n"})}


def materialize(source_path, profile, evidence):
    source = source_path.read_text()
    generated = derive(source, profile)
    for name in ("config-template", "config-input", "config-input.json"):
        if (evidence / name).exists():
            raise ValueError(f"Refusing to overwrite input evidence: {name}")
    (evidence / "config-template").write_text(source)
    (evidence / "config-input").write_text(generated)
    (evidence / "config-input.json").write_text(
        json.dumps(identity(source_path, source, profile, generated), indent=2, sort_keys=True) + "\n")


def verify(source_path, profile, evidence, resolved):
    source = source_path.read_text()
    generated = derive(source, profile)
    if (evidence / "config-template").read_text() != source:
        raise ValueError("Build input template differs from declared server source")
    if (evidence / "config-input").read_text() != generated:
        raise ValueError("Build input differs from exact declared server derivation")
    if json.loads((evidence / "config-input.json").read_text()) != identity(source_path, source, profile, generated):
        raise ValueError("Server configuration input provenance mismatch")
    validate_resolved(source, profile, resolved.read_text())


def compare(source, rust, c, axis="core"):
    if axis not in ("core", "rcu-list"):
        raise ValueError("Unknown comparison axis")
    validate_resolved(source, "server" if axis == "core" else "rcu-list-server-rust", rust)
    validate_resolved(source, "server-c" if axis == "core" else "rcu-list-server-c", c)
    left, right = settings(rust), settings(c)
    changes = {name: [left.get(name, "n"), right.get(name, "n")]
               for name in left.keys() | right.keys()
               if left.get(name, "n") != right.get(name, "n")}
    if changes != {CORE if axis == "core" else RCU: ["y", "n"]}:
        raise ValueError(f"Server pair differs beyond core selection: {changes}")
    return {"status": "PASS", "resolved_config_differences": changes,
            "rust_config_sha256": sha(rust.encode()), "c_config_sha256": sha(c.encode())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("materialize", "verify"):
        cmd = sub.add_parser(command)
        cmd.add_argument("--source", type=Path, required=True)
        cmd.add_argument("--profile", choices=PROFILES, required=True)
        cmd.add_argument("--evidence", type=Path, required=True)
        if command == "verify":
            cmd.add_argument("--resolved", type=Path, required=True)
    cmd = sub.add_parser("compare")
    cmd.add_argument("--source", type=Path, required=True)
    cmd.add_argument("--rust", type=Path, required=True)
    cmd.add_argument("--c", type=Path, required=True)
    cmd.add_argument("--axis", choices=("core", "rcu-list"), default="core")
    args = parser.parse_args()
    if args.command == "materialize":
        materialize(args.source, args.profile, args.evidence)
    elif args.command == "verify":
        verify(args.source, args.profile, args.evidence, args.resolved)
    else:
        print(json.dumps(compare(args.source.read_text(), args.rust.read_text(), args.c.read_text(), args.axis), indent=2))


if __name__ == "__main__":
    main()
