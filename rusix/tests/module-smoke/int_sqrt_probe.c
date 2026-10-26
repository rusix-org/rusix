// SPDX-License-Identifier: BSD-2-Clause
/* VM-only consumer of the existing unrestricted int_sqrt export. */
#include <linux/errno.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/limits.h>
#include <linux/math.h>
#include <linux/module.h>

#if BITS_PER_LONG != 64
#error "This module smoke fixture currently requires a 64-bit kernel"
#endif

struct sqrt_case {
	unsigned long input;
	unsigned long expected;
};

static const struct sqrt_case cases[] = {
	{ 0UL, 0UL },
	{ 1UL, 1UL },
	{ 2UL, 1UL },
	{ 3UL, 1UL },
	{ 4UL, 2UL },
	{ 15UL, 3UL },
	{ 16UL, 4UL },
	{ 17UL, 4UL },
	{ 4294967295UL, 65535UL },
	{ 4294967296UL, 65536UL },
	{ 4294967297UL, 65536UL },
	{ 9223372036854775808UL, 3037000499UL },
	/* (2^32 - 1)^2 and its adjacent values. */
	{ 18446744065119617024UL, 4294967294UL },
	{ 18446744065119617025UL, 4294967295UL },
	{ 18446744065119617026UL, 4294967295UL },
	{ ULONG_MAX - 1, 4294967295UL },
	{ ULONG_MAX, 4294967295UL },
};

static int __init int_sqrt_probe_init(void)
{
	unsigned long result;
	size_t i;

	for (i = 0; i < ARRAY_SIZE(cases); ++i) {
		result = int_sqrt(cases[i].input);
		if (result != cases[i].expected) {
			pr_err("RUSIX_MODULE_FAIL input=%lu actual=%lu expected=%lu\n",
			       cases[i].input, result, cases[i].expected);
			return -EINVAL;
		}
	}
	pr_info("RUSIX_MODULE_CHECKS_PASS cases=%zu\n", ARRAY_SIZE(cases));
	return 0;
}

static void __exit int_sqrt_probe_exit(void)
{
	pr_info("RUSIX_MODULE_UNLOAD_PASS\n");
}

module_init(int_sqrt_probe_init);
module_exit(int_sqrt_probe_exit);
MODULE_DESCRIPTION("rusix VM-only int_sqrt module ABI probe");
/* Deliberately non-GPL-compatible to verify the original export policy. */
MODULE_LICENSE("BSD");
