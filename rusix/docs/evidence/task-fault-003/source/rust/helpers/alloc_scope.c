// SPDX-License-Identifier: GPL-2.0
/* Inline boundaries for the synchronous Rust NOIO allocation scope. */
#include <linux/sched/mm.h>

unsigned int rust_helper_memalloc_noio_save(void)
{
	return memalloc_noio_save();
}

void rust_helper_memalloc_noio_restore(unsigned int flags)
{
	memalloc_noio_restore(flags);
}
