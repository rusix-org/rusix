// SPDX-License-Identifier: GPL-2.0-or-later
/* Temporary primitives for the Rust translation of kernel/rcu/sync.c.
 * Original: Copyright (c) 2015, Red Hat, Inc.
 * Author: Oleg Nesterov <oleg@redhat.com>.
 * State transitions, waiting and callback replay remain Rust policy. These
 * accesses retain the C mixed-access/LKMM domain until ownership is migrated.
 */
#include <linux/rcu_sync.h>
#include <linux/sched.h>

int rust_helper_rcu_sync_read_int(const int *slot)
{
	return *slot;
}
int rust_helper_rcu_sync_read_int_once(const int *slot)
{
	return READ_ONCE(*slot);
}
void rust_helper_rcu_sync_write_int(int *slot, int value)
{
	*slot = value;
}
void rust_helper_rcu_sync_write_int_once(int *slot, int value)
{
	WRITE_ONCE(*slot, value);
}

void rust_helper_rcu_sync_wait_init(struct rcu_sync *rsp)
{
	/* Original expression/name and one permanent key for this initializer. */
	init_waitqueue_head(&rsp->gp_wait);
}

void rust_helper_rcu_sync_hurry(struct rcu_head *head, rcu_callback_t func)
{
	/* Header inline when !RCU_LAZY; preserve its exact configuration meaning. */
	call_rcu_hurry(head, func);
}

void rust_helper_rcu_sync_might_sleep(void)
{
	might_sleep();
}

/* Independent original warn-once sites; never consolidate their state. */
void rust_helper_rcu_sync_warn_callback_idle(bool bad)
{
	WARN_ON_ONCE(bad);
}
void rust_helper_rcu_sync_warn_callback_passed(bool bad)
{
	WARN_ON_ONCE(bad);
}
void rust_helper_rcu_sync_warn_enter_count(bool bad)
{
	WARN_ON_ONCE(bad);
}
void rust_helper_rcu_sync_warn_exit_idle(bool bad)
{
	WARN_ON_ONCE(bad);
}
void rust_helper_rcu_sync_warn_exit_count(bool bad)
{
	WARN_ON_ONCE(bad);
}
void rust_helper_rcu_sync_warn_dtor_passed(bool bad)
{
	WARN_ON_ONCE(bad);
}
void rust_helper_rcu_sync_warn_dtor_count(bool bad)
{
	WARN_ON_ONCE(bad);
}
void rust_helper_rcu_sync_warn_dtor_idle(bool bad)
{
	WARN_ON_ONCE(bad);
}
