// SPDX-License-Identifier: GPL-2.0-only
/* KUnit-only deterministic boundaries and dedicated bit-wait consumers. */
#include "sched.h"
#include <linux/bitops.h>
#include <linux/slab.h>
#include <linux/jiffies.h>
#include <linux/limits.h>
#include <linux/wait_bit.h>

int rusix_wait_bit_test_loop(unsigned int scenario, s64 *out);
int rusix_wait_bit_test_key(unsigned int scenario, s64 *out);
void rusix_wait_bit_test_time(unsigned long now, unsigned long deadline, s64 *out);

#define PROBE_BIT 3
struct bit_loop_probe {
	wait_queue_head_t queue;
	struct wait_bit_queue_entry waiter;
	unsigned long word;
	unsigned int scenario, calls, errors;
	bool lock;
};

static int probe_action(struct wait_bit_key *key, int mode)
{
	struct wait_bit_queue_entry *waiter =
		container_of(key, struct wait_bit_queue_entry, key);
	struct bit_loop_probe *test = container_of(waiter, struct bit_loop_probe, waiter);
	unsigned long flags;
	unsigned int expected = WQ_FLAG_CUSTOM | (test->lock ? WQ_FLAG_EXCLUSIVE : 0);

	test->calls++;
	if (test->calls > 3) {
		test->errors |= 1;
		return -ELOOP;
	}
	if (mode != TASK_UNINTERRUPTIBLE || key->flags != &test->word ||
	    key->bit_nr != PROBE_BIT || key->timeout != 0)
		test->errors |= 2;
	if (READ_ONCE(current->__state) != TASK_UNINTERRUPTIBLE || irqs_disabled())
		test->errors |= 4;
	if (waiter->wq_entry.flags != expected)
		test->errors |= 8;
	spin_lock_irqsave(&test->queue.lock, flags);
	if (test->queue.head.next != &waiter->wq_entry.entry ||
	    test->queue.head.prev != &waiter->wq_entry.entry)
		test->errors |= 16;
	spin_unlock_irqrestore(&test->queue.lock, flags);

	switch (test->scenario) {
	case 1: case 8:
		clear_bit(PROBE_BIT, &test->word);
		return 0;
	case 2: case 6:
		clear_bit(PROBE_BIT, &test->word);
		return -EIO;
	case 3: case 7:
		return -EIO;
	case 4: case 9:
		if (test->calls == 2)
			clear_bit(PROBE_BIT, &test->word);
		return 0;
	default:
		test->errors |= 32; /* initial-clear cases must not invoke action */
		return -EINVAL;
	}
}

static void probe_init(struct bit_loop_probe *test)
{
	init_waitqueue_head(&test->queue);
	test->waiter.key.flags = &test->word;
	test->waiter.key.bit_nr = PROBE_BIT;
	test->waiter.key.timeout = 0;
	init_waitqueue_entry(&test->waiter.wq_entry, current);
	test->waiter.wq_entry.flags = WQ_FLAG_CUSTOM;
	test->waiter.wq_entry.func = wake_bit_function;
	INIT_LIST_HEAD(&test->waiter.wq_entry.entry);
}

int rusix_wait_bit_test_loop(unsigned int scenario, s64 *out)
{
	struct bit_loop_probe test = { .scenario = scenario, .lock = scenario >= 5 };
	unsigned long flags;
	int ret;
	u32 clean = 0;

	if (scenario > 9 || irqs_disabled() || READ_ONCE(current->__state) != TASK_RUNNING)
		return -EINVAL;
	probe_init(&test);
	if (scenario != 0 && scenario != 5)
		set_bit(PROBE_BIT, &test.word);
	if (test.lock)
		ret = __wait_on_bit_lock(&test.queue, &test.waiter, probe_action, TASK_UNINTERRUPTIBLE);
	else
		ret = __wait_on_bit(&test.queue, &test.waiter, probe_action, TASK_UNINTERRUPTIBLE);

	/* Snapshot before rescue cleanup, so cleanup cannot hide a broken return. */
	if (READ_ONCE(current->__state) == TASK_RUNNING)
		clean |= 4;
	if (!irqs_disabled())
		clean |= 8;
	spin_lock_irqsave(&test.queue.lock, flags);
	if (list_empty(&test.waiter.wq_entry.entry))
		clean |= 1;
	if (list_empty(&test.queue.head))
		clean |= 2;
	out[0] = ret;
	out[1] = test.calls;
	out[2] = test.errors;
	out[3] = test.waiter.wq_entry.flags;
	out[4] = test_bit(PROBE_BIT, &test.word);
	out[5] = clean;
	list_del_init(&test.waiter.wq_entry.entry);
	__set_current_state(TASK_RUNNING);
	spin_unlock_irqrestore(&test.queue.lock, flags);
	/* Entry contract required IRQs enabled; do not contaminate later tests. */
	local_irq_enable();
	return 0;
}

int rusix_wait_bit_test_key(unsigned int scenario, s64 *out)
{
	struct bit_loop_probe test = {};
	struct wait_bit_key key;
	unsigned long flags, other = 0;
	int ret;
	bool matched;

	if (scenario > 5 || irqs_disabled() || READ_ONCE(current->__state) != TASK_RUNNING)
		return -EINVAL;
	probe_init(&test);
	key = test.waiter.key;
	if (scenario == 0)
		key.flags = &other;
	if (scenario == 1)
		key.bit_nr++;
	if (scenario == 2)
		set_bit(PROBE_BIT, &test.word);
	if (scenario == 4)
		key.timeout = ULONG_MAX; /* matcher must ignore timeout */
	if (scenario == 5) {
		key.bit_nr = -1;
		test.waiter.key.bit_nr = -1;
	}
	add_wait_queue(&test.queue, &test.waiter.wq_entry);
	spin_lock_irqsave(&test.queue.lock, flags);
	matched = __var_wake_key(&test.waiter.wq_entry, &key) == &key;
	if (scenario == 5) {
		/* Variable key matcher only: -1 is not a bitmap index. */
		ret = 0;
	} else {
		set_current_state(TASK_INTERRUPTIBLE);
		ret = wake_bit_function(&test.waiter.wq_entry, TASK_INTERRUPTIBLE, 0, &key);
	}
	out[0] = matched;
	out[1] = ret;
	out[2] = list_empty(&test.waiter.wq_entry.entry);
	out[3] = list_empty(&test.queue.head);
	out[4] = READ_ONCE(current->__state) == TASK_RUNNING;
	out[5] = test.waiter.wq_entry.flags;
	list_del_init(&test.waiter.wq_entry.entry);
	__set_current_state(TASK_RUNNING);
	spin_unlock_irqrestore(&test.queue.lock, flags);
	/* Entry contract required IRQs enabled; do not contaminate later tests. */
	local_irq_enable();
	return 0;
}

void rusix_wait_bit_test_time(unsigned long now, unsigned long deadline, s64 *out)
{
	/* Pure pinned C arithmetic oracle: does NOT write/read global jiffies. */
	out[0] = time_after_eq(now, deadline);
	out[1] = (long)(deadline - now);
	out[2] = now + deadline; /* wrapping addition; observed as signed bits */
}

int rusix_wait_bit_test_expired(s64 *out);
int rusix_wait_bit_test_expired(s64 *out)
{
	unsigned long word = 0;
	struct wait_bit_key key = { .flags = &word, .bit_nr = PROBE_BIT };

	if (irqs_disabled() || READ_ONCE(current->__state) != TASK_RUNNING)
		return -EINVAL;
	key.timeout = READ_ONCE(jiffies);
	set_current_state(TASK_INTERRUPTIBLE);
	out[0] = bit_wait_timeout(&key, TASK_INTERRUPTIBLE);
	/* Expiry is tested before scheduling or a state restore. */
	out[1] = READ_ONCE(current->__state) == TASK_INTERRUPTIBLE;
	out[2] = !irqs_disabled();
	__set_current_state(TASK_RUNNING);
	local_irq_enable();
	return 0;
}

struct bit_worker_fixture;
struct bit_worker_slot {
	struct wait_bit_queue_entry entry;
	struct bit_worker_fixture *fixture;
	u32 index, abort, release;
	atomic_t acquired;
	int result;
	u32 payload, running, detached, overlap;
};
struct bit_worker_fixture {
	wait_queue_head_t queue;
	unsigned long word, other_word;
	u32 payload;
	atomic_t occupancy;
	bool lock;
	struct bit_worker_slot slots[2];
};

static void bit_worker_init(struct bit_worker_fixture *fixture, bool lock)
{
	unsigned int i;

	memset(fixture, 0, sizeof(*fixture));
	init_waitqueue_head(&fixture->queue);
	set_bit(3, &fixture->word); /* initial busy bit; controller owns first release */
	atomic_set(&fixture->occupancy, 0);
	fixture->lock = lock;
	for (i = 0; i < 2; i++) {
		fixture->slots[i].fixture = fixture;
		fixture->slots[i].index = i;
		atomic_set(&fixture->slots[i].acquired, 0);
	}
}

/* A real finite action: invokes selected bit_wait_timeout, not a scheduling
 * model. Abort may still be overridden by the lock loop's atomic acquisition;
 * a successful returned claim MUST be released even after cancellation.
 */
static int bit_worker_action(struct wait_bit_key *key, int mode)
{
	struct bit_worker_slot *slot = container_of(key, struct bit_worker_slot, entry.key);

	if (READ_ONCE(slot->abort))
		return -ECANCELED;
	return bit_wait_timeout(key, mode);
}

static void bit_worker_clear_and_wake(struct bit_worker_fixture *fixture)
{
	clear_bit_unlock(3, &fixture->word);
	/* RELEASE orders earlier payload, full post-atomic barrier precedes wake. */
	smp_mb__after_atomic();
	__wake_up_bit(&fixture->queue, &fixture->word, 3);
}

static void bit_worker_run(struct bit_worker_fixture *fixture, unsigned int index,
			   unsigned long timeout)
{
	struct bit_worker_slot *slot = &fixture->slots[index];
	unsigned long hold_deadline;

	allow_signal(SIGUSR1);
	slot->entry.key.flags = &fixture->word;
	slot->entry.key.bit_nr = 3;
	slot->entry.key.timeout = jiffies + timeout;
	init_waitqueue_entry(&slot->entry.wq_entry, current);
	slot->entry.wq_entry.func = wake_bit_function;
	INIT_LIST_HEAD(&slot->entry.wq_entry.entry);
	if (READ_ONCE(slot->abort)) {
		slot->result = -ECANCELED;
		goto done;
	}
	if (fixture->lock)
		slot->result = __wait_on_bit_lock(&fixture->queue, &slot->entry,
						bit_worker_action, TASK_INTERRUPTIBLE);
	else
		slot->result = __wait_on_bit(&fixture->queue, &slot->entry,
					  bit_worker_action, TASK_INTERRUPTIBLE);
	if (!slot->result) {
		slot->payload = READ_ONCE(fixture->payload);
		if (fixture->lock) {
			/* Only successful bit acquisition permits entering this section. */
			slot->overlap = atomic_inc_return(&fixture->occupancy) != 1;
			atomic_set_release(&slot->acquired, 1);
			hold_deadline = jiffies + timeout;
			while (!READ_ONCE(slot->release) && !READ_ONCE(slot->abort) &&
			       time_before(jiffies, hold_deadline))
				schedule_timeout_uninterruptible(1);
			/* Record a missed explicit release as failure, not normal success. */
			if (!READ_ONCE(slot->release) && !READ_ONCE(slot->abort))
				slot->overlap |= 2;
			WRITE_ONCE(fixture->payload, 0x5678);
			atomic_dec(&fixture->occupancy);
			bit_worker_clear_and_wake(fixture);
		}
	}
done:
	slot->running = READ_ONCE(current->__state) == TASK_RUNNING;
	slot->detached = slot->entry.wq_entry.entry.next == &slot->entry.wq_entry.entry &&
			slot->entry.wq_entry.entry.prev == &slot->entry.wq_entry.entry;
	flush_signals(current);
	/* Rust publishes per-slot Completion only after return; no subsequent C
	 * access. All Arcs/taskrefs survive normal and failed cleanup paths.
	 */
}

/* Called exactly once before any worker owns a successful lock claim. Cleanup
 * must NOT use this to clear a bit owned by a worker; that would manufacture
 * overlapping successful critical sections in the test itself.
 */
static void bit_worker_first_release(struct bit_worker_fixture *fixture)
{
	WRITE_ONCE(fixture->payload, 0x1234);
	bit_worker_clear_and_wake(fixture);
}

/* Guard against failed startup/expiry observation before callback invocation. */
static void bit_worker_probe(struct bit_worker_fixture *fixture, unsigned int index,
			     unsigned int command, s64 *out)
{
	struct wait_bit_key key = { .flags = &fixture->word, .bit_nr = 3, .timeout = 999 };
	struct list_head *node;
	unsigned long flags;
	bool found = false;

	if (command == 0)
		key.flags = &fixture->other_word;
	if (command == 1)
		key.bit_nr = 4;
	spin_lock_irqsave(&fixture->queue.lock, flags);
	list_for_each(node, &fixture->queue.head) {
		if (node == &fixture->slots[index].entry.wq_entry.entry) {
			found = true;
			break;
		}
	}
	out[0] = found ? wake_bit_function(&fixture->slots[index].entry.wq_entry,
					 TASK_INTERRUPTIBLE, 0, &key) : -ENOENT;
	/* Never read entry after callback: successful autoremove permits retirement.
	 * Actual fixture retains it, but observation should not depend on that.
	 */
	spin_unlock_irqrestore(&fixture->queue.lock, flags);
}

static void bit_worker_abort_flags(struct bit_worker_fixture *fixture)
{
	WRITE_ONCE(fixture->slots[0].abort, 1);
	WRITE_ONCE(fixture->slots[1].abort, 1);
	WRITE_ONCE(fixture->slots[0].release, 1);
	WRITE_ONCE(fixture->slots[1].release, 1);
	/* Controller sends allowed SIGUSR1 + directwake to each referenced task.
	 * Do not clear someone else's lock. Owners observe release and clear their
	 * own bit; pending signal/timeout frees waiting callers. Lock loop can
	 * acquire despite action error, and worker still releases that acquisition.
	 */
}

/* Hash buckets are shared. Observe only this referenced task's generic entry;
 * never container_of an unrelated bucket member into a bit-wait object.
 */
static unsigned int bit_worker_hash_members(struct bit_worker_fixture *fixture,
					    struct task_struct *task)
{
	wait_queue_head_t *queue = bit_waitqueue(&fixture->word, 3);
	struct list_head *node;
	unsigned long flags;
	unsigned int count = 0;

	spin_lock_irqsave(&queue->lock, flags);
	list_for_each(node, &queue->head) {
		wait_queue_entry_t *entry = list_entry(node, wait_queue_entry_t, entry);

		if (entry->private == task && entry->func == wake_bit_function)
			count++;
	}
	spin_unlock_irqrestore(&queue->lock, flags);
	return count;
}

static void bit_worker_stack_timeout(struct bit_worker_fixture *fixture,
				     unsigned int index, unsigned long timeout)
{
	struct bit_worker_slot *slot = &fixture->slots[index];

	allow_signal(SIGUSR1);
	if (READ_ONCE(slot->abort))
		slot->result = -ECANCELED;
	else
		slot->result = out_of_line_wait_on_bit_timeout(&fixture->word, 3,
					bit_wait_timeout, TASK_INTERRUPTIBLE, timeout);
	if (!slot->result)
		slot->payload = READ_ONCE(fixture->payload);
	slot->running = READ_ONCE(current->__state) == TASK_RUNNING;
	slot->detached = bit_worker_hash_members(fixture, current) == 0;
	flush_signals(current);
}

static void bit_worker_stack_release(struct bit_worker_fixture *fixture)
{
	WRITE_ONCE(fixture->payload, 0x1234);
	clear_bit_unlock(3, &fixture->word);
	smp_mb__after_atomic();
	wake_up_bit(&fixture->word, 3); /* Actual hash bucket, not fixture private queue. */
}

/* Actual stack wrappers with unused NULL action: no fixture-owned waiter is
 * inspected or misrepresented as the wrapper's private stack storage.
 */
static int probe_precleared_wrapper(bool lock, s64 *out)
{
	unsigned long word = 0, flags;
	wait_queue_head_t *queue = bit_waitqueue(&word, PROBE_BIT);
	struct list_head *node;
	unsigned int count = 0;
	int result;

	if (irqs_disabled() || READ_ONCE(current->__state) != TASK_RUNNING)
		return -EINVAL;
	if (lock)
		result = out_of_line_wait_on_bit_lock(&word, PROBE_BIT, NULL, TASK_UNINTERRUPTIBLE);
	else
		result = out_of_line_wait_on_bit(&word, PROBE_BIT, NULL, TASK_UNINTERRUPTIBLE);
	out[0] = result;
	out[1] = test_bit(PROBE_BIT, &word);
	out[2] = READ_ONCE(current->__state) == TASK_RUNNING;
	out[4] = !irqs_disabled();
	spin_lock_irqsave(&queue->lock, flags);
	list_for_each(node, &queue->head) {
		wait_queue_entry_t *entry = list_entry(node, wait_queue_entry_t, entry);

		if (entry->private == current && entry->func == wake_bit_function)
			count++;
	}
	out[3] = count;
	out[5] = 0;
	__set_current_state(TASK_RUNNING);
	spin_unlock_irqrestore(&queue->lock, flags);
	local_irq_enable();
	/* Successful lock claim belongs to this callback and is no longer queued. */
	clear_bit(PROBE_BIT, &word);
	return 0;
}

struct bit_test_case {
	struct bit_worker_fixture worker;
	unsigned int mode, scenario;
	s64 deterministic[8];
};
void *rusix_bit_case_alloc(unsigned int mode, unsigned int scenario);
void rusix_bit_case_free(void *data);
void rusix_bit_case_run(void *data, unsigned int index, unsigned int timeout_ms);
void rusix_bit_case_result(void *data, unsigned int index, s64 *out);
u32 rusix_bit_case_members(void *data, struct task_struct *task);
u32 rusix_bit_case_acquired(void *data);
u32 rusix_bit_case_value(void *data);
void rusix_bit_case_release(void *data);
void rusix_bit_case_release_owner(void *data, unsigned int index);
void rusix_bit_case_abort(void *data);
void rusix_bit_case_probe(void *data, unsigned int command, s64 *out);

void *rusix_bit_case_alloc(unsigned int mode, unsigned int scenario)
{
	struct bit_test_case *test = kzalloc(sizeof(*test), GFP_KERNEL);

	if (!test)
		return NULL;
	test->mode = mode;
	test->scenario = scenario;
	bit_worker_init(&test->worker, mode == 4);
	return test;
}

void rusix_bit_case_free(void *data)
{
	kfree(data);
}

void rusix_bit_case_run(void *data, unsigned int index, unsigned int timeout_ms)
{
	struct bit_test_case *test = data;
	unsigned long timeout = msecs_to_jiffies(timeout_ms);

	switch (test->mode) {
	case 0:
		if (test->scenario == 10 || test->scenario == 11)
			test->deterministic[0] = probe_precleared_wrapper(test->scenario == 11,
								       test->deterministic + 1);
		else
			test->deterministic[0] = rusix_wait_bit_test_loop(test->scenario, test->deterministic + 1);
		break;
	case 1:
		test->deterministic[0] = rusix_wait_bit_test_key(test->scenario, test->deterministic + 1);
		break;
	case 2:
		test->deterministic[0] = rusix_wait_bit_test_expired(test->deterministic + 1);
		break;
	case 6:
		bit_worker_stack_timeout(&test->worker, index, timeout);
		break;
	default:
		bit_worker_run(&test->worker, index, timeout);
		break;
	}
}

/* Rust calls only after acknowledgment for this exact slot. */
void rusix_bit_case_result(void *data, unsigned int index, s64 *out)
{
	struct bit_test_case *test = data;
	struct bit_worker_slot *slot = &test->worker.slots[index];

	if (test->mode <= 2) {
		memcpy(out, test->deterministic, sizeof(test->deterministic));
		return;
	}
	out[0] = slot->result;
	out[1] = slot->payload;
	out[2] = slot->running;
	out[3] = slot->detached;
	out[4] = slot->overlap;
	out[5] = out[6] = out[7] = 0;
}

u32 rusix_bit_case_members(void *data, struct task_struct *task)
{
	struct bit_test_case *test = data;
	struct list_head *node;
	unsigned long flags;
	u32 mask = 0, count = 0;

	if (test->mode == 6)
		return bit_worker_hash_members(&test->worker, task);
	spin_lock_irqsave(&test->worker.queue.lock, flags);
	list_for_each(node, &test->worker.queue.head) {
		if (++count > 2) {
			mask |= 4;
			break;
		}
		if (node == &test->worker.slots[0].entry.wq_entry.entry)
			mask |= 1;
		else if (node == &test->worker.slots[1].entry.wq_entry.entry)
			mask |= 2;
		else
			mask |= 4;
	}
	spin_unlock_irqrestore(&test->worker.queue.lock, flags);
	return mask;
}

u32 rusix_bit_case_acquired(void *data)
{
	struct bit_test_case *test = data;

	return (atomic_read_acquire(&test->worker.slots[0].acquired) != 0) |
	       ((atomic_read_acquire(&test->worker.slots[1].acquired) != 0) << 1);
}

u32 rusix_bit_case_value(void *data)
{
	struct bit_test_case *test = data;

	return test_bit(3, &test->worker.word);
}

void rusix_bit_case_release(void *data)
{
	struct bit_test_case *test = data;

	if (test->mode == 6)
		bit_worker_stack_release(&test->worker);
	else
		bit_worker_first_release(&test->worker);
}

void rusix_bit_case_release_owner(void *data, unsigned int index)
{
	struct bit_test_case *test = data;

	WRITE_ONCE(test->worker.slots[index].release, 1);
}

void rusix_bit_case_abort(void *data)
{
	struct bit_test_case *test = data;

	bit_worker_abort_flags(&test->worker);
}

void rusix_bit_case_probe(void *data, unsigned int command, s64 *out)
{
	struct bit_test_case *test = data;

	bit_worker_probe(&test->worker, 0, command, out);
}
