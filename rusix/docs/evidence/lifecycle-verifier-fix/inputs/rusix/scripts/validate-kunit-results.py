#!/usr/bin/env python3
"""Require the pinned square-root test inventory, not merely a passing run."""
import argparse
from collections import Counter
import json
from pathlib import Path


# Names from upstream 2926d88bb7fc4608fd942453d929c39e4e5ec006. Keep this
# inventory independent of the live C source, so removing a test cannot silently
# weaken both the tests and their acceptance gate in the same build.
UPSTREAM_CASES = (
    "edge case: square root of 0",
    "perfect square: square root of 1",
    "non-perfect square: square root of 2",
    "non-perfect square: square root of 3",
    "perfect square: square root of 4",
    "non-perfect square: square root of 5",
    "non-perfect square: square root of 6",
    "non-perfect square: square root of 7",
    "non-perfect square: square root of 8",
    "perfect square: square root of 9",
    "non-perfect square: square root of 15 (N-1 from 16)",
    "perfect square: square root of 16",
    "non-perfect square: square root of 17 (N+1 from 16)",
    "non-perfect square: square root of 80 (N-1 from 81)",
    "perfect square: square root of 81",
    "non-perfect square: square root of 82 (N+1 from 81)",
    "non-perfect square: square root of 255 (N-1 from 256)",
    "perfect square: square root of 256",
    "non-perfect square: square root of 257 (N+1 from 256)",
    "large input: square root of 2147483648",
    "edge case: ULONG_MAX for 32-bit",
)
COMPATIBILITY_CASES = (
    "int_sqrt_small_domain",
    "int_sqrt_boundaries",
    "int_sqrt_differential",
)


def groups(group):
    yield group
    for child in group["sub_groups"]:
        yield from groups(child)


def validate(result, *, baseline=False):
    """Raise ValueError on omitted, duplicate, skipped, failed or malformed tests."""
    inventory = list(groups(result))
    for group in inventory:
        for field in ("failed", "crashed", "skipped", "errors"):
            if group["misc"][field] != 0:
                raise ValueError(f"{group['name']}: nonzero {field}")
        for case in group["test_cases"]:
            if case["status"] != "PASS":
                raise ValueError(f"{group['name']}/{case['name']}: {case['status']}")

    def require_suite(name, expected, optional=False):
        matches = [group for group in inventory if group["name"] == name]
        if optional and not matches:
            return 0
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one {name} suite, found {len(matches)}")
        suite = matches[0]
        cases = [case for group in groups(suite) for case in group["test_cases"]]
        actual = Counter(case["name"] for case in cases)
        if actual != Counter(expected):
            raise ValueError(f"{name}: case inventory differs from the pinned expectation")
        if suite["misc"]["tests"] != len(expected) or suite["misc"]["passed"] != len(expected):
            raise ValueError(f"{name}: inconsistent pass/test totals")
        return len(cases)

    count = require_suite("math-int_sqrt", UPSTREAM_CASES)
    count += require_suite("rusix-int-sqrt-compatibility", COMPATIBILITY_CASES, optional=baseline)
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, help="JSON emitted by upstream kunit.py parse")
    parser.add_argument("--baseline", action="store_true",
                        help="allow the original baseline without the added compatibility suite")
    args = parser.parse_args()
    try:
        result = json.loads(args.results.read_text())
        count = validate(result, baseline=args.baseline)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"KUnit acceptance gate failed: {error}\n")
    print(f"KUnit acceptance gate passed: {count} required square-root cases, all PASS")


if __name__ == "__main__":
    main()
