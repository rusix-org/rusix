// SPDX-License-Identifier: GPL-2.0-or-later
/* Temporary LKMM access boundary for the Rust RCU list policy.
 * Based on Linux 6.18.58 rcu_segcblist.c, Copyright IBM Corporation, 2017,
 * author Paul E. McKenney. No list policy or storage ownership moves here.
 * Preserve plain versus marked accesses; replace only after native Rust LKMM
 * primitives and all C users' ownership/observation contracts are established.
 */
#include <linux/cpu.h>
#include <linux/rcu_segcblist.h>
#include <linux/bug.h>
#include <linux/build_bug.h>

static_assert(RCU_CBLIST_NSEGS == 4);
static_assert(RCU_NEXT_TAIL + 1 == RCU_CBLIST_NSEGS);
static_assert(sizeof(((struct rcu_segcblist *)0)->tails) /
	      sizeof(((struct rcu_segcblist *)0)->tails[0]) == RCU_CBLIST_NSEGS);
static_assert(sizeof(((struct rcu_segcblist *)0)->gp_seq) /
	      sizeof(((struct rcu_segcblist *)0)->gp_seq[0]) == RCU_CBLIST_NSEGS);

long rust_helper_rcu_list_read_long(const long *slot)
{
	return *slot;
}

void rust_helper_rcu_list_write_long(long *slot, long value)
{
	*slot = value;
}

long rust_helper_rcu_list_read_long_once(const long *slot)
{
	return READ_ONCE(*slot);
}

void rust_helper_rcu_list_write_long_once(long *slot, long value)
{
	WRITE_ONCE(*slot, value);
}

unsigned long rust_helper_rcu_list_read_ulong(const unsigned long *slot)
{
	return *slot;
}

void rust_helper_rcu_list_write_ulong(unsigned long *slot, unsigned long value)
{
	*slot = value;
}

u8 rust_helper_rcu_list_read_u8(const u8 *slot)
{
	return *slot;
}

u8 rust_helper_rcu_list_read_u8_once(const u8 *slot)
{
	return READ_ONCE(*slot);
}

void rust_helper_rcu_list_write_u8_once(u8 *slot, u8 value)
{
	WRITE_ONCE(*slot, value);
}

struct rcu_head *rust_helper_rcu_list_read_node(struct rcu_head *const *slot)
{
	return *slot;
}

void rust_helper_rcu_list_write_node(struct rcu_head **slot, struct rcu_head *value)
{
	*slot = value;
}

struct rcu_head *rust_helper_rcu_list_read_node_once(struct rcu_head *const *slot)
{
	return READ_ONCE(*slot);
}

void rust_helper_rcu_list_write_node_once(struct rcu_head **slot, struct rcu_head *value)
{
	WRITE_ONCE(*slot, value);
}

struct rcu_head **rust_helper_rcu_list_read_tail(struct rcu_head **const *slot)
{
	return *slot;
}

void rust_helper_rcu_list_write_tail(struct rcu_head ***slot, struct rcu_head **value)
{
	*slot = value;
}

struct rcu_head **rust_helper_rcu_list_read_tail_once(struct rcu_head **const *slot)
{
	return READ_ONCE(*slot);
}

void rust_helper_rcu_list_write_tail_once(struct rcu_head ***slot, struct rcu_head **value)
{
	WRITE_ONCE(*slot, value);
}

/* Count publication is one exact non-NOCB LKMM primitive. The full barriers
 * order enqueue/invocation against lockless rcu_barrier count observations.
 */
void rust_helper_rcu_list_ordered_add_len(long *slot, long delta)
{
	smp_mb();
	WRITE_ONCE(*slot, *slot + delta);
	smp_mb();
}

void rust_helper_rcu_list_mb(void)
{
	smp_mb();
}

void rust_helper_rcu_list_cpus_held(void)
{
	lockdep_assert_cpus_held();
}

/* Keep four independent warning sites, as in the original functions. */
void rust_helper_rcu_list_warn_disable_head(bool bad)
{
	WARN_ON_ONCE(bad);
}
void rust_helper_rcu_list_warn_disable_len(bool bad)
{
	WARN_ON_ONCE(bad);
}
void rust_helper_rcu_list_warn_advance(bool bad)
{
	WARN_ON_ONCE(bad);
}
void rust_helper_rcu_list_warn_accelerate(bool bad)
{
	WARN_ON_ONCE(bad);
}
