// SPDX-License-Identifier: GPL-2.0-only
/* KUnit-only synchronous observations of generic wait wake policy. */
#include "sched.h"
#include <linux/slab.h>
#include <linux/limits.h>
#include <linux/wait.h>

/* Private test bridge; keep scheduler-internal declarations out of bindings. */
int rusix_wait_test_run(unsigned int scenario, unsigned int wrapper,
			bool disabled, u32 *out);
u32 rusix_wait_test_null_sync(bool disabled);

#define TEST_NODES 4
struct wait_policy_test;
struct wait_policy_node {
	wait_queue_entry_t wait;
	struct wait_policy_test *owner;
	unsigned int ordinal;
	int result;
	bool flip_exclusive;
	bool retire;
};
struct wait_policy_test {
	wait_queue_head_t queue;
	struct wait_policy_node *owned[TEST_NODES];
	u32 log, calls, errors;
	unsigned int mode;
	int wake_flags;
	void *key;
	unsigned long key_storage;
};

static int wait_policy_callback(wait_queue_entry_t *wait, unsigned int mode,
				int wake_flags, void *key)
{
	struct wait_policy_node *node = container_of(wait, struct wait_policy_node, wait);
	struct wait_policy_test *test = node->owner;
	unsigned int ordinal = node->ordinal;
	int result = node->result;

	lockdep_assert_held(&test->queue.lock);
	if (mode != test->mode || wake_flags != test->wake_flags || key != test->key)
		test->errors |= 1;
	if (!irqs_disabled())
		test->errors |= 2;
	if (test->calls >= TEST_NODES) {
		test->errors |= 4;
		return -EINVAL;
	}
	test->log |= (ordinal + 1) << (test->calls++ * 4);
	if (node->flip_exclusive)
		wait->flags ^= WQ_FLAG_EXCLUSIVE;
	if (node->retire) {
		list_del_init(&wait->entry);
		/* External slot cleared BEFORE free. Neither fixture nor callback
		 * touches this entry again; cached successor remains allocated.
		 */
		test->owned[ordinal] = NULL;
		kfree(node);
	}
	return result;
}

/* Scenarios feed inputs, never duplicate traversal or compute expected results.
 * out: callback order (4-bit ordinals), calls, public count, surviving entry
 * mask, observation errors. Count is UINT_MAX for void-returning wrappers.
 * wrapper: 0 normal, 1 current CPU, 2 locked, 3 locked key, 4 sync key,
 *          5 locked sync key, 6 sync. disabled chooses incoming IRQ state.
 */
int rusix_wait_test_run(unsigned int scenario, unsigned int wrapper,
			bool disabled, u32 *out)
{
	struct wait_policy_test test = {};
	unsigned long incoming, held;
	unsigned int n = TEST_NODES, i;
	int budget = 1;
	u32 result = ~0U, live = 0;
	bool irq_before;

	if (scenario > 12 || wrapper > 6)
		return -EINVAL;
	init_waitqueue_head(&test.queue);
	/* Deliberately differs from TASK_NORMAL: catch hardcoded mode forwarding. */
	test.mode = TASK_INTERRUPTIBLE;
	test.key = &test.key_storage;
	test.wake_flags = wrapper == 1 ? WF_CURRENT_CPU : wrapper >= 4 ? WF_SYNC : 0;
	if (wrapper == 2 || wrapper == 6)
		test.key = NULL;
	if (scenario == 0)
		n = 0;
	if (scenario == 2 || scenario == 8 || scenario == 10)
		budget = 0;
	if (scenario == 3)
		budget = -1;
	if (scenario == 4)
		budget = 2;
	if (scenario == 12)
		budget = INT_MIN;
	for (i = 0; i < n; i++) {
		struct wait_policy_node *node = kzalloc(sizeof(*node), GFP_KERNEL);

		if (!node)
			goto no_memory;
		test.owned[i] = node;
		node->owner = &test;
		node->ordinal = i;
		node->result = 1;
		init_waitqueue_func_entry(&node->wait, wait_policy_callback);
		node->wait.flags = WQ_FLAG_EXCLUSIVE;
		/* Mixed nonexclusive/exclusive FIFO; only ordinal 2 consumes. */
		if (scenario == 1 && i != 1)
			node->wait.flags = 0;
		if (scenario == 4 && i == 0)
			node->result = 2;
		if (scenario == 5 && i == 0)
			node->result = 0;
		if (scenario == 6 && i == 1)
			node->result = -7;
		if (scenario == 6 && i == 0)
			node->wait.flags = 0;
		if (scenario == 7 && i == 0)
			node->flip_exclusive = true;
		if (scenario == 8 && i == 0) {
			node->wait.flags = 0;
			node->flip_exclusive = true;
		}
		if (scenario >= 9 && scenario <= 11) {
			node->retire = true;
			if (scenario == 9 && i == 0)
				node->result = 0;
			if (scenario == 9 && i == 1)
				node->result = -7;
		}
		/* Fixtures are private and not published; preserve explicit FIFO. */
		list_add_tail(&node->wait.entry, &test.queue.head);
	}

	local_save_flags(incoming);
	if (disabled)
		local_irq_disable();
	irq_before = irqs_disabled();
	if (wrapper == 2 || wrapper == 3 || wrapper == 5)
		spin_lock_irqsave(&test.queue.lock, held);
	switch (wrapper) {
	case 0:
		result = __wake_up(&test.queue, test.mode, budget, test.key);
		break;
	case 1:
		__wake_up_on_current_cpu(&test.queue, test.mode, test.key);
		break;
	case 2:
		__wake_up_locked(&test.queue, test.mode, budget);
		break;
	case 3:
		__wake_up_locked_key(&test.queue, test.mode, test.key);
		break;
	case 4:
		__wake_up_sync_key(&test.queue, test.mode, test.key);
		break;
	case 5:
		__wake_up_locked_sync_key(&test.queue, test.mode, test.key);
		break;
	case 6:
		__wake_up_sync(&test.queue, test.mode);
		break;
	}
	if (wrapper == 2 || wrapper == 3 || wrapper == 5) {
		lockdep_assert_held(&test.queue.lock);
		if (!irqs_disabled())
			test.errors |= 8;
		spin_unlock_irqrestore(&test.queue.lock, held);
	}
	if (irqs_disabled() != irq_before)
		test.errors |= 16;
	/* Always restore before cleanup/assertions, including failed observations. */
	local_irq_restore(incoming);
	for (i = 0; i < n; i++) {
		if (test.owned[i]) {
			live |= 1U << i;
			list_del_init(&test.owned[i]->wait.entry);
			kfree(test.owned[i]);
		}
	}
	out[0] = test.log;
	out[1] = test.calls;
	out[2] = result;
	out[3] = live;
	out[4] = test.errors;
	return 0;
no_memory:
	for (i = 0; i < n; i++) {
		if (test.owned[i]) {
			list_del_init(&test.owned[i]->wait.entry);
			kfree(test.owned[i]);
		}
	}
	return -ENOMEM;
}

/* Null is allowed only by these sync wrappers. No fake queue is supplied. */
u32 rusix_wait_test_null_sync(bool disabled)
{
	unsigned long flags;
	bool before;
	u32 errors = 0;

	local_save_flags(flags);
	if (disabled)
		local_irq_disable();
	before = irqs_disabled();
	__wake_up_sync_key(NULL, TASK_INTERRUPTIBLE, NULL);
	if (irqs_disabled() != before)
		errors |= 1;
	__wake_up_sync(NULL, TASK_UNINTERRUPTIBLE);
	if (irqs_disabled() != before)
		errors |= 2;
	local_irq_restore(flags);
	return errors;
}
