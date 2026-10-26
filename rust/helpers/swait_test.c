// SPDX-License-Identifier: GPL-2.0
/* KUnit-only observation and original generic swait consumer. */
#include <linux/sched.h>
#include <linux/swait.h>

void rust_helper_swait_test_init(struct swait_queue_head *queue)
{
	init_swait_queue_head(queue);
}

unsigned long rust_helper_swait_test_lock(struct swait_queue_head *queue)
{
	unsigned long flags;

	raw_spin_lock_irqsave(&queue->lock, flags);
	return flags;
}

void rust_helper_swait_test_unlock(struct swait_queue_head *queue,
				  unsigned long flags)
{
	raw_spin_unlock_irqrestore(&queue->lock, flags);
}

int rust_helper_swait_test_irqs_disabled(void)
{
	return irqs_disabled();
}

unsigned int rust_helper_swait_test_current_state(void)
{
	return READ_ONCE(current->__state);
}

/* Caller holds queue.lock. a/b are NULL or separately retained pinned nodes.
 * Low bits: count capped at three; higher bits describe pointer identity only.
 * This observes links; it never changes enrollment or reimplements wake policy.
 */
unsigned int rust_helper_swait_test_snapshot_locked(struct swait_queue_head *queue,
						   struct swait_queue *a,
						   struct swait_queue *b)
{
	struct list_head *head = &queue->task_list;
	struct list_head *entry;
	unsigned int result = 0;

	list_for_each(entry, head) {
		if (++result == 3)
			break;
	}
	if (head->next == head && head->prev == head)
		result |= 1U << 11;
	if (a) {
		if (head->next == &a->task_list)
			result |= 1U << 4;
		if (READ_ONCE(a->task_list.next) == &a->task_list &&
		    READ_ONCE(a->task_list.prev) == &a->task_list)
			result |= 1U << 8;
		if (a->task == current)
			result |= 1U << 10;
	}
	if (b) {
		if (head->next == &b->task_list)
			result |= 1U << 5;
		if (!list_empty(head) && head->next->next == &b->task_list)
			result |= 1U << 6;
		if (head->prev == &b->task_list)
			result |= 1U << 7;
		if (READ_ONCE(b->task_list.next) == &b->task_list &&
		    READ_ONCE(b->task_list.prev) == &b->task_list)
			result |= 1U << 9;
	}
	return result;
}

long rust_helper_swait_test_event_timeout(struct swait_queue_head *queue,
					 u32 *condition, long timeout)
{
	return swait_event_timeout_exclusive(*queue, READ_ONCE(*condition), timeout);
}

unsigned long rust_helper_swait_test_irq_save(void)
{
	unsigned long flags;

	local_irq_save(flags);
	return flags;
}

void rust_helper_swait_test_irq_restore(unsigned long flags)
{
	local_irq_restore(flags);
}

long rust_helper_swait_test_interruptible_timeout(struct swait_queue_head *queue,
						 u32 *condition, long timeout)
{
	return swait_event_interruptible_timeout_exclusive(*queue,
						   READ_ONCE(*condition), timeout);
}

/* Deterministic consumer precedence: outer condition is false, then true after
 * prepare_to_swait_event reports the pending signal. No scheduler race required.
 */
long rust_helper_swait_test_condition_after_prepare(struct swait_queue_head *queue,
						   unsigned int *evaluations,
						   long timeout)
{
	*evaluations = 0;
	return swait_event_interruptible_timeout_exclusive(*queue,
						   ++*evaluations > 1, timeout);
}

/* Static caller metadata outlives lockdep classes, including freed fixtures. */
#ifdef CONFIG_LOCKDEP
static struct lock_class_key swait_test_keys[2];
static const char swait_test_names[2][24] = { "swait-test-first", "swait-test-second" };
#endif

/* Constructor test adapter; no replacement initialization policy. */
unsigned int rust_helper_swait_test_init_class(struct swait_queue_head *queue,
					     unsigned int class, bool disabled)
{
	unsigned long flags;
	bool before = irqs_disabled();
	unsigned int result;

	local_save_flags(flags);
	if (disabled)
		local_irq_disable();
#ifdef CONFIG_LOCKDEP
	__init_swait_queue_head(queue, swait_test_names[class], &swait_test_keys[class]);
#else
	/* Neither empty C keys nor disabled lockdep metadata are dereferenced. */
	__init_swait_queue_head(queue, NULL, NULL);
#endif
	result = irqs_disabled() == (disabled || before) ? 1U : 0;
	/* Restore even if a broken initializer changed the enabled entry mode. */
	local_irq_restore(flags);
	if (irqs_disabled() == before)
		result |= 2U;
	return result;
}

/* Caller owns an initialized quiescent queue; class is zero or one. A zero
 * result explicitly means metadata is unavailable, not that it was tested.
 */
unsigned int rust_helper_swait_test_class(struct swait_queue_head *queue,
					 unsigned int class)
{
#ifdef CONFIG_LOCKDEP
	unsigned int result = 8U;

	if (queue->lock.dep_map.key == &swait_test_keys[class])
		result |= 1U;
	if (queue->lock.dep_map.name == swait_test_names[class])
		result |= 2U;
	if (queue->lock.dep_map.wait_type_inner == LD_WAIT_SPIN)
		result |= 4U;
	return result;
#else
	return 0;
#endif
}
