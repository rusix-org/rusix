/* SPDX-License-Identifier: GPL-2.0-only */
/* Include only from tree.c, where private fields, parameters and trace/lockdep
 * maps retain their canonical scope. These are primitive boundaries, not a C
 * implementation of extraction, callback dispatch, time policy or commit. */
#ifndef RUSIX_RCU_BATCH_FFI_IMPL_H
#define RUSIX_RCU_BATCH_FFI_IMPL_H
#include <linux/rusix_rcu_batch.h>

static_assert(sizeof(long) == 8);
static_assert(RUSIX_RCU_BATCH_KTHREAD_RUNNING == RCU_KTHREAD_RUNNING);
static_assert(RUSIX_RCU_BATCH_MAX_BLIMIT == DEFAULT_MAX_RCU_BLIMIT);
static_assert(RUSIX_RCU_BATCH_NSEC_PER_MSEC == NSEC_PER_MSEC);
static_assert(RUSIX_RCU_BATCH_NSEC_PER_SEC == NSEC_PER_SEC);
static_assert(RUSIX_RCU_BATCH_HZ > 0 && RUSIX_RCU_BATCH_HZ <= NSEC_PER_SEC);
static_assert(!IS_ENABLED(CONFIG_RCU_NOCB_CPU));
static_assert(!IS_ENABLED(CONFIG_RCU_BOOST));
static_assert(!IS_ENABLED(CONFIG_PREEMPT_RT));

struct rcu_segcblist *rusix_rcubatch_cblist(void *opaque)
{
	struct rcu_data *rdp = opaque;
	return &rdp->cblist;
}
long rusix_rcubatch_n_cbs(struct rcu_segcblist *list)
{
	return rcu_segcblist_n_cbs(list);
}
bool rusix_rcubatch_empty(struct rcu_segcblist *list)
{
	return rcu_segcblist_empty(list);
}
bool rusix_rcubatch_local_nonempty(struct rcu_cblist *list)
{
	return !!list->head;
}
/* Plain accesses match tree.c, including existing C observers. */
long rusix_rcubatch_blimit(void *opaque) { return ((struct rcu_data *)opaque)->blimit; }
void rusix_rcubatch_set_blimit(void *opaque, long v) { ((struct rcu_data *)opaque)->blimit = v; }
long rusix_rcubatch_qlen(void *opaque) { return ((struct rcu_data *)opaque)->qlen_last_fqs_check; }
void rusix_rcubatch_set_qlen(void *opaque, long v) { ((struct rcu_data *)opaque)->qlen_last_fqs_check = v; }
unsigned long rusix_rcubatch_invoked(void *opaque) { return ((struct rcu_data *)opaque)->n_cbs_invoked; }
void rusix_rcubatch_set_invoked(void *opaque, unsigned long v) { ((struct rcu_data *)opaque)->n_cbs_invoked = v; }
void rusix_rcubatch_set_force_snap(void *opaque, unsigned long v) { ((struct rcu_data *)opaque)->n_force_qs_snap = v; }
unsigned int rusix_rcubatch_status(void *opaque) { return ((struct rcu_data *)opaque)->rcu_cpu_kthread_status; }
void rusix_rcubatch_set_work(void *opaque, char v) { ((struct rcu_data *)opaque)->rcu_cpu_has_work = v; }
int rusix_rcubatch_divisor(void) { return READ_ONCE(rcu_divisor); }
long rusix_rcubatch_resched_ns(void) { return READ_ONCE(rcu_resched_ns); }
long rusix_rcubatch_global_blimit(void) { return blimit; }
long rusix_rcubatch_qlowmark(void) { return qlowmark; }
long rusix_rcubatch_qhimark(void) { return qhimark; }
unsigned long rusix_rcubatch_force_qs(void) { return READ_ONCE(rcu_state.n_force_qs); }
unsigned long rusix_rcubatch_irq_save(void *opaque)
{
	struct rcu_data *rdp = opaque;
	unsigned long flags;

	(void)rdp; /* !NOCB macro uses only flags. */
	rcu_nocb_lock_irqsave(rdp, flags);
	return flags;
}
void rusix_rcubatch_irq_restore(void *opaque, unsigned long flags)
{
	rcu_nocb_unlock_irqrestore(opaque, flags);
}
void rusix_rcubatch_warn_offline(void)
{
	WARN_ON_ONCE(cpu_is_offline(smp_processor_id()));
}
bool rusix_rcubatch_in_softirq(void) { return in_serving_softirq(); }
bool rusix_rcubatch_need_resched(void) { return need_resched(); }
bool rusix_rcubatch_idle_task(void) { return is_idle_task(current); }
u64 rusix_rcubatch_clock(void) { return local_clock(); }
unsigned long rusix_rcubatch_jiffies(void) { return jiffies; }
void rusix_rcubatch_trace_start(void *opaque, long limit)
{
	struct rcu_data *rdp = opaque;
	trace_rcu_batch_start(rcu_state.name, rcu_segcblist_n_cbs(&rdp->cblist), limit);
}
void rusix_rcubatch_trace_end(void *opaque, long count, bool remaining)
{
	struct rcu_data *rdp = opaque;
	trace_rcu_batch_end(rcu_state.name, count, remaining, need_resched(),
			    is_idle_task(current), rcu_is_callbacks_kthread(rdp));
}
void rusix_rcubatch_trace_dequeued(struct rcu_segcblist *list)
{
	trace_rcu_segcb_stats(list, TPS("SegCbDequeued"));
}
void rusix_rcubatch_trace_invoke(struct rcu_head *head)
{
	trace_rcu_invoke_callback(rcu_state.name, head);
}
void rusix_rcubatch_tick_set(void) { tick_dep_set_task(current, TICK_DEP_BIT_RCU); }
void rusix_rcubatch_tick_clear(void) { tick_dep_clear_task(current, TICK_DEP_BIT_RCU); }
void rusix_rcubatch_bh_enable(void) { local_bh_enable(); }
void rusix_rcubatch_bh_disable(void) { local_bh_disable(); }
/* Keep the two original lockdep WARN_ON_ONCE identities independent. */
void rusix_rcubatch_assert_irqs_enabled_before(void) { lockdep_assert_irqs_enabled(); }
void rusix_rcubatch_assert_irqs_enabled_after(void) { lockdep_assert_irqs_enabled(); }
void rusix_rcubatch_cond_resched(void) { cond_resched_tasks_rcu_qs(); }
void rusix_rcubatch_debug_unqueue(struct rcu_head *head) { debug_rcu_head_unqueue(head); }
void rusix_rcubatch_lock_acquire(void) { rcu_lock_acquire(&rcu_callback_map); }
void rusix_rcubatch_lock_release(void) { rcu_lock_release(&rcu_callback_map); }
rcu_callback_t rusix_rcubatch_func(struct rcu_head *head) { return head->func; }
void rusix_rcubatch_debug_callback(struct rcu_head *head) { debug_rcu_head_callback(head); }
void rusix_rcubatch_clear_func(struct rcu_head *head) { WRITE_ONCE(head->func, (rcu_callback_t)0L); }
/* Independent once state, not one warning site shared by four predicates. */
void rusix_rcubatch_warn_zero_nonempty(bool bad) { WARN_ON_ONCE(bad); }
void rusix_rcubatch_warn_nonzero_empty(bool bad) { WARN_ON_ONCE(bad); }
void rusix_rcubatch_warn_zero_segments(bool bad) { WARN_ON_ONCE(bad); }
void rusix_rcubatch_warn_nonempty_no_segments(bool bad) { WARN_ON_ONCE(bad); }
#endif
