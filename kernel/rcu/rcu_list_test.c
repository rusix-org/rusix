// SPDX-License-Identifier: GPL-2.0-only
/* Independent test operations and logical observations, never duplicate policy. */
#include <linux/cpu.h>
#include <linux/jiffies.h>
#include <linux/smp.h>
#include <linux/sched/task.h>
#include <linux/err.h>
#include <linux/slab.h>
#include "rcu_segcblist.h"

#define TEST_NODES 16
struct list_fixture {
	struct rcu_segcblist seg[2];
	struct rcu_cblist simple[2];
	struct rcu_head nodes[TEST_NODES];
};
void *rusix_rculist_alloc(void);
void rusix_rculist_free(void *p);
s64 rusix_rculist_action(void *p, u32 op, u32 dst, u32 src, u32 node, u64 value);
void rusix_rculist_snapshot(void *p, u32 which, s64 *out);
void rusix_rculist_simple(void *p, u32 which, s64 *out);

/* Identity checks precede every observer dereference, with bounded traversal. */
static int node_id(struct list_fixture *f, struct rcu_head *node)
{
	int i;
	if (!node)
		return 0;
	for (i = 0; i < TEST_NODES; i++)
		if (node == &f->nodes[i])
			return i + 1;
	return -1;
}
static int tail_id(struct list_fixture *f, struct rcu_head **head, struct rcu_head **tail)
{
	int i;
	if (tail == head)
		return 0;
	for (i = 0; i < TEST_NODES; i++)
		if (tail == &f->nodes[i].next)
			return i + 1;
	return -1;
}
static int chain(struct list_fixture *f, struct rcu_head *node, s64 *out)
{
	unsigned int seen = 0;
	int i, id;
	for (i = 0; node && i < TEST_NODES; i++) {
		id = node_id(f, node);
		if (id <= 0 || (seen & BIT(id - 1)))
			return -1;
		seen |= BIT(id - 1);
		out[i] = id;
		node = node->next;
	}
	return node ? -1 : i;
}
void *rusix_rculist_alloc(void)
{
	struct list_fixture *f = kzalloc(sizeof(*f), GFP_KERNEL);
	int i;
	if (!f)
		return ERR_PTR(-ENOMEM);
	for (i = 0; i < 2; i++) {
		rcu_segcblist_init(&f->seg[i]);
		rcu_cblist_init(&f->simple[i]);
	}
	return f;
}
void rusix_rculist_free(void *p)
{
	/* Private synthetic chains were never submitted to any global RCU queue. */
	kfree(p);
}
/* All descriptors remain at their allocation address. dst/src identify arrays;
 * node is a one-based pool ID (zero means NULL only for flush). */
s64 rusix_rculist_action(void *p, u32 op, u32 dst, u32 src, u32 node, u64 value)
{
	struct list_fixture *f = p;
	struct rcu_head *head;
	struct rcu_segcblist *s;
	unsigned long gp;
	int i;
	if (dst >= 2 || src >= 2 || node > TEST_NODES)
		return -EINVAL;
	head = node ? &f->nodes[node - 1] : NULL;
	s = &f->seg[dst];
	switch (op) {
	case 0:
		s->flags = value;
		for (i = 0; i < RCU_CBLIST_NSEGS; i++)
			s->gp_seq[i] = 0x100 + i;
		rcu_segcblist_init(s);
		for (i = 0; i < RCU_CBLIST_NSEGS; i++)
			if (s->gp_seq[i] != 0x100 + i)
				return -EIO;
		return s->flags;
	case 1: rcu_segcblist_disable(s); break;
	case 2: if (!head) return -EINVAL; rcu_segcblist_enqueue(s, head); break;
	case 3: if (!head) return -EINVAL; return rcu_segcblist_entrain(s, head);
	case 4: return rcu_segcblist_accelerate(s, value);
	case 5: rcu_segcblist_advance(s, value); break;
	case 6: rcu_segcblist_add_len(s, (long)value); break;
	case 7: rcu_segcblist_inc_len(s); break;
	case 8: rcu_segcblist_extract_done_cbs(s, &f->simple[src]); break;
	case 9: rcu_segcblist_extract_pend_cbs(s, &f->simple[src]); break;
	case 10: rcu_segcblist_insert_count(s, &f->simple[src]); break;
	case 11: rcu_segcblist_insert_done_cbs(s, &f->simple[src]); break;
	case 12: rcu_segcblist_insert_pend_cbs(s, &f->simple[src]); break;
	case 13:
		if (dst == src) return -EINVAL;
		cpus_read_lock();
		rcu_segcblist_merge(s, &f->seg[src]);
		cpus_read_unlock();
		break;
	case 14: rcu_cblist_init(&f->simple[dst]); break;
	case 15: if (!head) return -EINVAL; rcu_cblist_enqueue(&f->simple[dst], head); break;
	case 16: return node_id(f, rcu_cblist_dequeue(&f->simple[dst]));
	case 17:
		if (dst == src) return -EINVAL;
		rcu_cblist_flush_enqueue(&f->simple[dst], &f->simple[src], head);
		break;
	case 18:
		gp = value;
		if (rcu_segcblist_nextgp(s, &gp))
			return gp;
		return gp == value ? -ENOENT : -EIO;
	default: return -EINVAL;
	}
	return 0;
}
void rusix_rculist_snapshot(void *p, u32 which, s64 *out)
{
	struct list_fixture *f = p;
	struct rcu_segcblist *s = &f->seg[which];
	int i;
	memset(out, 0, 34 * sizeof(*out));
	out[0] = rcu_segcblist_n_cbs(s);
	out[1] = rcu_segcblist_n_segment_cbs(s);
	out[2] = s->flags;
	out[3] = rcu_segcblist_ready_cbs(s);
	out[4] = tail_id(f, &s->head, s->tails[RCU_DONE_TAIL]) < 0 ? -1 :
		rcu_segcblist_pend_cbs(s);
	out[5] = node_id(f, rcu_segcblist_first_cb(s));
	/* Validate the tail identity before calling the query which dereferences it. */
	out[6] = tail_id(f, &s->head, s->tails[RCU_DONE_TAIL]) < 0 ? -1 :
		node_id(f, rcu_segcblist_first_pend_cb(s));
	for (i = 0; i < 4; i++) {
		out[7 + i] = tail_id(f, &s->head, s->tails[i]);
		out[11 + i] = rcu_segcblist_get_seglen(s, i);
	}
	/* Only meaningful nonempty WAIT/NEXT_READY GP slots are observed. */
	if (out[12]) out[15] = s->gp_seq[RCU_WAIT_TAIL];
	if (out[13]) out[16] = s->gp_seq[RCU_NEXT_READY_TAIL];
	out[33] = chain(f, s->head, out + 17);
}
void rusix_rculist_simple(void *p, u32 which, s64 *out)
{
	struct list_fixture *f = p;
	struct rcu_cblist *s = &f->simple[which];
	memset(out, 0, 19 * sizeof(*out));
	out[0] = s->len;
	out[1] = tail_id(f, &s->head, s->tail);
	out[18] = chain(f, s->head, out + 2);
}

/* Real consumers. Every queued callback and worker owns a context reference.
 * Controller timeouts drop only their own reference; outstanding callbacks and
 * blocking barriers retain storage. A stuck RCU implementation needs VM timeout.
 */
#include <linux/completion.h>
#include <linux/kthread.h>
#include <linux/refcount.h>
#include <linux/srcu.h>
#include <linux/delay.h>

struct runtime_fixture;
struct runtime_slot {
	struct rcu_head head;
	struct runtime_fixture *owner;
	u32 index, payload;
};
struct runtime_fixture {
	refcount_t refs;
	struct task_struct *task;
	struct completion done, release;
	struct srcu_struct srcu;
	struct runtime_slot slots[2];
	atomic_t callbacks, payload_mask, phase;
	u32 mode;
	s64 result[5];
};
void *rusix_rculist_runtime_start(u32 mode);
u32 rusix_rculist_runtime_phase(void *p);
u32 rusix_rculist_runtime_count(void *p);
void rusix_rculist_runtime_release(void *p);
bool rusix_rculist_runtime_wait(void *p, u32 ms);
void rusix_rculist_runtime_result(void *p, s64 *out);
void rusix_rculist_runtime_put(void *p);

void rusix_rculist_runtime_put(void *p)
{
	struct runtime_fixture *f = p;
	if (refcount_dec_and_test(&f->refs)) {
		/* SRCU cleanup completed in process context before worker publication. */
		if (f->task)
			put_task_struct(f->task);
		kfree(f);
	}
}
static void runtime_callback(struct rcu_head *head)
{
	struct runtime_slot *slot = container_of(head, struct runtime_slot, head);
	struct runtime_fixture *f = slot->owner;
	if (READ_ONCE(slot->payload) == 0x1200 + slot->index)
		atomic_or(BIT(slot->index), &f->payload_mask);
	atomic_inc(&f->callbacks);
	rusix_rculist_runtime_put(f); /* Final access; caller may drop its last ref. */
}
static void submit_on_cpu(void *data)
{
	struct runtime_slot *slot = data;
	/* The worker retains its own ref before incrementing the callback ref. */
	refcount_inc(&slot->owner->refs);
	call_rcu(&slot->head, runtime_callback);
}
static int runtime_worker(void *data)
{
	struct runtime_fixture *f = data;
	int cpu, submitted = 0, status = 0, idx;
	unsigned int cpus = 0;
	if (!f->mode) {
		cpus_read_lock();
		for_each_online_cpu(cpu) {
			if (submitted == 2)
				break;
			if (cpu >= 32) { status = -ERANGE; break; }
			status = smp_call_function_single(cpu, submit_on_cpu,
						 &f->slots[submitted], 1);
			if (status)
				break;
			cpus |= BIT(cpu); /* Declared q35 SMP2 uses CPU0 and CPU1. */
			submitted++;
		}
		cpus_read_unlock();
		rcu_barrier(); /* Intentionally outside the bounded controller. */
	} else {
		idx = srcu_read_lock(&f->srcu);
		refcount_inc(&f->refs);
		call_srcu(&f->srcu, &f->slots[0].head, runtime_callback);
		submitted = 1;
		/* Release publication means the read-side hold and enqueue are real. */
		atomic_set_release(&f->phase, 1);
		if (!wait_for_completion_timeout(&f->release, msecs_to_jiffies(5000)))
			status = -ETIMEDOUT;
		srcu_read_unlock(&f->srcu, idx);
		srcu_barrier(&f->srcu);
	}
	f->result[0] = status;
	f->result[1] = atomic_read(&f->callbacks);
	f->result[2] = atomic_read(&f->payload_mask);
	f->result[3] = submitted;
	f->result[4] = cpus;
	/* A broken barrier returning before callback completion cannot permit SRCU
	 * destruction. Retain worker/context forever on that failing path. */
	if (f->mode && f->result[1] != submitted) {
		f->result[0] = -EIO;
		complete_all(&f->done);
		return 0;
	}
	if (f->mode) {
		cleanup_srcu_struct(&f->srcu);
		/* TREE_SRCU's void cleanup can warn and refuse teardown. Dynamic
		 * success clears srcu_sup; keep all storage if it still owns work. */
		if (READ_ONCE(f->srcu.srcu_sup)) {
			f->result[0] = -EIO;
			complete_all(&f->done);
			return 0; /* Retain worker ref, as for an incomplete barrier. */
		}
	}
	complete_all(&f->done);
	rusix_rculist_runtime_put(f);
	return 0;
}
void *rusix_rculist_runtime_start(u32 mode)
{
	struct runtime_fixture *f;
	int i, error;
	if (mode > 1)
		return ERR_PTR(-EINVAL);
	f = kzalloc(sizeof(*f), GFP_KERNEL);
	if (!f)
		return ERR_PTR(-ENOMEM);
	f->mode = mode;
	init_completion(&f->done);
	init_completion(&f->release);
	refcount_set(&f->refs, 2); /* Controller plus stopped worker. */
	for (i = 0; i < 2; i++) {
		f->slots[i].owner = f;
		f->slots[i].index = i;
		f->slots[i].payload = 0x1200 + i;
	}
	if (mode) {
		error = init_srcu_struct(&f->srcu);
		if (error) { kfree(f); return ERR_PTR(error); }
	}
	f->task = kthread_create(runtime_worker, f, "rusix_rculist");
	if (IS_ERR(f->task)) {
		error = PTR_ERR(f->task);
		if (mode) {
			cleanup_srcu_struct(&f->srcu);
			if (READ_ONCE(f->srcu.srcu_sup))
				return ERR_PTR(error); /* Retain failed live SRCU teardown. */
		}
		kfree(f);
		return ERR_PTR(error);
	}
	get_task_struct(f->task);
	wake_up_process(f->task);
	return f;
}
u32 rusix_rculist_runtime_phase(void *p)
{
	return atomic_read_acquire(&((struct runtime_fixture *)p)->phase);
}
u32 rusix_rculist_runtime_count(void *p)
{
	return atomic_read(&((struct runtime_fixture *)p)->callbacks);
}
void rusix_rculist_runtime_release(void *p)
{
	complete_all(&((struct runtime_fixture *)p)->release);
}
bool rusix_rculist_runtime_wait(void *p, u32 ms)
{
	return wait_for_completion_timeout(&((struct runtime_fixture *)p)->done,
					  msecs_to_jiffies(ms)) != 0;
}
void rusix_rculist_runtime_result(void *p, s64 *out)
{
	/* Exact worker completion observed by controller before these plain reads. */
	struct runtime_fixture *f = p;
	int i;
	for (i = 0; i < 5; i++) out[i] = f->result[i];
}
