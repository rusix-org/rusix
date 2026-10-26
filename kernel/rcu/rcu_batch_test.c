// SPDX-License-Identifier: GPL-2.0-only
/* Private differential operations and real consumers, never a second batch loop. */
#include <linux/atomic.h>
#include <linux/completion.h>
#include <linux/cpu.h>
#include <linux/delay.h>
#include <linux/err.h>
#include <linux/jiffies.h>
#include <linux/kthread.h>
#include <linux/rcupdate.h>
#include <linux/refcount.h>
#include <linux/sched/task.h>
#include <linux/slab.h>
#include "rcu_batch_test.h"

#define BATCH_NODES 129
#define BATCH_RESULTS 16
struct batch_fixture;
struct batch_slot {
	struct rcu_head head;
	struct batch_fixture *owner;
	atomic_t seen;
	u32 index;
	u32 payload;
};
struct batch_fixture {
	refcount_t refs;
	struct task_struct *worker, *reader;
	struct completion done, reader_entered, reader_done;
	atomic_t release_reader, reader_expired, callbacks, verified, violations;
	atomic_t private_accounts;
	struct batch_slot slots[BATCH_NODES];
	void *private_rdp;
	u32 mode;
	s64 result[BATCH_RESULTS];
};

void rusix_rcubatch_put(void *p)
{
	struct batch_fixture *f = p;
	int i;

	if (!refcount_dec_and_test(&f->refs))
		return;
	/* Every queued callback, the reader and worker retain a reference. Thus
	 * final release means no callback can still access these embedded heads.
	 */
	for (i = 0; i < BATCH_NODES; i++)
		destroy_rcu_head(&f->slots[i].head);
	if (f->reader)
		put_task_struct(f->reader);
	if (f->worker)
		put_task_struct(f->worker);
	kfree(f);
}

static void batch_callback(struct rcu_head *head)
{
	struct batch_slot *slot = container_of(head, struct batch_slot, head);
	struct batch_fixture *f = slot->owner;
	u32 index = slot->index;
	int seen = atomic_inc_return(&slot->seen);
	bool valid = READ_ONCE(slot->payload) == (0x5a00U + index) &&
		     !READ_ONCE(head->func);

	if (seen > (f->mode == 4 ? 2 : 1))
		valid = false;
	if (valid)
		atomic_inc(&f->verified);
	else
		atomic_inc(&f->violations);
	if (f->mode == 0) {
		/* FIFO and detached-count observation of a private synchronous batch. */
		if (atomic_read(&f->callbacks) != index)
			atomic_inc(&f->violations);
		if (rusix_rcubatch_private_accounting(f->private_rdp, 3))
			atomic_inc(&f->private_accounts);
	}
	atomic_inc(&f->callbacks);
	if (f->mode == 3) {
		/* No slot/head access after free, including from our caller. */
		destroy_rcu_head(head);
		kfree(slot);
	} else if (f->mode == 4 && seen == 1) {
		/* Transfer a new context reference before requeue. Another CPU may
		 * invoke it before this callback returns: no slot access follows.
		 */
		refcount_inc(&f->refs);
		call_rcu(head, batch_callback);
	}
	/* Private callbacks are synchronous and hold no independent submission
	 * reference; the retained worker owns their entire invocation interval.
	 */
	if (f->mode != 0)
		rusix_rcubatch_put(f);
}

static int batch_reader(void *p)
{
	struct batch_fixture *f = p;
	unsigned long deadline = jiffies + msecs_to_jiffies(3000);

	rcu_read_lock();
	complete(&f->reader_entered);
	while (!atomic_read_acquire(&f->release_reader)) {
		if (time_after_eq(jiffies, deadline)) {
			atomic_set(&f->reader_expired, 1);
			break;
		}
		cpu_relax();
	}
	rcu_read_unlock();
	complete(&f->reader_done);
	rusix_rcubatch_put(f);
	return 0;
}

static int start_reader(struct batch_fixture *f)
{
	struct task_struct *task;

	refcount_inc(&f->refs);
	task = kthread_create(batch_reader, f, "rusix-batch-reader");
	if (IS_ERR(task)) {
		rusix_rcubatch_put(f);
		return PTR_ERR(task);
	}
	get_task_struct(task);
	f->reader = task;
	kthread_bind(task, 0);
	wake_up_process(task);
	if (!wait_for_completion_timeout(&f->reader_entered, msecs_to_jiffies(1000)))
		return -ETIMEDOUT;
	return 0;
}

static void submit(struct batch_fixture *f, struct batch_slot *slot)
{
	/* call_rcu provides the established publication protocol. */
	refcount_inc(&f->refs);
	call_rcu(&slot->head, batch_callback);
}

static int batch_worker(void *p)
{
	struct batch_fixture *f = p;
	struct rcu_head *heads[3];
	struct batch_slot *allocated = NULL;
	bool retained = false;
	int i, nr = 1, error = 0;

	cpus_read_lock();
	if (!cpu_online(0) || !cpu_online(1)) {
		error = -ENODEV;
		goto publish;
	}
	if (f->mode == 0) {
		error = rusix_rcubatch_private(heads, 0, &f->private_rdp,
						 &retained, f->result + 4);
		if (error)
			goto publish;
		for (i = 0; i < 3; i++) {
			heads[i] = &f->slots[i].head;
			heads[i]->func = batch_callback;
		}
		error = rusix_rcubatch_private(heads, 3, &f->private_rdp,
						 &retained, f->result + 8);
		f->result[12] = atomic_read(&f->private_accounts);
		goto publish;
	}
	if (f->mode == 1) {
		rusix_rcubatch_time_samples(f->result + 4);
		goto publish;
	}
	if (f->mode == 2) {
		error = start_reader(f);
		if (error)
			goto release;
	}
	if (f->mode == 3) {
		allocated = kzalloc(sizeof(*allocated), GFP_KERNEL);
		if (!allocated) {
			error = -ENOMEM;
			goto release;
		}
		allocated->owner = f;
		allocated->payload = 0x5a00;
		atomic_set(&allocated->seen, 0);
		init_rcu_head(&allocated->head);
		submit(f, allocated);
		/* Ownership transferred: never inspect this pointer again. */
		allocated = NULL;
	} else {
		if (f->mode == 5)
			nr = BATCH_NODES;
		for (i = 0; i < nr; i++)
			submit(f, &f->slots[i]);
	}
	if (f->mode == 2) {
		/* CPU1 drives release; CPU0 never sleeps while holding the reader.
		 * A timeout cannot masquerade as a successful held-reader observation.
		 */
		msleep(50);
		f->result[13] = !atomic_read(&f->callbacks) &&
				 !atomic_read(&f->reader_expired) &&
				 !completion_done(&f->reader_done);
	}
release:
	atomic_set_release(&f->release_reader, 1);
	if (f->reader && !wait_for_completion_timeout(&f->reader_done,
						     msecs_to_jiffies(4000))) {
		error = -ETIMEDOUT;
		retained = true;
	}
	if (atomic_read(&f->reader_expired))
		error = -ETIMEDOUT;
	/* Only this retained process worker can block in barriers. Two calls
	 * also cover the callback requeued before the original callback returns.
	 * A broken implementation leaves references alive until VM containment.
	 */
	rcu_barrier();
	rcu_barrier();
	if (f->mode == 4)
		f->result[14] = atomic_read(&f->slots[0].seen);
	if (f->mode != 3) {
		for (i = 0; i < nr; i++) {
			if (READ_ONCE(f->slots[i].head.func)) {
				error = -EIO;
				retained = true;
			}
		}
	}
publish:
	cpus_read_unlock();
	f->result[0] = error;
	f->result[1] = atomic_read(&f->callbacks);
	f->result[2] = atomic_read(&f->verified);
	f->result[3] = atomic_read(&f->violations);
	complete_all(&f->done);
	if (!retained)
		rusix_rcubatch_put(f);
	return 0;
}

void *rusix_rcubatch_start(u32 mode)
{
	struct batch_fixture *f;
	struct task_struct *task;
	int i;

	if (mode > 5 || nr_cpu_ids < 2)
		return ERR_PTR(-EINVAL);
	f = kzalloc(sizeof(*f), GFP_KERNEL);
	if (!f)
		return ERR_PTR(-ENOMEM);
	refcount_set(&f->refs, 2); /* Controller plus worker, before publication. */
	init_completion(&f->done);
	init_completion(&f->reader_entered);
	init_completion(&f->reader_done);
	f->mode = mode;
	for (i = 0; i < BATCH_NODES; i++) {
		f->slots[i].owner = f;
		f->slots[i].index = i;
		f->slots[i].payload = 0x5a00U + i;
		atomic_set(&f->slots[i].seen, 0);
		init_rcu_head(&f->slots[i].head);
	}
	cpus_read_lock();
	if (!cpu_online(0) || !cpu_online(1)) {
		cpus_read_unlock();
		rusix_rcubatch_put(f);
		rusix_rcubatch_put(f);
		return ERR_PTR(-ENODEV);
	}
	task = kthread_create(batch_worker, f, "rusix-batch-worker");
	if (IS_ERR(task)) {
		int error = PTR_ERR(task);

		cpus_read_unlock();
		rusix_rcubatch_put(f);
		rusix_rcubatch_put(f);
		return ERR_PTR(error);
	}
	get_task_struct(task);
	f->worker = task;
	kthread_bind(task, 1);
	wake_up_process(task);
	cpus_read_unlock();
	return f;
}

bool rusix_rcubatch_wait(void *p, u32 ms)
{
	struct batch_fixture *f = p;

	return wait_for_completion_timeout(&f->done, msecs_to_jiffies(ms)) != 0;
}

void rusix_rcubatch_result(void *p, s64 *out)
{
	struct batch_fixture *f = p;

	/* Caller must observe this worker's done completion first. */
	memcpy(out, f->result, sizeof(f->result));
}
