/* SPDX-License-Identifier: GPL-2.0-only */
/* Exact configured layout for Rust-owned bit-wait storage; no C allocation. */
#ifndef _LINUX_RUSIX_WAIT_BIT_TYPES_H
#define _LINUX_RUSIX_WAIT_BIT_TYPES_H
#include <linux/cache.h>
#include <linux/wait.h>

/* Alignment belongs to the array, not every head. Bindgen carries the exact
 * configured alignment to Rust without hardcoding an x86 cache-line literal.
 */
struct rusix_wait_bit_table {
	struct wait_queue_head heads[256];
} __aligned(SMP_CACHE_BYTES);
enum {
	RUSIX_WAIT_BIT_TABLE_ALIGNMENT = SMP_CACHE_BYTES,
	RUSIX_WAIT_BIT_HEAD_SIZE = sizeof(struct wait_queue_head),
};
#endif
