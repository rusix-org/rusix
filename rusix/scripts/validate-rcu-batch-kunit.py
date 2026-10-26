#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Strict isolated or combined Tree RCU batch migration acceptance gate."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

lists = load("rcu_batch_lists_gate", "validate-rcu-kunit.py")
completion = lists.completion
common = lists.common
SUITES = {"rusix_rcu_batch": (
    "private_empty_and_fifo_accounting",
    "private_time_check_boundaries",
    "held_reader_payload_before_barrier",
    "self_free_callback_final_access",
    "self_requeue_once_before_second_barrier",
    "flood_exact_once_before_barrier",
    "softirq_count_budget_reinserts_done_before_pending",
)}

def validate(result, combined=False):
    suites = dict(SUITES)
    if combined:
        suites.update(lists.SUITES)
        suites.update(completion.SUITES)
        suites.update(common.SUITES)
    # The shared gate permits extra suites for other profiles. Here the complete
    # declared suite set is required, and no undeclared test suite is accepted.
    inventory = list(common.groups(result))
    if any(g["name"].startswith("rusix_") and g["name"] not in suites for g in inventory):
        raise ValueError("Unexpected RCU gate suite")
    present = [g["name"] for g in inventory if g["test_cases"]]
    if set(present) != set(suites) or len(present) != len(suites):
        raise ValueError("Missing, duplicate or unexpected RCU gate suite")
    return common.validate(result, suites=suites)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined", action="store_true")
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    try:
        count = validate(json.loads(args.results.read_text()), args.combined)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"RCU KUnit acceptance failed: {error}\n")
    print(f"RCU KUnit acceptance passed: {count} required cases, all PASS")

if __name__ == "__main__":
    main()
