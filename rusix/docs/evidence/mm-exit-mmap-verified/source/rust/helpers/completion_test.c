// SPDX-License-Identifier: GPL-2.0
/* Temporary KUnit-only queue observation; no completion policy implementation.
 * Remove when Rust owns a reviewed waiter-inspection interface for these tests.
 */
#include <linux/completion.h>

unsigned int rust_helper_completion_waiter_count(struct completion *completion)
{
	struct list_head *entry;
	unsigned long flags;
	unsigned int count = 0;

	raw_spin_lock_irqsave(&completion->wait.lock, flags);
	list_for_each(entry, &completion->wait.task_list) {
		if (++count == 3)
			break;
	}
	raw_spin_unlock_irqrestore(&completion->wait.lock, flags);
	return count;
}
