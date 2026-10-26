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
