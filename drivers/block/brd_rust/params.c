// SPDX-License-Identifier: GPL-2.0-only
/* Parameter storage and kernel metadata for the Rust BRD implementation.
 * Parsing policy, normalization, device lifetime and I/O live in Rust.
 */
#include <linux/init.h>
#include <linux/initrd.h>
#include <linux/module.h>
#include <linux/moduleparam.h>

int rusix_brd_rd_nr = CONFIG_BLK_DEV_RAM_COUNT;
module_param_named(rd_nr, rusix_brd_rd_nr, int, 0444);
MODULE_PARM_DESC(rd_nr, "Maximum number of brd devices");

/* Existing initrd code refers to this symbol when CONFIG_BLK_DEV_RAM is set. */
unsigned long rd_size = CONFIG_BLK_DEV_RAM_SIZE;
module_param(rd_size, ulong, 0444);
MODULE_PARM_DESC(rd_size, "Size of each RAM disk in kbytes.");

int rusix_brd_max_part = 1;
module_param_named(max_part, rusix_brd_max_part, int, 0444);
MODULE_PARM_DESC(max_part, "Num Minors to reserve between devices");

void rusix_brd_params_lock(void);
void rusix_brd_params_unlock(void);

/* These also cover configurations where the APIs are static inline no-ops. */
void rusix_brd_params_lock(void)
{
	kernel_param_lock(THIS_MODULE);
}

void rusix_brd_params_unlock(void)
{
	kernel_param_unlock(THIS_MODULE);
}

#ifndef MODULE
extern int rusix_brd_legacy_size(char *value);
__setup("ramdisk_size=", rusix_brd_legacy_size);
#endif
