// SPDX-License-Identifier: GPL-2.0
#[path = "../../lib/math/int_sqrt_rust.rs"]
mod replacement;

unsafe extern "C" {
    fn upstream_int_sqrt(x: core::ffi::c_ulong) -> core::ffi::c_ulong;
    #[cfg(target_pointer_width = "32")]
    fn upstream_int_sqrt64(x: u64) -> u32;
}

fn check(x: core::ffi::c_ulong) {
    let actual = replacement::int_sqrt(x);
    // SAFETY: the linked reference takes/returns unsigned long, touches no
    // memory and accepts every representable input.
    assert_eq!(actual, unsafe { upstream_int_sqrt(x) }, "input {x}");
    let r = actual as u128;
    assert!(r * r <= x as u128, "lower bound at {x}");
    assert!((r + 1) * (r + 1) > x as u128, "upper bound at {x}");
}

#[test]
fn small_domain() {
    for x in 0..1_000_000 {
        check(x);
    }
}

#[test]
fn full_width_corpus() {
    let mut state = 0x6a09e667f3bcc909u64;
    for _ in 0..1_000_000 {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        check(state as core::ffi::c_ulong);
    }
}

#[test]
fn boundaries() {
    use core::ffi::c_ulong;
    check(c_ulong::MAX);
    check(c_ulong::MAX - 1);
    for bit in 0..c_ulong::BITS {
        let n = (1 as c_ulong) << bit;
        check(n - 1);
        check(n);
        check(n + 1);
    }
    let largest_root = ((1 as c_ulong) << (c_ulong::BITS / 2)) - 1;
    for root in largest_root - 4095..=largest_root {
        let square = root * root;
        check(square - 1);
        check(square);
        check(square + 1);
    }
}

#[cfg(target_pointer_width = "32")]
fn check64(x: u64) {
    let actual = replacement::int_sqrt64(x);
    // SAFETY: the pinned C reference accepts every u64 input, returns u32,
    // and neither accesses memory nor relies on external initialization.
    assert_eq!(actual, unsafe { upstream_int_sqrt64(x) }, "u64 input {x}");
    let r = actual as u128;
    assert!(r * r <= x as u128, "u64 lower bound at {x}");
    assert!((r + 1) * (r + 1) > x as u128, "u64 upper bound at {x}");
}

#[cfg(target_pointer_width = "32")]
#[test]
fn int_sqrt64_boundaries() {
    let threshold = core::ffi::c_ulong::MAX as u64;
    for x in [
        0,
        1,
        2,
        threshold - 1,
        threshold,
        threshold + 1,
        u64::MAX - 1,
        u64::MAX,
    ] {
        check64(x);
    }
    for bit in 0..64 {
        let n = 1u64 << bit;
        check64(n - 1);
        check64(n);
        check64(n + 1);
    }
    let largest_root = u32::MAX as u64;
    for root in largest_root - 4095..=largest_root {
        let square = root * root;
        check64(square - 1);
        check64(square);
        check64(square + 1);
    }
}

#[cfg(target_pointer_width = "32")]
#[test]
fn int_sqrt64_full_width_corpus() {
    let mut state = 0x6a09e667f3bcc909u64;
    for _ in 0..1_000_000 {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        check64(state);
    }
}
