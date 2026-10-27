/* SPDX-License-Identifier: GPL-2.0-only */
/* Separate builtin-context TU; normal bindings retain their MODULE definition. */
#ifdef MODULE
#error "builtin init bindings require MODULE undefined"
#endif
#include <linux/init.h>
