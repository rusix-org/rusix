// SPDX-License-Identifier: GPL-2.0
// Copyright (C) 2013 Davidlohr Bueso <davidlohr.bueso@hp.com>
// Rust translation of int_sqrt.c, based on Guy L. Steele's shift/subtract algorithm.

//! Integer square root with the existing Linux C ABI.

use core::ffi::c_ulong;

/// Computes floor(sqrt(x)) for every unsigned-long input, without allocation.
// SAFETY: Kbuild selects this definition instead of int_sqrt.c when Rust is
// enabled. Its signature matches include/linux/math.h; there is one definition.
#[unsafe(no_mangle)]
pub extern "C" fn int_sqrt(mut x: c_ulong) -> c_ulong {
    if x <= 1 {
        return x;
    }

    let mut y: c_ulong = 0;
    let highest_bit = c_ulong::BITS
        .wrapping_sub(1)
        .wrapping_sub(x.leading_zeros());
    let mut m = (1 as c_ulong).wrapping_shl(highest_bit & !1);
    while m != 0 {
        // Explicit wrapping preserves C unsigned arithmetic even with Rust
        // overflow checks enabled, without introducing an early-boot panic path.
        let b = y.wrapping_add(m);
        y >>= 1;
        if x >= b {
            x = x.wrapping_sub(b);
            y = y.wrapping_add(m);
        }
        m >>= 2;
    }
    y
}

/// Computes floor(sqrt(x)) for 64-bit inputs on 32-bit architectures.
// SAFETY: On 32-bit targets this is the sole definition of the C ABI declared
// in include/linux/math.h. The 64-bit ABI uses that header's inline wrapper.
#[cfg(target_pointer_width = "32")]
#[unsafe(no_mangle)]
pub extern "C" fn int_sqrt64(mut x: u64) -> u32 {
    if x <= c_ulong::MAX as u64 {
        return int_sqrt(x as c_ulong) as u32;
    }

    let mut y: u64 = 0;
    let highest_bit = 63u32.wrapping_sub(x.leading_zeros());
    let mut m = 1u64.wrapping_shl(highest_bit & !1);
    while m != 0 {
        let b = y.wrapping_add(m);
        y >>= 1;
        if x >= b {
            x = x.wrapping_sub(b);
            y = y.wrapping_add(m);
        }
        m >>= 2;
    }
    y as u32
}
