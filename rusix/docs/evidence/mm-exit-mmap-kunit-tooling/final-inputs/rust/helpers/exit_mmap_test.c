// SPDX-License-Identifier: GPL-2.0-only
#include <linux/types.h>
void *rusix_exit_test_start(u32 mode);
bool rusix_exit_test_wait(void *ptr, u32 ms);
void rusix_exit_test_result(void *ptr, s64 *out);
void rusix_exit_test_put(void *ptr);

void *rust_helper_exit_test_start(u32 mode) { return rusix_exit_test_start(mode); }
bool rust_helper_exit_test_wait(void *ptr, u32 ms) { return rusix_exit_test_wait(ptr, ms); }
void rust_helper_exit_test_result(void *ptr, s64 *out) { rusix_exit_test_result(ptr, out); }
void rust_helper_exit_test_put(void *ptr) { rusix_exit_test_put(ptr); }
