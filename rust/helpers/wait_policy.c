// SPDX-License-Identifier: GPL-2.0-only
/* Temporary primitive boundary for the Rust generic wait policy translation.
 * Include only under CONFIG_RUSIX_COMPLETION_RUST. Replace these adapters when
 * reviewed Rust spinlock and generic-wait flag ownership protocols take over.
 */
#include <linux/list.h>
#include <linux/lockdep.h>
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

void rust_helper_wait_entry_update_flags(struct wait_queue_entry *entry,
					unsigned int clear, unsigned int set)
{
	/* Original non-atomic C RMW, intentionally before caller takes queue lock. */
	entry->flags = (entry->flags & ~clear) | set;
}

void rust_helper_wait_list_add(struct list_head *entry, struct list_head *head)
{
	list_add(entry, head);
}

void rust_helper_wait_list_del(struct list_head *entry)
{
	list_del(entry);
}

void rust_helper_wait_spin_init(struct wait_queue_head *wq_head)
{
	/* Preserve original expression for initial lockdep debug naming. */
	spin_lock_init(&wq_head->lock);
}

void rust_helper_wait_lock_class(struct wait_queue_head *wq_head,
				const char *name, struct lock_class_key *key)
{
	lockdep_set_class_and_name(&wq_head->lock, key, name);
}

void rust_helper_wait_list_del_init_careful(struct list_head *entry)
{
	/* Release self-link pairs with the acquire list_empty_careful in finish. */
	list_del_init_careful(entry);
}

void rust_helper_wait_clear_woken_mb(struct wait_queue_entry *entry)
{
	/* Original B: C read/clear plus store-and-full-barrier, not fetch_and. */
	smp_store_mb(entry->flags, entry->flags & ~WQ_FLAG_WOKEN);
}

void rust_helper_wait_set_woken_after_mb(struct wait_queue_entry *entry)
{
	/* Original C: full barrier precedes the C non-atomic flags RMW. */
	smp_mb();
	entry->flags |= WQ_FLAG_WOKEN;
}
