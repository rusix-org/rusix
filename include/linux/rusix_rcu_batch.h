/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _LINUX_RUSIX_RCU_BATCH_H
#define _LINUX_RUSIX_RCU_BATCH_H

#include <linux/jiffies.h>
#include <linux/rcupdate.h>
#include <linux/rcu_segcblist.h>

/* tree.c asserts the private constants against their canonical definitions. */
enum {
	RUSIX_RCU_BATCH_KTHREAD_RUNNING = 1,
	RUSIX_RCU_BATCH_MAX_BLIMIT = 10000,
	RUSIX_RCU_BATCH_NSEC_PER_MSEC = 1000000,
	RUSIX_RCU_BATCH_NSEC_PER_SEC = 1000000000,
	RUSIX_RCU_BATCH_HZ = HZ,
	RUSIX_RCU_BATCH_DOUBLE_CHECK = IS_ENABLED(CONFIG_RCU_DOUBLE_CHECK_CB_TIME),
};

void rusix_rcu_do_batch(void *rdp);
bool rusix_rcu_batch_check_time(long count, long tlimit, bool check, unsigned long limit);
struct rcu_segcblist *rusix_rcubatch_cblist(void *rdp);
long rusix_rcubatch_n_cbs(struct rcu_segcblist *list);
bool rusix_rcubatch_empty(struct rcu_segcblist *list);
bool rusix_rcubatch_local_nonempty(struct rcu_cblist *list);
long rusix_rcubatch_blimit(void *rdp);
void rusix_rcubatch_set_blimit(void *rdp, long value);
long rusix_rcubatch_qlen(void *rdp);
void rusix_rcubatch_set_qlen(void *rdp, long value);
unsigned long rusix_rcubatch_invoked(void *rdp);
void rusix_rcubatch_set_invoked(void *rdp, unsigned long value);
void rusix_rcubatch_set_force_snap(void *rdp, unsigned long value);
unsigned int rusix_rcubatch_status(void *rdp);
void rusix_rcubatch_set_work(void *rdp, char value);
int rusix_rcubatch_divisor(void);
long rusix_rcubatch_resched_ns(void);
long rusix_rcubatch_global_blimit(void);
long rusix_rcubatch_qlowmark(void);
long rusix_rcubatch_qhimark(void);
unsigned long rusix_rcubatch_force_qs(void);
unsigned long rusix_rcubatch_irq_save(void *rdp);
void rusix_rcubatch_irq_restore(void *rdp, unsigned long flags);
void rusix_rcubatch_warn_offline(void);
bool rusix_rcubatch_in_softirq(void);
bool rusix_rcubatch_need_resched(void);
bool rusix_rcubatch_idle_task(void);
u64 rusix_rcubatch_clock(void);
unsigned long rusix_rcubatch_jiffies(void);
void rusix_rcubatch_trace_start(void *rdp, long limit);
void rusix_rcubatch_trace_end(void *rdp, long count, bool remaining);
void rusix_rcubatch_trace_dequeued(struct rcu_segcblist *list);
void rusix_rcubatch_trace_invoke(struct rcu_head *head);
void rusix_rcubatch_tick_set(void);
void rusix_rcubatch_tick_clear(void);
void rusix_rcubatch_bh_enable(void);
void rusix_rcubatch_bh_disable(void);
void rusix_rcubatch_assert_irqs_enabled_before(void);
void rusix_rcubatch_assert_irqs_enabled_after(void);
void rusix_rcubatch_cond_resched(void);
void rusix_rcubatch_debug_unqueue(struct rcu_head *head);
void rusix_rcubatch_lock_acquire(void);
void rusix_rcubatch_lock_release(void);
rcu_callback_t rusix_rcubatch_func(struct rcu_head *head);
void rusix_rcubatch_debug_callback(struct rcu_head *head);
void rusix_rcubatch_clear_func(struct rcu_head *head);
void rusix_rcubatch_warn_zero_nonempty(bool bad);
void rusix_rcubatch_warn_nonzero_empty(bool bad);
void rusix_rcubatch_warn_zero_segments(bool bad);
void rusix_rcubatch_warn_nonempty_no_segments(bool bad);
#endif
