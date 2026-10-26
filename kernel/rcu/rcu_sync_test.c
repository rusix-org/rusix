// SPDX-License-Identifier: GPL-2.0-only
/* Real protocol workers plus a separately labelled synthetic callback oracle.
 * No blocking RCU teardown executes on the KUnit controller. Each task retains
 * storage through its last access; incomplete teardown deliberately retains it.
 */
#include <linux/completion.h>
#include <linux/cpu.h>
#include <linux/delay.h>
#include <linux/kthread.h>
#include <linux/percpu-rwsem.h>
#include <linux/rcu_sync.h>
#include <linux/refcount.h>
#include <linux/sched/task.h>
#include <linux/slab.h>

struct sync_fixture;
struct sync_slot {
	struct sync_fixture *f;
	struct task_struct *task;
	struct completion done;
	bool reader;
};
struct sync_fixture {
	refcount_t refs;
	struct task_struct *task;
	struct sync_slot slots[3];
	struct completion done, leave;
	atomic_t reader_ready, reader_release, reader_expired, entered, observed_payload;
	struct rcu_sync sync, scratch;
	struct percpu_rw_semaphore sem;
	unsigned int mode;
	int payload;
	s64 result[16];
};
void *rusix_rcusync_start(u32 mode);
bool rusix_rcusync_wait(void *p, u32 ms);
void rusix_rcusync_result(void *p, s64 *out);
void rusix_rcusync_put(void *p);
void rusix_rcusync_release(void *p);

void rusix_rcusync_put(void *p)
{
	struct sync_fixture *f = p;
	int i;
	if (!refcount_dec_and_test(&f->refs))
		return;
	for (i = 0; i < 3; i++)
		if (f->slots[i].task)
			put_task_struct(f->slots[i].task);
	if (f->task)
		put_task_struct(f->task);
	kfree(f);
}
void rusix_rcusync_release(void *p)
{
	struct sync_fixture *f = p;
	atomic_set_release(&f->reader_release, 1);
	complete_all(&f->leave);
}
static void snapshot(struct rcu_sync *s, s64 *out)
{
	unsigned long flags;
	spin_lock_irqsave(&s->gp_wait.lock, flags);
	out[0] = s->gp_state;
	out[1] = s->gp_count;
	spin_unlock_irqrestore(&s->gp_wait.lock, flags);
}
static bool poll_value(atomic_t *value, int wanted)
{
	unsigned long end = jiffies + msecs_to_jiffies(1000);
	do {
		if (atomic_read_acquire(value) == wanted)
			return true;
		usleep_range(1000, 2000);
	} while (time_before(jiffies, end));
	return false;
}
static int participant(void *p)
{
	struct sync_slot *slot = p;
	struct sync_fixture *f = slot->f;
	unsigned long end;
	if (slot->reader) {
		if (f->mode == 4)
			percpu_down_read(&f->sem);
		else
			rcu_read_lock();
		end = jiffies + msecs_to_jiffies(3000);
		atomic_set_release(&f->reader_ready, 1);
		/* CPU0 never sleeps inside ordinary RCU. CPU1 drives all controls,
		 * even if the KUnit controller cannot run during this hold. */
		while (!atomic_read_acquire(&f->reader_release)) {
			if (time_after_eq(jiffies, end)) {
				atomic_set(&f->reader_expired, 1);
				break;
			}
			if (f->mode == 4)
				usleep_range(1000, 2000);
			else
				cpu_relax();
		}
		if (f->mode == 4) {
			WRITE_ONCE(f->payload, 0x1234);
			percpu_up_read(&f->sem);
		} else {
			rcu_read_unlock();
		}
	} else {
		if (f->mode == 4)
			percpu_down_write(&f->sem);
		else
			rcu_sync_enter(&f->sync);
		if (f->mode == 4)
			atomic_set(&f->observed_payload, READ_ONCE(f->payload));
		atomic_inc_return(&f->entered);
		wait_for_completion_timeout(&f->leave, msecs_to_jiffies(5000));
		if (f->mode == 4)
			percpu_up_write(&f->sem);
		else
			rcu_sync_exit(&f->sync);
	}
	complete_all(&slot->done);
	rusix_rcusync_put(f);
	return 0;
}
static int start_slot(struct sync_fixture *f, int i, bool reader)
{
	struct sync_slot *s = &f->slots[i];
	struct task_struct *task;
	s->reader = reader;
	task = kthread_create(participant, s, "rusix_sync_%d", i);
	if (IS_ERR(task))
		return PTR_ERR(task);
	s->task = task;
	get_task_struct(task);
	refcount_inc(&f->refs);
	kthread_bind(task, reader ? 0 : 1);
	wake_up_process(task);
	return 0;
}
static bool joined(struct sync_fixture *f)
{
	int i;
	unsigned long deadline = jiffies + msecs_to_jiffies(6000);
	for (i = 0; i < 3; i++) {
		long left = (long)(deadline - jiffies);
		if (f->slots[i].task && (left <= 0 ||
		    !wait_for_completion_timeout(&f->slots[i].done, left)))
			return false;
	}
	return true;
}
static bool wait_enrolled(struct sync_fixture *f)
{
	unsigned long end = jiffies + msecs_to_jiffies(1000), flags;
	bool present;
	do {
		spin_lock_irqsave(&f->sync.gp_wait.lock, flags);
		present = !list_empty(&f->sync.gp_wait.head) &&
			f->sync.gp_state == 1 && f->sync.gp_count == 2;
		spin_unlock_irqrestore(&f->sync.gp_wait.lock, flags);
		if (present)
			return true;
		usleep_range(1000, 2000);
	} while (time_before(jiffies, end));
	return false;
}
static int orchestrator(void *p)
{
	struct sync_fixture *f = p;
	void (*callback)(struct rcu_head *);
	int error = 0;
	bool entered = false, sem = false, scratch = false, unsafe_teardown = false;
	s64 observed[2];
	unsigned long flags;

	memset(&f->sync, 0xa5, sizeof(f->sync));
	rcu_sync_init(&f->sync);
	cpus_read_lock();
	if (!cpu_online(0) || !cpu_online(1)) {
		error = -ENODEV;
		goto cleanup;
	}
	snapshot(&f->sync, &f->result[1]);
	f->result[3] = f->sync.gp_wait.head.next == &f->sync.gp_wait.head &&
		f->sync.gp_wait.head.prev == &f->sync.gp_wait.head;
	if (f->mode == 0) {
		f->result[10] = !irqs_disabled();
		f->result[11] = !f->sync.cb_head.next && !f->sync.cb_head.func;
		rcu_sync_enter(&f->sync);
		entered = true;
		snapshot(&f->sync, &f->result[4]);
		rcu_sync_enter(&f->sync);
		snapshot(&f->sync, &f->result[6]);
		rcu_sync_exit(&f->sync);
		snapshot(&f->sync, &f->result[8]);
		goto cleanup;
	}
	if (f->mode == 4) {
		error = percpu_init_rwsem(&f->sem);
		if (error)
			goto cleanup;
		sem = true;
	} else if (f->mode != 1) {
		rcu_sync_enter(&f->sync);
		entered = true;
	}
	error = start_slot(f, 0, true);
	if (error)
		goto cleanup;
	if (!poll_value(&f->reader_ready, 1)) {
		error = -ETIMEDOUT;
		goto cleanup;
	}
	if (f->mode == 1 || f->mode == 4) {
		error = start_slot(f, 1, false);
		if (error)
			goto cleanup;
		if (f->mode == 1) {
			/* First entrant is held in synchronize_rcu;
			second must enroll. */
			unsigned long end = jiffies + msecs_to_jiffies(1000);
			do {
				snapshot(&f->sync, &f->result[4]);
				if (f->result[4] == 1 && f->result[5] == 1)
					break;
				usleep_range(1000, 2000);
			} while (time_before(jiffies, end));
			error = start_slot(f, 2, false);
			if (error)
				goto cleanup;
			f->result[6] = wait_enrolled(f);
		} else {
			/* Wait for the real writer to set block before sampling exclusion. */
			f->result[6] = poll_value(&f->sem.block, 1);
		}
		f->result[7] = atomic_read(&f->entered);
		atomic_set_release(&f->reader_release, 1);
		f->result[8] = poll_value(&f->entered, f->mode == 1 ? 2 : 1);
		f->result[9] = atomic_read(&f->entered);
	} else {
		rcu_sync_exit(&f->sync);
		entered = false;
		snapshot(&f->sync, &f->result[4]);
		if (f->mode == 2) {
			rcu_sync_enter(&f->sync);
			entered = true;
			snapshot(&f->sync, &f->result[6]);
			rcu_sync_exit(&f->sync);
			entered = false;
			snapshot(&f->sync, &f->result[8]);
		} else {
			/* Submission returned and CPU0's reader stalls the original.
			 * Never invoke a callback on a queued head. This scratch object
			 * is distinct and has never been submitted to RCU. */
			callback = READ_ONCE(f->sync.cb_head.func);
			if (!callback || atomic_read(&f->reader_expired)) {
				error = -EIO;
				goto cleanup;
			}
			rcu_sync_init(&f->scratch);
			scratch = true;
			f->scratch.gp_state = 1;
			f->scratch.gp_count = 1;
			callback(&f->scratch.cb_head);
			snapshot(&f->scratch, &f->result[6]);
			f->scratch.gp_state = 3;
			f->scratch.gp_count = 0;
			callback(&f->scratch.cb_head);
			snapshot(&f->scratch, &f->result[8]);
			f->scratch.gp_state = 4;
			/* This invocation queues it once. */
			callback(&f->scratch.cb_head);
			snapshot(&f->scratch, &f->result[10]);
		}
	}
cleanup:
	rusix_rcusync_release(f);
	if (entered)
		rcu_sync_exit(&f->sync);
	if (!joined(f)) {
		f->result[0] = -ETIMEDOUT;
		cpus_read_unlock();
		complete_all(&f->done);
		/* Retain orchestrator ref and all potentially live storage. */
		return 0;
	}
	if (f->mode == 4)
		f->result[10] = atomic_read(&f->observed_payload);
	if (f->mode == 2) {
		/* Let the actual REPLAY callback run, then its requeued successor,
		 * before dtor can fold REPLAY. These barriers run only here. */
		rcu_barrier();
		rcu_barrier();
		snapshot(&f->sync, &f->result[10]);
	}
	if (scratch) {
		rcu_sync_dtor(&f->scratch);
		snapshot(&f->scratch, observed);
		unsafe_teardown = observed[0] || observed[1] ||
			READ_ONCE(f->scratch.cb_head.func);
		if (unsafe_teardown)
			error = -EIO;
	}
	if (sem) {
		rcu_sync_dtor(&f->sem.rss);
		snapshot(&f->sem.rss, observed);
		unsafe_teardown = observed[0] || observed[1] ||
			READ_ONCE(f->sem.rss.cb_head.func);
		/* Independent callback drain before freeing the real consumer. */
		rcu_barrier();
		rcu_barrier();
		if (unsafe_teardown || READ_ONCE(f->sem.rss.gp_state) ||
		    READ_ONCE(f->sem.rss.gp_count) || READ_ONCE(f->sem.rss.cb_head.func) ||
		    !list_empty(&f->sem.waiters.head) || rcuwait_active(&f->sem.writer)) {
			f->result[0] = -EIO;
			cpus_read_unlock();
			complete_all(&f->done);
			/* Preserve counts and embedded callback after bad teardown. */
			return 0;
		}
		percpu_free_rwsem(&f->sem);
	}
	rcu_sync_dtor(&f->sync);
	snapshot(&f->sync, &f->result[12]);
	if (READ_ONCE(f->sync.cb_head.func)) {
		unsafe_teardown = true;
		error = -EIO;
	}
	/* Preserve the candidate dtor observation, then independently drain both
	 * the original callback and a possible single replay generation. */
	rcu_barrier();
	rcu_barrier();
	f->result[14] = atomic_read(&f->reader_expired);
	/* State is observed under its lock, even on a failing implementation. */
	spin_lock_irqsave(&f->sync.gp_wait.lock, flags);
	f->result[15] = list_empty(&f->sync.gp_wait.head);
	spin_unlock_irqrestore(&f->sync.gp_wait.lock, flags);
	unsafe_teardown = unsafe_teardown || f->result[12] || f->result[13] ||
		!f->result[15] || READ_ONCE(f->sync.gp_state) ||
		READ_ONCE(f->sync.gp_count) || READ_ONCE(f->sync.cb_head.func) ||
		(scratch && (READ_ONCE(f->scratch.gp_state) ||
			     READ_ONCE(f->scratch.gp_count) ||
			     READ_ONCE(f->scratch.cb_head.func)));
	f->result[0] = unsafe_teardown ? -EIO : error;
	cpus_read_unlock();
	complete_all(&f->done);
	/* A failing refusal to free is visible before publication. */
	if (unsafe_teardown)
		return 0;
	rusix_rcusync_put(f);
	return 0;
}
void *rusix_rcusync_start(u32 mode)
{
	struct sync_fixture *f;
	int i, error;
	if (mode > 4)
		return ERR_PTR(-EINVAL);
	if (!cpu_online(0) || !cpu_online(1))
		return ERR_PTR(-ENODEV);
	f = kzalloc(sizeof(*f), GFP_KERNEL);
	if (!f)
		return ERR_PTR(-ENOMEM);
	refcount_set(&f->refs, 2);
	f->mode = mode;
	init_completion(&f->done);
	init_completion(&f->leave);
	for (i = 0; i < 3; i++) {
		f->slots[i].f = f;
		init_completion(&f->slots[i].done);
	}
	f->task = kthread_create(orchestrator, f, "rusix_rcusync");
	if (IS_ERR(f->task)) {
		error = PTR_ERR(f->task);
		kfree(f);
		return ERR_PTR(error);
	}
	get_task_struct(f->task);
	kthread_bind(f->task, 1);
	wake_up_process(f->task);
	return f;
}
bool rusix_rcusync_wait(void *p, u32 ms)
{
	return wait_for_completion_timeout(&((struct sync_fixture *)p)->done,
					  msecs_to_jiffies(ms)) != 0;
}
void rusix_rcusync_result(void *p, s64 *out)
{
	memcpy(out, ((struct sync_fixture *)p)->result, 16 * sizeof(*out));
}
