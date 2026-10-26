// SPDX-License-Identifier: GPL-2.0-only
#include <linux/types.h>
void *rusix_rculist_alloc(void);
void rusix_rculist_free(void *p);
s64 rusix_rculist_action(void *p, u32 op, u32 dst, u32 src, u32 node, u64 value);
void rusix_rculist_snapshot(void *p, u32 which, s64 *out);
void rusix_rculist_simple(void *p, u32 which, s64 *out);
void *rust_helper_rculist_alloc(void) { return rusix_rculist_alloc(); }
void rust_helper_rculist_free(void *p) { rusix_rculist_free(p); }
s64 rust_helper_rculist_action(void *p, u32 op, u32 dst, u32 src, u32 node, u64 value)
{
	return rusix_rculist_action(p, op, dst, src, node, value);
}
void rust_helper_rculist_snapshot(void *p, u32 which, s64 *out)
{
	rusix_rculist_snapshot(p, which, out);
}
void rust_helper_rculist_simple(void *p, u32 which, s64 *out)
{
	rusix_rculist_simple(p, which, out);
}
void *rusix_rculist_runtime_start(u32 mode);
u32 rusix_rculist_runtime_phase(void *p);
u32 rusix_rculist_runtime_count(void *p);
void rusix_rculist_runtime_release(void *p);
bool rusix_rculist_runtime_wait(void *p, u32 ms);
void rusix_rculist_runtime_result(void *p, s64 *out);
void rusix_rculist_runtime_put(void *p);
void *rust_helper_rculist_runtime_start(u32 mode) { return rusix_rculist_runtime_start(mode); }
u32 rust_helper_rculist_runtime_phase(void *p) { return rusix_rculist_runtime_phase(p); }
u32 rust_helper_rculist_runtime_count(void *p) { return rusix_rculist_runtime_count(p); }
void rust_helper_rculist_runtime_release(void *p) { rusix_rculist_runtime_release(p); }
bool rust_helper_rculist_runtime_wait(void *p, u32 ms) { return rusix_rculist_runtime_wait(p, ms); }
void rust_helper_rculist_runtime_result(void *p, s64 *out) { rusix_rculist_runtime_result(p, out); }
void rust_helper_rculist_runtime_put(void *p) { rusix_rculist_runtime_put(p); }
