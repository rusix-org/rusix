// SPDX-License-Identifier: GPL-2.0-only
/* Temporary wait-bit primitive boundary under CONFIG_RUSIX_COMPLETION_RUST.
 * Keep architecture/KCSAN ordering and mixed C bitmap accesses in original C
 * operations until reviewed Rust bit/marked-read primitives own those contracts.
 */
#include <linux/bitops.h>
#include <linux/jiffies.h>
#include <linux/wait_bit.h>

int rust_helper_wait_bit_test(const struct wait_bit_key *key)
{
	return test_bit(key->bit_nr, key->flags);
}
int rust_helper_wait_bit_test_acquire(const struct wait_bit_key *key)
{
	return test_bit_acquire(key->bit_nr, key->flags);
}
int rust_helper_wait_bit_test_and_set(const struct wait_bit_key *key)
{
	return test_and_set_bit(key->bit_nr, key->flags);
}
unsigned long rust_helper_wait_bit_jiffies(void)
{
	return READ_ONCE(jiffies);
}
