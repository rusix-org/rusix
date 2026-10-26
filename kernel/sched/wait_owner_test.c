// SPDX-License-Identifier: GPL-2.0-only
/* KUnit-only borrowed-global-table observations and retained worker fixtures. */
#include "sched.h"
#include <asm/sections.h>
#include <linux/cache.h>
#include <linux/hash.h>
#include <linux/jiffies.h>
#include <linux/limits.h>
#include <linux/slab.h>
#include <linux/string.h>
#include <linux/wait_bit.h>

void rusix_owner_hash_observe(unsigned long address, int bit, bool variable, unsigned long *out);
u32 rusix_owner_head_observe(unsigned long identity, unsigned int index);
void *rusix_owner_alloc(unsigned int mode, unsigned int flags_a, unsigned int flags_b);
void rusix_owner_free(void *data);
void rusix_owner_run(void *data, unsigned int slot, unsigned int timeout_ms);
u32 rusix_owner_members(void *data);
void rusix_owner_publish(void *data, unsigned int slot, u32 payload);
void rusix_owner_abort(void *data);
void rusix_owner_result(void *data, unsigned int slot, s64 *out);

/* Independent original C hash macros, not a transcription of the Rust multiply.
 * Integer identities may be fabricated here; never dereference or wake them.
 * Output: C index, actual queue address, actual base, C stride, C head alignment,
 * configured table cache alignment. No global list state is changed.
 */
void rusix_owner_hash_observe(unsigned long address, int bit, bool variable,
			       unsigned long *out)
{
	const int shift = BITS_PER_LONG == 32 ? 5 : 6;

	out[0] = variable ? hash_ptr((void *)address, 8) : hash_long(address << shift | bit, 8);
	out[1] = (unsigned long)(variable ? __var_waitqueue((void *)address) :
				bit_waitqueue((unsigned long *)address, bit));
	out[2] = (unsigned long)__var_waitqueue(NULL); /* identity only: hash(0)==0 */
	out[3] = sizeof(wait_queue_head_t);
	out[4] = __alignof__(wait_queue_head_t);
	out[5] = SMP_CACHE_BYTES;
}

/* Call only with an identity already proved by independent hash/layout checks to
 * select the given index. Lock exactly one head, never nested shared-class locks.
 * No list emptiness assumptions: filesystem/users may already occupy any bucket.
 * Result error mask; bit8 means debug metadata was available and checked.
 */
u32 rusix_owner_head_observe(unsigned long identity, unsigned int index)
{
	wait_queue_head_t *head = __var_waitqueue((void *)identity);
	wait_queue_head_t *base = __var_waitqueue(NULL);
	unsigned long flags;
	bool before = irqs_disabled();
	u32 result = 0;

	if ((unsigned long)head != (unsigned long)base + index * sizeof(*head))
		return 1; /* Do not acquire a wrongly selected pointer. */
	spin_lock_irqsave(&head->lock, flags);
	if (!irqs_disabled())
		result |= 2;
#ifdef CONFIG_LOCKDEP
	result |= 0x100;
	/* Constructor class/name are immutable after boot. class_cache is NOT an
	 * identity contract; live registration timing differs between buckets.
	 */
	if (!head->lock.dep_map.key || head->lock.dep_map.key != base->lock.dep_map.key)
		result |= 4;
	if (!head->lock.dep_map.name || head->lock.dep_map.name != base->lock.dep_map.name)
		result |= 8;
	if (head->lock.dep_map.wait_type_inner != LD_WAIT_CONFIG)
		result |= 16;
	if ((unsigned long)head->lock.dep_map.key >= (unsigned long)__init_begin &&
	    (unsigned long)head->lock.dep_map.key < (unsigned long)__init_end)
		result |= 32;
	if (!head->lock.dep_map.name ||
	    ((unsigned long)head->lock.dep_map.name >= (unsigned long)__init_begin &&
	     (unsigned long)head->lock.dep_map.name < (unsigned long)__init_end))
		result |= 64;
	else if (strcmp(head->lock.dep_map.name, "bit_wait_table + i"))
		result |= 64;
#endif
	spin_unlock_irqrestore(&head->lock, flags);
	if (!!irqs_disabled() != before)
		result |= 128;
	return result;
}

struct owner_collision;
struct owner_slot {
	struct owner_collision *owner;
	struct wait_bit_queue_entry entry;
	struct task_struct *held_task; /* Released only when fixture is safe to free. */
	unsigned int word_index, initial_flags;
	u32 ready, abort, payload;
	long result;
	u32 seen_payload, running, detached;
};
struct owner_collision {
	unsigned long words[257]; /* each address is distinct, valid and stable */
	wait_queue_head_t *queues[257];
	wait_queue_head_t private_queue;
	unsigned int mode;
	wait_queue_head_t *bucket; /* global borrowed head, or private_queue for constructor mode */
	struct owner_slot slots[2];
};

/* Caller frees returned allocation only after both callback Arcs are gone.
 * Bounded pigeonhole search uses ACTUAL returned queue identity, not assumptions
 * that an oracle index corresponds to the selected implementation's address.
 */
void *rusix_owner_alloc(unsigned int mode, unsigned int flags_a, unsigned int flags_b)
{
	struct owner_collision *test = kzalloc(sizeof(*test), GFP_KERNEL);
	unsigned int i, j;

	if (!test)
		return ERR_PTR(-ENOMEM);
	test->mode = mode;
	test->slots[0].owner = test;
	test->slots[1].owner = test;
	test->slots[0].initial_flags = flags_a;
	test->slots[1].initial_flags = flags_b;
	if (mode == 1) {
		init_waitqueue_head(&test->private_queue);
		test->bucket = &test->private_queue;
		return test;
	}
	for (i = 0; i < ARRAY_SIZE(test->words); i++) {
		test->queues[i] = __var_waitqueue(&test->words[i]);
		for (j = 0; j < i; j++) {
			if (test->queues[j] == test->queues[i]) {
				test->bucket = test->queues[i];
				test->slots[0].word_index = j;
				test->slots[1].word_index = i;
				return test;
			}
		}
	}
	kfree(test);
	return ERR_PTR(-ENOSPC); /* Distinct from allocation failure. */
}

static void collision_worker(struct owner_slot *slot, unsigned long timeout)
{
	struct owner_collision *test = slot->owner;
	unsigned long deadline = jiffies + timeout, now;
	long error;

	allow_signal(SIGUSR1);
	init_wait_var_entry(&slot->entry, &test->words[slot->word_index], slot->initial_flags);
	for (;;) {
		error = prepare_to_wait_event(test->bucket, &slot->entry.wq_entry, TASK_INTERRUPTIBLE);
		if (READ_ONCE(slot->abort)) {
			slot->result = -ECANCELED;
			break;
		}
		if (smp_load_acquire(&slot->ready)) {
			slot->seen_payload = READ_ONCE(slot->payload);
			slot->result = 1;
			break;
		}
		if (error) {
			slot->result = error;
			break;
		}
		now = jiffies;
		if (time_after_eq(now, deadline)) {
			slot->result = 0;
			break;
		}
		schedule_timeout(deadline - now);
	}
	finish_wait(test->bucket, &slot->entry.wq_entry);
	slot->running = READ_ONCE(current->__state) == TASK_RUNNING;
	slot->detached = slot->entry.wq_entry.entry.next == &slot->entry.wq_entry.entry &&
			slot->entry.wq_entry.entry.prev == &slot->entry.wq_entry.entry;
	/* Preserve snapshots; never repair the global queue to conceal a failed
	 * finish. Final destruction retains both storage and task if still linked.
	 */
	__set_current_state(TASK_RUNNING);
	flush_signals(current);
	/* Rust Completion publication follows return; no more C slot accesses. */
}

/* Observe own identity only. No foreign entry casts, global count/empty checks,
 * deletion, or ownership assertions about another kernel subsystem's waiter.
 */
u32 rusix_owner_members(void *data)
{
	struct owner_collision *test = data;
	struct list_head *node;
	unsigned long flags;
	unsigned int mask = 0;

	spin_lock_irqsave(&test->bucket->lock, flags);
	list_for_each(node, &test->bucket->head) {
		if (node == &test->slots[0].entry.wq_entry.entry)
			mask |= 1;
		if (node == &test->slots[1].entry.wq_entry.entry)
			mask |= 2;
	}
	spin_unlock_irqrestore(&test->bucket->lock, flags);
	return mask;
}

void rusix_owner_publish(void *data, unsigned int index, u32 payload)
{
	struct owner_collision *test = data;
	struct owner_slot *slot = &test->slots[index];

	WRITE_ONCE(slot->payload, payload);
	smp_store_release(&slot->ready, 1);
	/* Pair condition publication with potentially lockless active-queue test. */
	smp_mb();
	wake_up_var(&test->words[slot->word_index]);
}

void rusix_owner_abort(void *data)
{
	struct owner_collision *test = data;
	unsigned int i;

	if (test->mode == 1)
		return;
	for (i = 0; i < 2; i++)
		WRITE_ONCE(test->slots[i].abort, 1);
	smp_mb();
	for (i = 0; i < 2; i++)
		wake_up_var(&test->words[test->slots[i].word_index]);
	/* Controller additionally direct-wakes each retained task and waits
	 * with one finite shared cleanup deadline; no table or foreign entry cleanup.
	 */
}

/* Dedicated callback only: changes current's state, never the controller's.
 * Snapshot failures before repair. Private queue/storage remain owned throughout
 * callback invocation, so test reads do not rely on production post-removal use.
 */
static void constructor_probe(struct owner_collision *test)
{
	const int flags_values[] = { 0, WQ_FLAG_EXCLUSIVE, WQ_FLAG_PRIORITY, INT_MIN, -1 };
	struct owner_slot *slot = &test->slots[0];
	struct wait_bit_queue_entry *entry = &slot->entry;
	unsigned int i, errors = 0;
	unsigned long irq;

	for (i = 0; i < ARRAY_SIZE(flags_values); i++) {
		struct wait_bit_key key = { .flags = &test->words[0], .bit_nr = -1 };
		struct list_head *node = &entry->wq_entry.entry;
		int ret;

		init_wait_var_entry(entry, &test->words[0], flags_values[i]);
		if (entry->key.flags != &test->words[0] || entry->key.bit_nr != -1 ||
		    entry->key.timeout || entry->wq_entry.flags != (unsigned int)flags_values[i] ||
		    entry->wq_entry.private != current || !entry->wq_entry.func ||
		    node->next != node || node->prev != node)
			errors |= 1;
		if (!entry->wq_entry.func)
			continue;
		spin_lock_irqsave(&test->bucket->lock, irq);
		list_add_tail(node, &test->bucket->head);
		set_current_state(TASK_INTERRUPTIBLE);
		key.flags = &test->words[1];
		if (entry->wq_entry.func(&entry->wq_entry, TASK_NORMAL, 0, &key) != 0 ||
		    READ_ONCE(current->__state) != TASK_INTERRUPTIBLE || list_empty(node))
			errors |= 2;
		key.flags = &test->words[0];
		key.bit_nr = 0;
		if (entry->wq_entry.func(&entry->wq_entry, TASK_NORMAL, 0, &key) != 0 ||
		    READ_ONCE(current->__state) != TASK_INTERRUPTIBLE || list_empty(node))
			errors |= 4;
		key.bit_nr = -1;
		if (entry->wq_entry.func(&entry->wq_entry, 0, 0, &key) != 0 || list_empty(node))
			errors |= 8;
		set_current_state(TASK_INTERRUPTIBLE);
		ret = entry->wq_entry.func(&entry->wq_entry, TASK_NORMAL, 0, &key);
		if (ret != 1 || node->next != node || node->prev != node ||
		    READ_ONCE(current->__state) != TASK_RUNNING)
			errors |= 16;
		/* Repair only after recording; never leave sleeping state/list links. */
		__set_current_state(TASK_RUNNING);
		if (!list_empty(node))
			list_del_init(node);
		spin_unlock_irqrestore(&test->bucket->lock, irq);
	}
	slot->result = errors;
	slot->seen_payload = ARRAY_SIZE(flags_values);
	slot->running = READ_ONCE(current->__state) == TASK_RUNNING;
	slot->detached = list_empty(&slot->entry.wq_entry.entry);
}

void rusix_owner_run(void *data, unsigned int index, unsigned int timeout_ms)
{
	struct owner_collision *test = data;

	/* No slot is run twice. Retain callback private=current even if a failed
	 * cleanup forces the destructor to retain a globally reachable waiter.
	 */
	get_task_struct(current);
	test->slots[index].held_task = current;
	if (test->mode == 1)
		constructor_probe(test);
	else
		collision_worker(&test->slots[index], msecs_to_jiffies(timeout_ms));
}
void rusix_owner_result(void *data, unsigned int index, s64 *out)
{
	struct owner_slot *slot = &((struct owner_collision *)data)->slots[index];

	/* Controller has observed this slot's completion before this plain read. */
	out[0] = slot->result;
	out[1] = slot->seen_payload;
	out[2] = slot->running;
	out[3] = slot->detached;
}
void rusix_owner_free(void *data)
{
	struct owner_collision *test = data;
	unsigned int i;

	/* Last Arc means no callback can enroll again, not that tested cleanup
	 * necessarily worked. Retain storage AND private task references if own
	 * nodes remain reachable, or a started node lacks both final self-links
	 * (including possible linkage to a wrong head). Recorded results still fail.
	 * No foreign waiter is removed and no shared head is reinitialized.
	 */
	if (rusix_owner_members(data))
		return;
	for (i = 0; i < 2; i++) {
		struct list_head *node = &test->slots[i].entry.wq_entry.entry;

		if (test->slots[i].held_task && !list_empty_careful(node))
			return;
	}
	for (i = 0; i < 2; i++)
		if (test->slots[i].held_task)
			put_task_struct(test->slots[i].held_task);
	kfree(test);
}
