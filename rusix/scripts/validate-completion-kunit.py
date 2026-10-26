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
    "rusix_completion_wait_owner": (
        "original_hash_oracle_covers_all_heads_and_shared_class",
        "variable_constructor_and_callback_preserve_identity_and_flags",
        "normal_collision_preserves_distinct_predicates",
        "exclusive_collision_preserves_unmatched_waiter",
        "mixed_collision_orders_preserve_key_filtering",
        "blocked_collision_abort_detaches_both_owned_entries",
    ),
    "rusix_completion_wait_locked": (
        "pending_iteration_preserves_lock_state_irq_and_enrollment",
        "original_macro_distinguishes_initial_condition_from_pending_error",
        "blocked_spurious_wake_rechecks_before_locked_publication",
        "blocked_signal_returns_error_with_caller_cleanup",
    ),
    "rusix_completion_wait_bit": (
        "ordinary_loop_preserves_action_errors_even_when_bit_clears",
        "lock_loop_acquisition_overrides_action_error",
        "key_match_and_clear_bit_gate_autoremove",
        "already_expired_action_returns_without_scheduling",
        "production_deadline_arithmetic_matches_c_across_wrap",
        "blocked_bit_clear_publishes_payload",
        "blocked_bit_lock_serializes_two_owners",
        "blocked_bit_signal_and_expiry_unlink",
        "stack_timeout_wrapper_blocks_and_cleans",
    ),
    "rusix_completion_wait_woken": (
        "prelatched_running_callback_skips_schedule_and_preserves_membership",
        "zero_and_positive_timeout_restore_state_without_autoremove",
        "blocked_woken_consumer_observes_published_condition",
        "bit_keys_filter_address_and_bit_but_not_timeout",
    ),
    "rusix_completion_wait_lifecycle": (
        "blocked_priority_exclusive_handoff_consumes_one_token",
        "blocked_signal_and_nonmatching_wake_preserve_lifecycle",
        "pending_condition_wins_after_prepare_signal_error",
        "timeout_finishes_before_late_wake",
        "repeated_prepare_preserves_membership_state_and_empty_return",
    ),
    "rusix_completion_wake": (
        "enrollment_preserves_priority_prefix_lifo_and_exclusive_tail",
        "priority_exclusive_rejects_only_priority_at_head",
        "removal_poisons_links_and_allows_readdition",
        "constructor_preserves_caller_class_links_and_irq_context",
        "exclusive_budget_uses_callback_success_not_return_magnitude",
        "exclusive_accounting_uses_flags_from_before_callback",
        "callbacks_can_retire_current_for_each_return_path",
        "all_wrappers_forward_arguments_and_preserve_irq_context",
        "null_sync_wrappers_preserve_irq_context",
    ),
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
