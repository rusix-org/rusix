// SPDX-License-Identifier: GPL-2.0
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
