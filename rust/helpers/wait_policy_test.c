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

int rusix_wait_test_enrollment(unsigned int scenario, bool disabled, u32 *out);
u32 rusix_wait_test_constructor(bool disabled);

int rust_helper_wait_test_enrollment(unsigned int scenario, bool disabled, u32 *out)
{
	return rusix_wait_test_enrollment(scenario, disabled, out);
}

u32 rust_helper_wait_test_constructor(bool disabled)
{
	return rusix_wait_test_constructor(disabled);
}
