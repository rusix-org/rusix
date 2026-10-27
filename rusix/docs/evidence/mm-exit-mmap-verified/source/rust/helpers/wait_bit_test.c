// SPDX-License-Identifier: GPL-2.0-only
/* Test-only opaque fixture bridge. */
#include <linux/types.h>
struct task_struct;
void * rusix_bit_case_alloc(unsigned int mode, unsigned int scenario);
void rusix_bit_case_free(void *data);
void rusix_bit_case_run(void *data, unsigned int index, unsigned int timeout_ms);
void rusix_bit_case_result(void *data, unsigned int index, s64 *out);
u32 rusix_bit_case_members(void *data, struct task_struct *task);
u32 rusix_bit_case_acquired(void *data);
u32 rusix_bit_case_value(void *data);
void rusix_bit_case_release(void *data);
void rusix_bit_case_release_owner(void *data, unsigned int index);
void rusix_bit_case_abort(void *data);
void rusix_bit_case_probe(void *data, unsigned int command, s64 *out);

void * rust_helper_bit_case_alloc(unsigned int mode, unsigned int scenario)
{
	return rusix_bit_case_alloc(mode, scenario);
}

void rust_helper_bit_case_free(void *data)
{
	rusix_bit_case_free(data);
}

void rust_helper_bit_case_run(void *data, unsigned int index, unsigned int timeout_ms)
{
	rusix_bit_case_run(data, index, timeout_ms);
}

void rust_helper_bit_case_result(void *data, unsigned int index, s64 *out)
{
	rusix_bit_case_result(data, index, out);
}

u32 rust_helper_bit_case_members(void *data, void *task)
{
	return rusix_bit_case_members(data, task);
}

u32 rust_helper_bit_case_acquired(void *data)
{
	return rusix_bit_case_acquired(data);
}

u32 rust_helper_bit_case_value(void *data)
{
	return rusix_bit_case_value(data);
}

void rust_helper_bit_case_release(void *data)
{
	rusix_bit_case_release(data);
}

void rust_helper_bit_case_release_owner(void *data, unsigned int index)
{
	rusix_bit_case_release_owner(data, index);
}

void rust_helper_bit_case_abort(void *data)
{
	rusix_bit_case_abort(data);
}

void rust_helper_bit_case_probe(void *data, unsigned int command, s64 *out)
{
	rusix_bit_case_probe(data, command, out);
}

void rusix_wait_bit_test_time(unsigned long now, unsigned long deadline, s64 *out);
void rust_helper_wait_bit_test_time(unsigned long now, unsigned long deadline, s64 *out)
{
	rusix_wait_bit_test_time(now, deadline, out);
}
