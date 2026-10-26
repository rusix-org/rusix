// SPDX-License-Identifier: GPL-2.0-only
/* Test-only opaque fixture and original-C oracle bridge. */
#include <linux/types.h>
void rusix_owner_hash_observe(unsigned long address, int bit, bool variable, unsigned long *out);
u32 rusix_owner_head_observe(unsigned long identity, unsigned int index);
void *rusix_owner_alloc(unsigned int mode, unsigned int flags_a, unsigned int flags_b);
void rusix_owner_free(void *data);
void rusix_owner_run(void *data, unsigned int slot, unsigned int timeout_ms);
u32 rusix_owner_members(void *data);
void rusix_owner_publish(void *data, unsigned int slot, u32 payload);
void rusix_owner_abort(void *data);
void rusix_owner_result(void *data, unsigned int slot, s64 *out);

void rust_helper_owner_hash_observe(unsigned long address, int bit, bool variable, unsigned long *out)
{
	rusix_owner_hash_observe(address, bit, variable, out);
}
u32 rust_helper_owner_head_observe(unsigned long identity, unsigned int index)
{
	return rusix_owner_head_observe(identity, index);
}
void *rust_helper_owner_alloc(unsigned int mode, unsigned int flags_a, unsigned int flags_b)
{
	return rusix_owner_alloc(mode, flags_a, flags_b);
}
void rust_helper_owner_free(void *data) { rusix_owner_free(data); }
void rust_helper_owner_run(void *data, unsigned int slot, unsigned int timeout_ms)
{
	rusix_owner_run(data, slot, timeout_ms);
}
u32 rust_helper_owner_members(void *data) { return rusix_owner_members(data); }
void rust_helper_owner_publish(void *data, unsigned int slot, u32 payload)
{
	rusix_owner_publish(data, slot, payload);
}
void rust_helper_owner_abort(void *data) { rusix_owner_abort(data); }
void rust_helper_owner_result(void *data, unsigned int slot, s64 *out)
{
	rusix_owner_result(data, slot, out);
}
