// SPDX-License-Identifier: GPL-2.0-only
/* KUnit-only forwarding, without exposing private scheduler headers. */
#include <linux/types.h>

int rusix_wait_test_run(unsigned int scenario, unsigned int wrapper,
			bool disabled, u32 *out);
u32 rusix_wait_test_null_sync(bool disabled);

int rust_helper_wait_test_run(unsigned int scenario, unsigned int wrapper,
			      bool disabled, u32 *out)
{
	return rusix_wait_test_run(scenario, wrapper, disabled, out);
}

u32 rust_helper_wait_test_null_sync(bool disabled)
{
	return rusix_wait_test_null_sync(disabled);
}
