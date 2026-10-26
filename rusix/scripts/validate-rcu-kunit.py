#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Strict isolated or combined RCU list migration acceptance gate."""
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

completion = load("rcu_completion_gate", "validate-completion-kunit.py")
common = completion.common
# Independent literal inventory; source deletions cannot weaken this gate.
SUITES = {"rusix_rcu_list": (
    "simple_fifo_and_both_flush_forms_preserve_tail_identity",
    "init_flags_gp_sentinels_empty_queries_and_count_updates",
    "four_segments_advance_compacts_and_accelerate_merges",
    "done_extraction_partial_reinsertion_keeps_detached_accounting",
    "pending_transfer_retains_source_descriptor_and_separate_count",
    "entrain_empty_head_with_positive_count_joins_done",
    "merge_under_cpu_lock_prepends_done_restarts_pending",
    "modular_gp_equality_wrap_and_half_range_ordering",
    "real_call_rcu_two_cpu_payloads_complete_before_barrier_return",
    "real_srcu_reader_blocks_callback_until_release_and_barrier",
)}

def validate(result, combined=False):
    suites = dict(SUITES)
    if combined:
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
