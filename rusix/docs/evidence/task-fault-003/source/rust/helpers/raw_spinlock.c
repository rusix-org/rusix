// SPDX-License-Identifier: GPL-2.0
#include <linux/lockdep.h>
#include <linux/sched.h>
#include <linux/spinlock.h>

unsigned long rust_helper_raw_spin_lock_irqsave(raw_spinlock_t *lock)
{
	unsigned long flags;

	raw_spin_lock_irqsave(lock, flags);
	return flags;
}

void rust_helper_raw_spin_unlock_irqrestore(raw_spinlock_t *lock,
					  unsigned long flags)
{
	raw_spin_unlock_irqrestore(lock, flags);
}

void rust_helper_lockdep_assert_RT_in_threaded_ctx(void)
{
	lockdep_assert_RT_in_threaded_ctx();
}

void rust_helper_raw_spin_lock_irq(raw_spinlock_t *lock)
{
	raw_spin_lock_irq(lock);
}

void rust_helper_raw_spin_unlock_irq(raw_spinlock_t *lock)
{
	raw_spin_unlock_irq(lock);
}
