# SPDX-License-Identifier: GPL-2.0-only
obj-y += div64.o gcd.o lcm.o int_log.o int_pow.o reciprocal_div.o

ifdef CONFIG_RUST
obj-y += int_sqrt_rust.o int_sqrt_exports.o
else
obj-y += int_sqrt.o
endif

obj-$(CONFIG_CORDIC)		+= cordic.o
obj-$(CONFIG_PRIME_NUMBERS)	+= prime_numbers.o
obj-$(CONFIG_RATIONAL)		+= rational.o

obj-$(CONFIG_TEST_DIV64)	+= test_div64.o
obj-$(CONFIG_TEST_MULDIV64)	+= test_mul_u64_u64_div_u64.o

obj-y += tests/
