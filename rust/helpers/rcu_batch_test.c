// SPDX-License-Identifier: GPL-2.0-only
#include <linux/types.h>
void *rusix_rcubatch_start(u32 mode);
bool rusix_rcubatch_wait(void *p, u32 ms);
void rusix_rcubatch_result(void *p, s64 *out);
void rusix_rcubatch_put(void *p);

void *rust_helper_rcubatch_start(u32 mode)
{
	return rusix_rcubatch_start(mode);
}
bool rust_helper_rcubatch_wait(void *p, u32 ms)
{
	return rusix_rcubatch_wait(p, ms);
}
void rust_helper_rcubatch_result(void *p, s64 *out)
{
	rusix_rcubatch_result(p, out);
}
void rust_helper_rcubatch_put(void *p)
{
	rusix_rcubatch_put(p);
}
