// SPDX-License-Identifier: GPL-2.0
/*
 * rusix compatibility checks, separate from the unchanged upstream test suite.
 * Reference algorithm from Linux commit
 * 21a7f44fd0765fcc5194130b28767786eba1d1e7, lib/math/int_sqrt.c:
 * Copyright (C) 2013 Davidlohr Bueso <davidlohr.bueso@hp.com>
 * Based on Guy L. Steele's shift-and-subtract algorithm.
 */
#include <kunit/test.h>
#include <linux/bitops.h>
#include <linux/limits.h>
#include <linux/math.h>
#include <linux/math64.h>
#include <linux/module.h>

static unsigned long reference_int_sqrt(unsigned long x)
{
	unsigned long b, m, y = 0;

	if (x <= 1)
		return x;

	m = 1UL << (__fls(x) & ~1UL);
	while (m != 0) {
		b = y + m;
		y >>= 1;
		if (x >= b) {
			x -= b;
			y += m;
		}
		m >>= 2;
	}
	return y;
}

static void check_input(struct kunit *test, unsigned long x)
{
	unsigned long result = int_sqrt(x);

	KUNIT_ASSERT_EQ_MSG(test, result, reference_int_sqrt(x), "x=%lu", x);
	/* Independent floor-sqrt bounds, using division to avoid square overflow. */
	KUNIT_ASSERT_LE(test, result, (1UL << (BITS_PER_LONG / 2)) - 1);
	if (x == 0) {
		KUNIT_ASSERT_EQ(test, result, 0UL);
		return;
	}
	KUNIT_ASSERT_NE(test, result, 0UL);
	KUNIT_ASSERT_LE_MSG(test, result, x / result, "x=%lu", x);
	KUNIT_ASSERT_GT_MSG(test, result + 1, x / (result + 1), "x=%lu", x);
}

static void int_sqrt_small_domain(struct kunit *test)
{
	unsigned long x;

	for (x = 0; x < 65536; ++x)
		check_input(test, x);
}

static void int_sqrt_boundaries(struct kunit *test)
{
	unsigned long bit, square, root;
	unsigned int i;

	check_input(test, ULONG_MAX);
	check_input(test, ULONG_MAX - 1);
	for (i = 0; i < BITS_PER_LONG; ++i) {
		bit = 1UL << i;
		check_input(test, bit - 1);
		check_input(test, bit);
		check_input(test, bit + 1);
	}
	/* Squares near the largest representable root, not only small values. */
	root = (1UL << (BITS_PER_LONG / 2)) - 1;
	for (i = 0; i < 4096; ++i, --root) {
		square = root * root;
		check_input(test, square - 1);
		check_input(test, square);
		check_input(test, square + 1);
	}
}

static void int_sqrt_differential(struct kunit *test)
{
	u64 state = 0x6a09e667f3bcc909ULL;
	unsigned int i;

	/* Deterministic corpus spans the full native input width on each target. */
	for (i = 0; i < 65536; ++i) {
		state ^= state << 13;
		state ^= state >> 7;
		state ^= state << 17;
		check_input(test, (unsigned long)state);
	}
}

#if BITS_PER_LONG < 64
static u32 reference_int_sqrt64(u64 x)
{
	u64 b, m, y = 0;

	if (x <= ULONG_MAX)
		return reference_int_sqrt((unsigned long)x);

	m = 1ULL << ((fls64(x) - 1) & ~1ULL);
	while (m != 0) {
		b = y + m;
		y >>= 1;
		if (x >= b) {
			x -= b;
			y += m;
		}
		m >>= 2;
	}
	return y;
}

static void check_input64(struct kunit *test, u64 x)
{
	u32 result = int_sqrt64(x);
	u64 r = result;

	KUNIT_ASSERT_EQ_MSG(test, result, reference_int_sqrt64(x), "x=%llu", x);
	if (x == 0) {
		KUNIT_ASSERT_EQ(test, result, 0U);
		return;
	}
	KUNIT_ASSERT_NE(test, result, 0U);
	/* Kernel division helpers avoid compiler runtime calls on 32-bit targets. */
	KUNIT_ASSERT_LE_MSG(test, r, div64_u64(x, r), "x=%llu", x);
	KUNIT_ASSERT_GT_MSG(test, r + 1, div64_u64(x, r + 1), "x=%llu", x);
}

static void int_sqrt64_boundaries(struct kunit *test)
{
	u64 bit, square, root;
	unsigned int i;

	check_input64(test, 0);
	check_input64(test, 1);
	check_input64(test, 2);
	check_input64(test, (u64)ULONG_MAX - 1);
	check_input64(test, ULONG_MAX);
	check_input64(test, (u64)ULONG_MAX + 1);
	check_input64(test, U64_MAX - 1);
	check_input64(test, U64_MAX);
	for (i = 0; i < 64; ++i) {
		bit = 1ULL << i;
		check_input64(test, bit - 1);
		check_input64(test, bit);
		check_input64(test, bit + 1);
	}
	root = U32_MAX;
	for (i = 0; i < 4096; ++i, --root) {
		square = root * root;
		check_input64(test, square - 1);
		check_input64(test, square);
		check_input64(test, square + 1);
	}
}

static void int_sqrt64_differential(struct kunit *test)
{
	u64 state = 0x6a09e667f3bcc909ULL;
	unsigned int i;

	for (i = 0; i < 65536; ++i) {
		state ^= state << 13;
		state ^= state >> 7;
		state ^= state << 17;
		check_input64(test, state);
	}
}
#endif

static struct kunit_case int_sqrt_rusix_cases[] = {
	KUNIT_CASE(int_sqrt_small_domain),
	KUNIT_CASE(int_sqrt_boundaries),
	KUNIT_CASE(int_sqrt_differential),
#if BITS_PER_LONG < 64
	KUNIT_CASE(int_sqrt64_boundaries),
	KUNIT_CASE(int_sqrt64_differential),
#endif
	{}
};

static struct kunit_suite int_sqrt_rusix_suite = {
	.name = "rusix-int-sqrt-compatibility",
	.test_cases = int_sqrt_rusix_cases,
};

kunit_test_suite(int_sqrt_rusix_suite);
MODULE_DESCRIPTION("rusix integer square root compatibility tests");
MODULE_LICENSE("GPL");
