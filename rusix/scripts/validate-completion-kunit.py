#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Require completion behavior, Rust-owned layout, and bounded worker cases."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    "brd_kunit_common", Path(__file__).with_name("validate-brd-kunit.py"))
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)

# Independent of live Rust source so removing a test does not weaken this gate.
SUITES = {
    "rusix_completion_contract": (
        "initial_state_has_no_token",
        "presignals_are_consumed_once_each",
        "broadcast_persists_until_quiescent_reset",
        "zero_timeout_reports_completion_and_consumes_token",
        "signal_saturates_instead_of_wrapping",
    ),
    "rusix_completion_layout": (
        "c_operations_share_pinned_rust_owned_storage",
        "worker_handoff_observes_published_value",
        "two_workers_consume_exactly_two_tokens",
        "timed_out_worker_unlinks_before_late_signal",
    ),
}


def validate(result):
    return common.validate(result, suites=SUITES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, help="JSON emitted by upstream kunit.py parse")
    args = parser.parse_args()
    try:
        count = validate(json.loads(args.results.read_text()))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Completion KUnit acceptance gate failed: {error}\n")
    print(f"Completion KUnit acceptance gate passed: {count} required cases, all PASS")


if __name__ == "__main__":
    main()
