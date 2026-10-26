// SPDX-License-Identifier: GPL-2.0-only
//! Literal batch observations; all callbacks/barriers run on retained C workers.
use crate::{bindings, ffi::c_void, prelude::*};

struct Fixture(*mut c_void);
impl Fixture {
    fn start(mode: u32) -> Result<Self> {
        // SAFETY: Private modes 0..=6; C returns one controller reference to a
        // stable allocation. Workers/callbacks retain independent references.
        Ok(Self(crate::error::from_err_ptr(unsafe {
            bindings::rcubatch_start(mode)
        })?))
    }
    fn wait(&self) -> bool {
        // SAFETY: Retained completion storage; finite sleepable controller wait.
        // RCU barriers never execute in this KUnit controller task.
        unsafe { bindings::rcubatch_wait(self.0, 15000) }
    }
    unsafe fn result(&self) -> [i64; 16] {
        let mut out = [0; 16];
        // SAFETY: Caller observed the exact worker acknowledgment. Plain result
        // fields are immutable after that publication; output has 16 slots.
        unsafe { bindings::rcubatch_result(self.0, out.as_mut_ptr()) };
        out
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        // SAFETY: Drop only the controller ref. Timeout leaves worker/callback
        // storage alive. The held reader has its own finite release deadline.
        unsafe { bindings::rcubatch_put(self.0) };
    }
}

#[macros::kunit_tests(rusix_rcu_batch)]
mod tests {
    use super::*;

    fn run(mode: u32, expected: [i64; 16]) -> Result {
        let fixture = Fixture::start(mode)?;
        let done = fixture.wait();
        let observed = if done {
            // SAFETY: Exact worker completion precedes result reads.
            unsafe { fixture.result() }
        } else {
            [-1; 16]
        };
        // KUnit assertions can abort without Rust unwinding: release first.
        drop(fixture);
        assert!(done);
        assert_eq!(observed, expected);
        Ok(())
    }

    #[test]
    fn private_empty_and_fifo_accounting() -> Result {
        run(0, [0, 3, 3, 0, 0, 0, 0, 1, 0, 0, 3, 1, 3, 0, 0, 0])
    }

    #[test]
    fn private_time_check_boundaries() -> Result {
        // Includes LONG_MIN/-1 deadlines: u64 clock comparison is false, not
        // signed clock >= negative deadline. These occupy result slots8/9.
        run(1, [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    }

    #[test]
    fn held_reader_payload_before_barrier() -> Result {
        run(2, [0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0])
    }

    #[test]
    fn self_free_callback_final_access() -> Result {
        run(3, [0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    }

    #[test]
    fn self_requeue_once_before_second_barrier() -> Result {
        run(4, [0, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0])
    }

    #[test]
    fn flood_exact_once_before_barrier() -> Result {
        run(5, [0, 129, 129, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    }
    #[test]
    fn softirq_count_budget_reinserts_done_before_pending() -> Result {
        run(6, [0, 3, 3, 0, 1, 2, 1, 1, 2, 1, 1, 1, 1, 0, 3, 1])
    }
}
