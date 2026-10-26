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
int rusix_wait_test_enrollment(unsigned int scenario, bool disabled, u32 *out);
u32 rusix_wait_test_constructor(bool disabled);

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

struct enrollment_log {
	u32 order, calls;
};
struct enrollment_node {
	wait_queue_entry_t wait;
	u32 ordinal;
};

static int enrollment_callback(wait_queue_entry_t *wait, unsigned int mode,
			       int wake_flags, void *key)
{
	struct enrollment_node *node = container_of(wait, struct enrollment_node, wait);
	struct enrollment_log *log = wait->private;

	if (log->calls >= 5)
		return -EINVAL;
	log->order |= (node->ordinal + 1) << (4 * log->calls++);
	return 0;
}

static u32 enrollment_order(wait_queue_head_t *queue)
{
	struct list_head *entry;
	u32 order = 0, count = 0;

	list_for_each(entry, &queue->head) {
		struct enrollment_node *node;

		if (count == 5)
			return ~0U;
		node = container_of(entry, struct enrollment_node, wait.entry);
		order |= (node->ordinal + 1) << (4 * count++);
	}
	return order;
}

static bool enrollment_poisoned(wait_queue_entry_t *entry)
{
	return entry->entry.next == LIST_POISON1 && entry->entry.prev == LIST_POISON2;
}

/* Fixed synchronous API sequences, not a second insertion implementation.
 * out[0..2]: structural order, callback order, operation result;
 * out[3]: observed link invariant bits; out[4]: context/field errors;
 * out[5..9]: final flags of each real entry.
 */
int rusix_wait_test_enrollment(unsigned int scenario, bool disabled, u32 *out)
{
	struct enrollment_node nodes[5] = {};
	struct enrollment_log log = {};
	wait_queue_head_t queue;
	unsigned long incoming, held;
	bool before;
	u32 links = 0, errors = 0, order;
	int result = 0;
	unsigned int i;

	if (scenario > 3)
		return -EINVAL;
	init_waitqueue_head(&queue);
	for (i = 0; i < 5; i++) {
		nodes[i].ordinal = i;
		/* Deliberately leave NULL links: enrollment must initialize them,
		 * not assume they were self-linked by an entry initializer.
		 */
		nodes[i].wait.func = enrollment_callback;
		nodes[i].wait.private = &log;
		nodes[i].wait.flags = 0x100;
	}
	local_save_flags(incoming);
	if (disabled)
		local_irq_disable();
	before = irqs_disabled();
	switch (scenario) {
	case 0:
		nodes[0].wait.flags |= WQ_FLAG_EXCLUSIVE;
		add_wait_queue_priority(&queue, &nodes[0].wait);
		add_wait_queue_priority(&queue, &nodes[1].wait);
		nodes[2].wait.flags |= WQ_FLAG_EXCLUSIVE;
		add_wait_queue(&queue, &nodes[2].wait);
		add_wait_queue(&queue, &nodes[3].wait);
		add_wait_queue_exclusive(&queue, &nodes[4].wait);
		break;
	case 1:
		add_wait_queue_priority(&queue, &nodes[0].wait);
		/* Preserve NULL links on rejection; delete-init must not go unnoticed. */
		result = add_wait_queue_priority_exclusive(&queue, &nodes[1].wait);
		if (!nodes[1].wait.entry.next && !nodes[1].wait.entry.prev)
			links = 1;
		break;
	case 2:
		add_wait_queue(&queue, &nodes[0].wait);
		nodes[1].wait.flags |= WQ_FLAG_PRIORITY;
		add_wait_queue_exclusive(&queue, &nodes[1].wait);
		result = add_wait_queue_priority_exclusive(&queue, &nodes[2].wait);
		break;
	case 3:
		for (i = 0; i < 3; i++)
			add_wait_queue_exclusive(&queue, &nodes[i].wait);
		remove_wait_queue(&queue, &nodes[1].wait);
		if (enrollment_poisoned(&nodes[1].wait))
			links |= 1;
		/* Legal re-add after poison; insertion initializes both links. */
		add_wait_queue(&queue, &nodes[1].wait);
		break;
	}
	spin_lock_irqsave(&queue.lock, held);
	order = enrollment_order(&queue);
	spin_unlock_irqrestore(&queue.lock, held);
	__wake_up(&queue, TASK_INTERRUPTIBLE, 0, NULL);
	if (scenario == 3) {
		remove_wait_queue(&queue, &nodes[1].wait); /* head */
		if (enrollment_poisoned(&nodes[1].wait))
			links |= 2;
		remove_wait_queue(&queue, &nodes[2].wait); /* tail */
		if (enrollment_poisoned(&nodes[2].wait))
			links |= 4;
		remove_wait_queue(&queue, &nodes[0].wait); /* only entry */
		if (enrollment_poisoned(&nodes[0].wait))
			links |= 8;
		INIT_LIST_HEAD(&nodes[3].wait.entry);
		remove_wait_queue(&queue, &nodes[3].wait);
		if (enrollment_poisoned(&nodes[3].wait))
			links |= 16;
		if (queue.head.next == &queue.head && queue.head.prev == &queue.head)
			links |= 32;
	}
	if (irqs_disabled() != before)
		errors |= 1;
	local_irq_restore(incoming);
	for (i = 0; i < 5; i++) {
		if (nodes[i].wait.func != enrollment_callback || nodes[i].wait.private != &log)
			errors |= 2;
		out[5 + i] = nodes[i].wait.flags;
	}
	/* Private queue: discard surviving links without invoking policy under test.
	 * No node or queue pointer escapes this synchronous call.
	 */
	while (!list_empty(&queue.head))
		list_del_init(queue.head.next);
	out[0] = order;
	out[1] = log.order;
	out[2] = result;
	out[3] = links;
	out[4] = errors;
	return 0;
}

#ifdef CONFIG_LOCKDEP
static struct lock_class_key enrollment_keys[2];
static const char enrollment_names[2][24] = { "wait-test-first", "wait-test-second" };
#endif

/* Three simultaneously live queues: same caller class twice, then distinct. */
u32 rusix_wait_test_constructor(bool disabled)
{
	wait_queue_head_t queues[3];
	unsigned long flags, held;
	bool before;
	u32 errors = 0;
	unsigned int i;

	local_save_flags(flags);
	if (disabled)
		local_irq_disable();
	before = irqs_disabled();
	for (i = 0; i < 3; i++) {
		unsigned int class = i == 2;
		wait_queue_head_t *queue = &queues[i];

#ifdef CONFIG_LOCKDEP
		__init_waitqueue_head(queue, enrollment_names[class], &enrollment_keys[class]);
		if (queue->lock.dep_map.key != &enrollment_keys[class] ||
		    queue->lock.dep_map.name != enrollment_names[class] ||
		    queue->lock.dep_map.wait_type_inner != LD_WAIT_CONFIG)
			errors |= 1;
#else
		(void)class;
		__init_waitqueue_head(queue, NULL, NULL);
#endif
		if (irqs_disabled() != before)
			errors |= 2;
		spin_lock_irqsave(&queue->lock, held);
		if (queue->head.next != &queue->head || queue->head.prev != &queue->head)
			errors |= 4;
		if (!irqs_disabled())
			errors |= 8;
		spin_unlock_irqrestore(&queue->lock, held);
		if (irqs_disabled() != before)
			errors |= 16;
	}
	local_irq_restore(flags);
	/* Make unavailable metadata observation explicit to the Rust oracle. */
	return errors | (IS_ENABLED(CONFIG_LOCKDEP) ? 0x100 : 0);
}
