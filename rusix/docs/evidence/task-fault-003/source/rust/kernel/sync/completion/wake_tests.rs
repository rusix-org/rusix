// SPDX-License-Identifier: GPL-2.0-only
//! Synchronous synthetic callback traversal, not task wake integration.
use crate::{bindings, prelude::*};

fn observe(scenario: u32, wrapper: u32, disabled: bool) -> Result<[u32; 5]> {
    let mut out = [0u32; 5];
    // SAFETY: Five writable words exclusively borrowed for this synchronous
    // helper. Inputs are private bounded fixture IDs. No pointer escapes: C
    // owns, unlinks and frees all queue entries before returning. Callback keys
    // name real local storage (or NULL); callback never dereferences that key.
    let error = unsafe { bindings::wait_test_run(scenario, wrapper, disabled, out.as_mut_ptr()) };
    if error != 0 {
        return Err(Error::from_errno(error));
    }
    Ok(out)
}

fn enrollment(scenario: u32, disabled: bool) -> Result<[u32; 10]> {
    let mut out = [0u32; 10];
    // SAFETY: Ten exclusive writable words for a synchronous private fixture.
    // C initializes actual pinned stack queue/entries, restores IRQ flags, and
    // removes every surviving link before their storage leaves scope.
    let error = unsafe { bindings::wait_test_enrollment(scenario, disabled, out.as_mut_ptr()) };
    if error != 0 {
        return Err(Error::from_errno(error));
    }
    Ok(out)
}

#[macros::kunit_tests(rusix_completion_wake)]
mod tests {
    use super::*;

    #[test]
    fn exclusive_budget_uses_callback_success_not_return_magnitude() -> Result {
        // Literal independent oracle: order, calls, exclusive successes, live
        // node mask, argument/context errors. Ordinals occupy four bits each.
        for (scenario, expected) in [
            (0, [0, 0, 0, 0, 0]),        // Empty real list sentinel.
            (1, [0x21, 2, 1, 15, 0]),    // Leading nonexclusive consumes no slot.
            (2, [0x4321, 4, 4, 15, 0]),  // Zero budget scans all exclusives.
            (3, [0x4321, 4, 4, 15, 0]),  // Negative budget also scans all.
            (4, [0x21, 2, 2, 15, 0]),    // Return 2 consumes only one slot.
            (5, [0x21, 2, 1, 15, 0]),    // Zero return continues.
            (12, [0x4321, 4, 4, 15, 0]), // INT_MIN decrement wraps without panic.
            (6, [0x21, 2, 0, 15, 0]),    // Negative return stops immediately.
        ] {
            for disabled in [false, true] {
                assert_eq!(observe(scenario, 0, disabled)?, expected);
            }
        }
        Ok(())
    }

    #[test]
    fn exclusive_accounting_uses_flags_from_before_callback() -> Result {
        for disabled in [false, true] {
            // Exclusive -> nonexclusive still consumes the sole slot.
            assert_eq!(observe(7, 0, disabled)?, [1, 1, 1, 15, 0]);
            // Nonexclusive -> exclusive must not count the first callback.
            assert_eq!(observe(8, 0, disabled)?, [0x4321, 4, 3, 15, 0]);
        }
        Ok(())
    }

    #[test]
    fn callbacks_can_retire_current_for_each_return_path() -> Result {
        for disabled in [false, true] {
            // Zero removal continues; negative removal stops before ordinal 3.
            assert_eq!(observe(9, 0, disabled)?, [0x21, 2, 0, 12, 0]);
            // All four retire, including the final node before the sentinel.
            assert_eq!(observe(10, 0, disabled)?, [0x4321, 4, 4, 0, 0]);
            // Successful exclusive retirement stops at the first node.
            assert_eq!(observe(11, 0, disabled)?, [1, 1, 1, 14, 0]);
        }
        Ok(())
    }

    #[test]
    fn all_wrappers_forward_arguments_and_preserve_irq_context() -> Result {
        for disabled in [false, true] {
            for wrapper in 0..7 {
                let expected_count = if wrapper == 0 { 1 } else { u32::MAX };
                // Same mixed FIFO for all seven wrappers. Callback checks exact
                // mode/key plus private scheduler WF constants independently.
                assert_eq!(
                    observe(1, wrapper, disabled)?,
                    [0x21, 2, expected_count, 15, 0]
                );
            }
        }
        Ok(())
    }

    #[test]
    fn null_sync_wrappers_preserve_irq_context() {
        for disabled in [false, true] {
            // SAFETY: Synchronous test helper calls only the two APIs that
            // accept NULL, and always restores current's incoming IRQ flags.
            let errors = unsafe { bindings::wait_test_null_sync(disabled) };
            assert_eq!(errors, 0);
        }
    }

    #[test]
    fn enrollment_preserves_priority_prefix_lifo_and_exclusive_tail() -> Result {
        for disabled in [false, true] {
            // Original C-list observation and actual callbacks both see
            // priorities 1,2, ordinary LIFO 4,3, then exclusive tail 5.
            assert_eq!(
                enrollment(0, disabled)?,
                [0x53421, 0x53421, 0, 0, 0, 0x111, 0x110, 0x100, 0x100, 0x101,]
            );
        }
        Ok(())
    }

    #[test]
    fn priority_exclusive_rejects_only_priority_at_head() -> Result {
        for disabled in [false, true] {
            // EBUSY still sets both bits, while both new entry links stay intact.
            assert_eq!(
                enrollment(1, disabled)?,
                [
                    1,
                    1,
                    (-16i32) as u32,
                    1,
                    0,
                    0x110,
                    0x111,
                    0x100,
                    0x100,
                    0x100,
                ]
            );
            // A priority-marked exclusive tail does not block a new head.
            assert_eq!(
                enrollment(2, disabled)?,
                [0x213, 0x213, 0, 0, 0, 0x100, 0x111, 0x111, 0x100, 0x100,]
            );
        }
        Ok(())
    }

    #[test]
    fn removal_poisons_links_and_allows_readdition() -> Result {
        for disabled in [false, true] {
            // Middle removal/readd produces 2,1,3. Six observed link bits cover
            // poison on middle/head/tail/only/self-linked nodes and empty head.
            assert_eq!(
                enrollment(3, disabled)?,
                [0x312, 0x312, 0, 63, 0, 0x101, 0x100, 0x101, 0x100, 0x100,]
            );
        }
        Ok(())
    }

    #[test]
    fn constructor_preserves_caller_class_links_and_irq_context() {
        for disabled in [false, true] {
            // SAFETY: Synchronous private constructor fixture. Metadata has
            // static storage; three queues remain immovable until all calls
            // finish. Non-lockdep builds deliberately pass unused NULL metadata.
            let observations = unsafe { bindings::wait_test_constructor(disabled) };
            assert_eq!(observations, if cfg!(CONFIG_LOCKDEP) { 0x100 } else { 0 });
        }
    }
}
