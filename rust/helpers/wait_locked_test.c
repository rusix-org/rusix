// SPDX-License-Identifier: GPL-2.0-only
/* Test-only opaque locked-wait fixture bridge. */
#include <linux/types.h>
struct task_struct;
void * rusix_locked_test_alloc(unsigned int mode, unsigned int scenario, bool irq);
void rusix_locked_test_free(void *data);
void rusix_locked_test_run(void *data);
u32 rusix_locked_test_members(void *data, struct task_struct *task);
u32 rusix_locked_test_checks(void *data);
u32 rusix_locked_test_wake(void *data, bool publish);
void rusix_locked_test_abort(void *data);
void rusix_locked_test_result(void *data, s64 *out);

void * rust_helper_locked_test_alloc(unsigned int mode, unsigned int scenario, bool irq)
{
	return rusix_locked_test_alloc(mode, scenario, irq);
}

void rust_helper_locked_test_free(void *data)
{
	rusix_locked_test_free(data);
}

void rust_helper_locked_test_run(void *data)
{
	rusix_locked_test_run(data);
}

u32 rust_helper_locked_test_members(void *data, void *task)
{
	return rusix_locked_test_members(data, task);
}

u32 rust_helper_locked_test_checks(void *data)
{
	return rusix_locked_test_checks(data);
}

u32 rust_helper_locked_test_wake(void *data, bool publish)
{
	return rusix_locked_test_wake(data, publish);
}

void rust_helper_locked_test_abort(void *data)
{
	rusix_locked_test_abort(data);
}

void rust_helper_locked_test_result(void *data, s64 *out)
{
	rusix_locked_test_result(data, out);
}
