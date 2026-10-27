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

struct task_struct;
void *rusix_wait_lifecycle_alloc(unsigned int mode);
void rusix_wait_lifecycle_free(void *data);
void rusix_wait_lifecycle_run(void *data, unsigned int slot, unsigned int timeout_ms);
u32 rusix_wait_lifecycle_members(void *data);
int rusix_wait_lifecycle_publish(void *data, u32 payload);
int rusix_wait_lifecycle_mismatch(void *data);
void rusix_wait_lifecycle_abort(void *data);
void rusix_wait_lifecycle_result(void *data, unsigned int slot, s64 *out);
u32 rusix_wait_lifecycle_blocked(struct task_struct *task);

void *rust_helper_wait_lifecycle_alloc(unsigned int mode)
{
	return rusix_wait_lifecycle_alloc(mode);
}
void rust_helper_wait_lifecycle_free(void *data)
{
	rusix_wait_lifecycle_free(data);
}
void rust_helper_wait_lifecycle_run(void *data, unsigned int slot, unsigned int timeout_ms)
{
	rusix_wait_lifecycle_run(data, slot, timeout_ms);
}
u32 rust_helper_wait_lifecycle_members(void *data)
{
	return rusix_wait_lifecycle_members(data);
}
int rust_helper_wait_lifecycle_publish(void *data, u32 payload)
{
	return rusix_wait_lifecycle_publish(data, payload);
}
int rust_helper_wait_lifecycle_mismatch(void *data)
{
	return rusix_wait_lifecycle_mismatch(data);
}
void rust_helper_wait_lifecycle_abort(void *data)
{
	rusix_wait_lifecycle_abort(data);
}
void rust_helper_wait_lifecycle_result(void *data, unsigned int slot, s64 *out)
{
	rusix_wait_lifecycle_result(data, slot, out);
}
u32 rust_helper_wait_lifecycle_blocked(void *task)
{
	return rusix_wait_lifecycle_blocked(task);
}

/* WOKEN protocol consumers use separate storage and condition publication. */
void *rusix_wait_woken_test_alloc(unsigned int mode);
void rusix_wait_woken_test_free(void *data);
void rusix_wait_woken_test_run(void *data, unsigned int timeout_ms);
u32 rusix_wait_woken_test_members(void *data);
void rusix_wait_woken_test_publish(void *data);
void rusix_wait_woken_test_probe(void *data, unsigned int command, s64 *out);
void rusix_wait_woken_test_abort(void *data);
void rusix_wait_woken_test_result(void *data, s64 *out);

void * rust_helper_wait_woken_test_alloc(unsigned int mode)
{
	return rusix_wait_woken_test_alloc(mode);
}

void rust_helper_wait_woken_test_free(void *data)
{
	rusix_wait_woken_test_free(data);
}

void rust_helper_wait_woken_test_run(void *data, unsigned int timeout_ms)
{
	rusix_wait_woken_test_run(data, timeout_ms);
}

u32 rust_helper_wait_woken_test_members(void *data)
{
	return rusix_wait_woken_test_members(data);
}

void rust_helper_wait_woken_test_publish(void *data)
{
	rusix_wait_woken_test_publish(data);
}

void rust_helper_wait_woken_test_probe(void *data, unsigned int command, s64 *out)
{
	rusix_wait_woken_test_probe(data, command, out);
}

void rust_helper_wait_woken_test_abort(void *data)
{
	rusix_wait_woken_test_abort(data);
}

void rust_helper_wait_woken_test_result(void *data, s64 *out)
{
	rusix_wait_woken_test_result(data, out);
}
