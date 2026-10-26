/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef RUSIX_RCU_BATCH_TEST_H
#define RUSIX_RCU_BATCH_TEST_H
#include <linux/types.h>
struct rcu_head;
/* Private fixture only. Caller pins CPUs and retains heads throughout the call.
 * A refused teardown retains the private descriptor and requires caller storage
 * retention; no descriptor is installed in the global per-CPU RCU state. */
int rusix_rcubatch_private(struct rcu_head **heads, u32 nr, void **private_rdp,
			   bool *retained, s64 *out);
bool rusix_rcubatch_private_accounting(void *private_rdp, u32 expected);
void *rusix_rcubatch_budget_create(struct rcu_head **heads);
int rusix_rcubatch_budget_step(void *private_rdp, struct rcu_head *second,
                              struct rcu_head *pending, s64 *out);
bool rusix_rcubatch_budget_detached(void *private_rdp, struct rcu_head *pending);
bool rusix_rcubatch_budget_drain(void *private_rdp, s64 *out);
void rusix_rcubatch_time_samples(s64 *out);
void *rusix_rcubatch_start(u32 mode);
bool rusix_rcubatch_wait(void *p, u32 ms);
void rusix_rcubatch_result(void *p, s64 *out);
void rusix_rcubatch_put(void *p);
#endif
