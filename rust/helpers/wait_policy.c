// SPDX-License-Identifier: GPL-2.0-only
/* Temporary primitive boundary for the Rust generic wait policy translation.
 * Include only under CONFIG_RUSIX_COMPLETION_RUST. Replace these adapters when
 * reviewed Rust spinlock and generic-wait flag ownership protocols take over.
 */
#include <linux/spinlock.h>
#include <linux/wait.h>

unsigned long rust_helper_wait_spin_lock_irqsave(spinlock_t *lock)
{
	unsigned long flags;

	spin_lock_irqsave(lock, flags);
	return flags;
}

void rust_helper_wait_spin_unlock_irqrestore(spinlock_t *lock,
					   unsigned long flags)
{
	spin_unlock_irqrestore(lock, flags);
}

unsigned int rust_helper_wait_entry_flags(const struct wait_queue_entry *entry)
{
	/*
	 * Preserve baseline pre-callback flags observation. C flags synchronization
	 * includes lockless wait_woken accesses; direct Rust ownership is not proven.
	 */
	return entry->flags;
}
