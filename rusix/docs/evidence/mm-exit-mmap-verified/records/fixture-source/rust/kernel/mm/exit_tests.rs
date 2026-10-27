// SPDX-License-Identifier: GPL-2.0-only
//! Native mapping teardown; worker references protect all asynchronous lifetime.
use crate::{bindings, ffi::c_void, prelude::*};

/// One controller reference; never exposes the foreign MM, VMA or file.
struct Fixture(*mut c_void);
impl Fixture {
    fn new(mode: u32) -> Result<Self> {
        // SAFETY: The C constructor validates the mode and returns exactly one
        // controller ref, with a separate worker ref obtained before publication.
        // ERR_PTR carries no ownership. No foreign reference is formed here.
        Ok(Self(crate::error::from_err_ptr(unsafe {
            bindings::exit_test_start(mode)
        })?))
    }

    fn observe(&self) -> Result<[i64; 16]> {
        // SAFETY: Our controller ref pins the completion through this finite
        // wait. Timeout does not cancel or reclaim a worker's resources.
        if !unsafe { bindings::exit_test_wait(self.0, 10000) } {
            return Err(ETIMEDOUT);
        }
        let mut out = [0; 16];
        // SAFETY: Successful completion observes immutable result publication.
        // C writes exactly 16 s64s into this live, suitably aligned output array.
        // Acknowledgement is not a task join; the separate worker ref protects
        // its remaining complete-to-return accesses independently of ours.
        unsafe { bindings::exit_test_result(self.0, out.as_mut_ptr()) };
        Ok(out)
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        // SAFETY: Release our one reference only. A blocked or failed worker
        // keeps its fixture/MM/file/task refs; this drop never runs teardown or
        // joins a worker. The private file's callbacks cannot outlive its ref.
        unsafe { bindings::exit_test_put(self.0) };
    }
}

#[macros::kunit_tests(rusix_exit_mmap)]
mod tests {
    use super::*;

    fn run(mode: u32) -> Result<[i64; 16]> {
        let fixture = Fixture::new(mode)?;
        let result = fixture.observe();
        // KUnit assertions may terminate without unwinding. Release controller
        // ownership before propagating errors or asserting any literal oracle.
        drop(fixture);
        let r = result?;
        assert_eq!(r[0], 0);
        assert_eq!(r[1], 2); // Explicit mmgrab, before any MM adoption.
        assert_eq!(r[10], 0); // Final users consumed.
        assert_eq!(&r[12..15], &[1, 1, 1]); // Empty tree, live storage, cleanup.
        assert_eq!(r[15], 0); // Reserved output remains untouched.
        Ok(r)
    }

    fn mapped(r: &[i64; 16]) {
        // Initial file refs; primary/poison closes; callback file identity;
        // callback refcount; close-before-release; release count/order.
        assert_eq!(&r[2..10], &[2, 1, 0, 1, 2, 1, 1, 1]);
        // Native lazy-TLB refs can survive unuse_mm or be lent to another
        // kthread. We own one retained count, not exclusive storage ownership.
        assert!(r[11] >= 1);
    }

    #[test]
    fn empty_final_users_retains_storage() -> Result {
        let r = run(0)?;
        assert_eq!(&r[2..10], &[0; 8]);
        assert_eq!(r[11], 1); // This MM was never adopted or published to a CPU.
        Ok(())
    }

    #[test]
    fn mapped_final_users_closes_before_file_put() -> Result {
        let r = run(1)?;
        mapped(&r);
        Ok(())
    }

    #[test]
    fn fixed_replace_close_dummy_reset() -> Result {
        let r = run(2)?;
        mapped(&r);
        Ok(())
    }
}
