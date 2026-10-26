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
    "rusix_completion_swait": (
        "initializer_preserves_caller_class_links_and_irq_state",
        "empty_wake_preserves_initialized_queue",
        "repeated_prepare_keeps_single_enrollment_and_finish_restores_state",
        "queued_wake_removes_fifo_head_before_second_waiter",
        "generic_swait_event_observes_condition_and_unlinks",
        "generic_swait_timeout_unlinks_before_late_wake",
        "pending_prepare_event_unlinks_without_changing_state_or_irqs",
        "generic_signal_error_and_post_prepare_condition_precedence",
        "generic_broadcast_removes_initial_batch_and_leaves_late_waiter",
    ),
    "rusix_completion_signal": (
        "pending_signals_interrupt_timed_waits",
        "enrolled_waits_wake_for_signals",
        "presignaled_token_wins_over_pending_signal",
        "killable_wait_ignores_nonfatal_pending_signal",
    ),
    "rusix_completion_contract": (
        "initial_state_has_no_token",
        "presignals_are_consumed_once_each",
        "broadcast_persists_until_quiescent_reset",
        "zero_timeout_reports_completion_and_consumes_token",
        "signal_saturates_instead_of_wrapping",
    ),
    "rusix_completion_layout": (
        "c_operations_share_pinned_rust_owned_storage",
        "current_cpu_signal_counts_and_saturates",
        "worker_handoff_observes_published_value",
        "current_cpu_signal_wakes_enrolled_worker",
        "two_workers_consume_exactly_two_tokens",
        "competing_try_waiters_consume_one_token",
        "broadcast_serves_two_workers_and_late_waiters",
        "timed_out_worker_unlinks_before_late_signal",
    ),
    "rusix_completion_wait": (
        "all_wait_entries_consume_presignaled_token",
        "all_wait_entries_preserve_broadcast_sentinel",
        "all_timed_entries_distinguish_zero_timeout_states",
        "all_timed_entries_unlink_after_positive_timeout",
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
