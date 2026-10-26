// SPDX-License-Identifier: GPL-2.0
/* Preserve the existing C module export policy for the Rust implementation. */
#include <linux/export.h>
#include <linux/math.h>

EXPORT_SYMBOL(int_sqrt);
#if BITS_PER_LONG < 64
EXPORT_SYMBOL(int_sqrt64);
#endif
