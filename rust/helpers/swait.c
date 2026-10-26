// SPDX-License-Identifier: GPL-2.0
/* Temporary list-operation boundary for the Rust swait policy migration.
 * Include from helpers.c only under CONFIG_RUSIX_COMPLETION_RUST.
 * Retain list hardening/debug validation and READ_ONCE/WRITE_ONCE semantics.
 * Remove when a reviewed Rust marked-pointer/list implementation owns them.
 */
#include <linux/list.h>

int rust_helper_swait_list_empty(const struct list_head *head)
{
	return list_empty(head);
}

void rust_helper_swait_list_add_tail(struct list_head *node,
				   struct list_head *head)
{
	list_add_tail(node, head);
}

void rust_helper_swait_list_del_init(struct list_head *node)
{
	list_del_init(node);
}
