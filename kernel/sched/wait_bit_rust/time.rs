// SPDX-License-Identifier: GPL-2.0-only
//! Pure arithmetic used by production wait-bit deadlines and shared tests.
// Match bindgen/kernel FFI aliases (long=isize, unsigned long=usize).
use kernel::ffi::{c_long, c_ulong};

/// Exact time_after_eq rule; meaningful time ordering assumes half-range limits.
pub(crate) const fn deadline_expired(now: c_ulong, deadline: c_ulong) -> bool {
    now.wrapping_sub(deadline) as c_long >= 0
}

/// Original unsigned subtraction converted to schedule_timeout's signed long.
pub(crate) const fn remaining_interval(deadline: c_ulong, now: c_ulong) -> c_long {
    deadline.wrapping_sub(now) as c_long
}

/// Absolute deadline construction retains unsigned jiffies wraparound.
pub(crate) const fn deadline_after(now: c_ulong, timeout: c_ulong) -> c_ulong {
    now.wrapping_add(timeout)
}
