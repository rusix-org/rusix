// SPDX-License-Identifier: GPL-2.0-only
/* Private-thread tests of locked wait iteration and original C caller macros. */
#include "sched.h"
#include <linux/slab.h>
#include <linux/wait.h>
#include <linux/workqueue.h>

struct locked_case {
	wait_queue_head_t queue;
	struct delayed_work watchdog;
	bool irq;
	unsigned int mode, scenario;
	u32 abort, ready, payload, checks, expired;
	s64 result[8];
};
void *rusix_locked_test_alloc(unsigned int mode, unsigned int scenario, bool irq);
void rusix_locked_test_free(void *data);
void rusix_locked_test_run(void *data);
u32 rusix_locked_test_members(void *data, struct task_struct *task);
u32 rusix_locked_test_checks(void *data);
u32 rusix_locked_test_wake(void *data, bool publish);
void rusix_locked_test_abort(void *data);
void rusix_locked_test_result(void *data, s64 *out);

/* Process-context watchdog is essential: a hardirq timer taking this lock could
 * interrupt an ordinary spin_lock holder on its CPU and deadlock. The timer only
 * queues work; this callback takes queue.lock after normal scheduling permits it.
 */
static void locked_watchdog(struct work_struct *work)
{
	struct locked_case *test = container_of(to_delayed_work(work), struct locked_case, watchdog);
	unsigned long flags;

	spin_lock_irqsave(&test->queue.lock, flags);
	test->expired = 1;
	test->abort = 1;
	__wake_up_locked(&test->queue, TASK_NORMAL, 0);
	spin_unlock_irqrestore(&test->queue.lock, flags);
}

void *rusix_locked_test_alloc(unsigned int mode, unsigned int scenario, bool irq)
{
	struct locked_case *test = kzalloc(sizeof(*test), GFP_KERNEL);

	if (!test)
		return NULL;
	init_waitqueue_head(&test->queue);
	INIT_DELAYED_WORK(&test->watchdog, locked_watchdog);
	test->mode = mode;
	test->scenario = scenario;
	test->irq = irq;
	return test;
}

/* Called only after callback Arc release; any armed work was synchronously
 * cancelled before acknowledgment. Unstarted contexts never arm their work.
 */
void rusix_locked_test_free(void *data)
{
	kfree(data);
}

static void locked_take(struct locked_case *test)
{
	if (test->irq)
		spin_lock_irq(&test->queue.lock);
	else
		spin_lock(&test->queue.lock);
}

static void locked_drop(struct locked_case *test)
{
	if (test->irq)
		spin_unlock_irq(&test->queue.lock);
	else
		spin_unlock(&test->queue.lock);
}

static bool locked_condition(struct locked_case *test)
{
	lockdep_assert_held(&test->queue.lock);
	test->checks++;
	if (test->mode == 1)
		return test->scenario == 0 || test->checks > 1;
	return test->abort || test->ready;
}

/* Pending-signal direct calls run only in dedicated task context. Record all
 * observations before original caller cleanup; restoration is not the oracle.
 */
static void locked_pending(struct locked_case *test, bool pending)
{
	DEFINE_WAIT(entry);
	long first, second;
	u32 detail = pending ? 1 : 0;

	entry.flags = WQ_FLAG_EXCLUSIVE | WQ_FLAG_PRIORITY | WQ_FLAG_CUSTOM;
	locked_take(test);
	__set_current_state(TASK_UNINTERRUPTIBLE);
	first = test->irq ? do_wait_intr_irq(&test->queue, &entry) : do_wait_intr(&test->queue, &entry);
	if (READ_ONCE(current->__state) == TASK_INTERRUPTIBLE)
		detail |= 2;
	__set_current_state(TASK_UNINTERRUPTIBLE);
	second = test->irq ? do_wait_intr_irq(&test->queue, &entry) : do_wait_intr(&test->queue, &entry);
	lockdep_assert_held(&test->queue.lock);
	test->result[0] = second;
	test->result[1] = READ_ONCE(current->__state) == TASK_INTERRUPTIBLE;
	test->result[2] = spin_is_locked(&test->queue.lock);
	test->result[3] = !!irqs_disabled() == test->irq;
	test->result[4] = test->queue.head.next == &entry.entry &&
		test->queue.head.prev == &entry.entry && entry.entry.next == &test->queue.head &&
		entry.entry.prev == &test->queue.head;
	if (first == -ERESTARTSYS)
		detail |= 4;
	if (entry.flags == (WQ_FLAG_EXCLUSIVE | WQ_FLAG_PRIORITY | WQ_FLAG_CUSTOM))
		detail |= 8;
	__remove_wait_queue(&test->queue, &entry);
	__set_current_state(TASK_RUNNING);
	if (entry.entry.next == LIST_POISON1 && entry.entry.prev == LIST_POISON2)
		detail |= 16;
	test->result[5] = detail;
	locked_drop(test);
}

void rusix_locked_test_run(void *data)
{
	struct locked_case *test = data;
	long result;
	bool pending = false;

	allow_signal(SIGUSR1);
	/* Per-callback Arc retains embedded work until cancel completes below.
	 * No intrinsic timeout exists in the production locked-wait APIs.
	 */
	if (!schedule_delayed_work(&test->watchdog, msecs_to_jiffies(10000))) {
		/* Fresh one-shot work must arm successfully; do not enter an untimed
		 * consumer if this invariant fails. Cancel outside all locks.
		 */
		cancel_delayed_work_sync(&test->watchdog);
		test->result[0] = -EBUSY;
		test->result[7] = 2;
		return;
	}
	if (test->mode <= 1) {
		pending = send_sig(SIGUSR1, current, 0) == 0 && signal_pending(current);
		if (!pending) {
			/* Do not enter untimed deterministic iterations with an invalid
			 * prerequisite; one watchdog cannot release two such sleeps.
			 */
			test->result[0] = -EIO;
			test->result[6] = -1;
			goto cancel;
		}
	}
	if (test->mode == 0) {
		locked_pending(test, pending);
	} else {
		locked_take(test);
		if (test->irq)
			result = wait_event_interruptible_locked_irq(test->queue, locked_condition(test));
		else
			result = wait_event_interruptible_locked(test->queue, locked_condition(test));
		lockdep_assert_held(&test->queue.lock);
		test->result[0] = result;
		test->result[1] = READ_ONCE(current->__state) == TASK_RUNNING;
		test->result[2] = spin_is_locked(&test->queue.lock);
		test->result[3] = !!irqs_disabled() == test->irq;
		test->result[4] = test->queue.head.next == &test->queue.head &&
			test->queue.head.prev == &test->queue.head;
		test->result[5] = test->checks;
		test->result[6] = test->mode == 1 ? pending : test->payload;
		locked_drop(test);
	}
cancel:
	/* Never wait for work while holding queue.lock: work acquires that lock. */
	cancel_delayed_work_sync(&test->watchdog);
	test->result[7] = test->expired;
	flush_signals(current);
	/* Rust acknowledges only after return; no C context access follows. */
}

u32 rusix_locked_test_members(void *data, struct task_struct *task)
{
	struct locked_case *test = data;
	struct list_head *node;
	unsigned long flags;
	u32 count = 0;

	spin_lock_irqsave(&test->queue.lock, flags);
	list_for_each(node, &test->queue.head) {
		wait_queue_entry_t *entry = list_entry(node, wait_queue_entry_t, entry);

		if (entry->private == task && entry->func == autoremove_wake_function)
			count++;
	}
	spin_unlock_irqrestore(&test->queue.lock, flags);
	return count;
}

u32 rusix_locked_test_checks(void *data)
{
	struct locked_case *test = data;
	unsigned long flags;
	u32 checks;

	spin_lock_irqsave(&test->queue.lock, flags);
	checks = test->checks;
	spin_unlock_irqrestore(&test->queue.lock, flags);
	return checks;
}

u32 rusix_locked_test_wake(void *data, bool publish)
{
	struct locked_case *test = data;
	unsigned long flags;
	u32 checks;

	spin_lock_irqsave(&test->queue.lock, flags);
	checks = test->checks;
	if (publish) {
		test->payload = 0x1234;
		test->ready = 1;
	}
	__wake_up_locked(&test->queue, TASK_INTERRUPTIBLE, 1);
	spin_unlock_irqrestore(&test->queue.lock, flags);
	return checks;
}

void rusix_locked_test_abort(void *data)
{
	struct locked_case *test = data;
	unsigned long flags;

	spin_lock_irqsave(&test->queue.lock, flags);
	test->abort = 1;
	__wake_up_locked(&test->queue, TASK_NORMAL, 0);
	spin_unlock_irqrestore(&test->queue.lock, flags);
}

/* Only after corresponding callback acknowledgment, including work cancellation. */
void rusix_locked_test_result(void *data, s64 *out)
{
	struct locked_case *test = data;

	memcpy(out, test->result, sizeof(test->result));
}
