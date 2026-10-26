// SPDX-License-Identifier: GPL-2.0-only
#include <linux/types.h>
void *rusix_rcusync_start(u32 mode);
bool rusix_rcusync_wait(void *p, u32 ms);
void rusix_rcusync_result(void *p, s64 *out);
void rusix_rcusync_put(void *p);
void rusix_rcusync_release(void *p);
void *rust_helper_rcusync_start(u32 mode) { return rusix_rcusync_start(mode); }
bool rust_helper_rcusync_wait(void *p, u32 ms) { return rusix_rcusync_wait(p, ms); }
void rust_helper_rcusync_result(void *p, s64 *out) { rusix_rcusync_result(p, out); }
void rust_helper_rcusync_put(void *p) { rusix_rcusync_put(p); }
void rust_helper_rcusync_release(void *p) { rusix_rcusync_release(p); }
