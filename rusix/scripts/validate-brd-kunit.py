#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Require the nine Rust BRD ownership/policy KUnit cases from parsed JSON."""
import argparse
from collections import Counter
import json
from pathlib import Path

# Independent inventory: deleting or renaming source tests must not weaken this gate.
SUITES = {
    "rusix_brd_policy": (
        "minor_count_preserves_defined_normalization",
        "invalid_minor_normalization_is_rejected",
        "legacy_size_retains_prefix_and_wrapping_semantics",
    ),
    "rusix_brd_store": (
        "lookup_and_repeated_insert_preserve_page",
        "discard_keeps_inflight_page_alive_and_reinsert_is_independent",
        "discard_excludes_end_and_is_idempotent",
    ),
    "rusix_xarray_insert": (
        "occupied_insert_returns_owner_without_replacing",
        "array_drop_releases_inserted_owner",
    ),
    "rusix_noio_scope": ("nested_scopes_restore_task_policy_on_error",),
}


def groups(group):
    if not isinstance(group, dict):
        raise ValueError("Test group must be an object")
    if not isinstance(group["name"], str):
        raise ValueError("Test group must have a string name")
    for field in ("sub_groups", "test_cases"):
        if not isinstance(group[field], list):
            raise ValueError(f"{field} must be a list")
    yield group
    for child in group["sub_groups"]:
        yield from groups(child)


def validate(result, *, suites=SUITES):
    """Reject missing/duplicate cases, bad totals, and any reported non-pass."""
    inventory = list(groups(result))
    for group in inventory:
        for field in ("tests", "passed", "failed", "crashed", "skipped", "errors"):
            value = group["misc"][field]
            if type(value) is not int or value < 0:
                raise ValueError(f"{group['name']}: invalid {field} count")
            if field not in ("tests", "passed") and value:
                raise ValueError(f"{group['name']}: nonzero {field}")
        names = []
        for case in group["test_cases"]:
            if not isinstance(case["name"], str) or case["status"] != "PASS":
                raise ValueError(f"{group['name']}: invalid or non-passing case")
            names.append(case["name"])
        if len(names) != len(set(names)):
            raise ValueError(f"{group['name']}: duplicate case")
    count = 0
    for name, expected in suites.items():
        matches = [group for group in inventory if group["name"] == name]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one {name} suite, found {len(matches)}")
        suite = matches[0]
        actual = Counter(case["name"] for group in groups(suite)
                         for case in group["test_cases"])
        if actual != Counter(expected):
            raise ValueError(f"{name}: case inventory differs from pinned expectation")
        if any(suite["misc"][field] != len(expected) for field in ("tests", "passed")):
            raise ValueError(f"{name}: inconsistent pass/test totals")
        count += len(expected)
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, help="JSON emitted by upstream kunit.py parse")
    args = parser.parse_args()
    try:
        count = validate(json.loads(args.results.read_text()))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"BRD KUnit acceptance gate failed: {error}\n")
    print(f"BRD KUnit acceptance gate passed: {count} required cases, all PASS")


if __name__ == "__main__":
    main()
