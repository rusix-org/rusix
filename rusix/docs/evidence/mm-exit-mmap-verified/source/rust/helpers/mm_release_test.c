// SPDX-License-Identifier: GPL-2.0-only
#include <linux/types.h>
void *rusix_mm_test_start(u32 mode);
bool rusix_mm_test_wait(void *p, u32 ms);
void rusix_mm_test_result(void *p, s64 *out);
void rusix_mm_test_put(void *p);

void *rust_helper_mm_test_start(u32 mode) { return rusix_mm_test_start(mode); }
bool rust_helper_mm_test_wait(void *p, u32 ms) { return rusix_mm_test_wait(p, ms); }
void rust_helper_mm_test_result(void *p, s64 *out) { rusix_mm_test_result(p, out); }
void rust_helper_mm_test_put(void *p) { rusix_mm_test_put(p); }
