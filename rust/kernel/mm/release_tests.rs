// SPDX-License-Identifier: GPL-2.0-only
//! Real MM lifecycle observations; only the retained worker performs teardown.
use crate::{bindings, ffi::c_void, prelude::*};

struct Fixture(*mut c_void);
impl Fixture {
    fn new(mode: u32) -> Result<Self> {
        // SAFETY: Returns one controller ref; the worker owns a separate ref
        // through its last access, including the completion-to-return interval.
        Ok(Self(crate::error::from_err_ptr(unsafe {
            bindings::mm_test_start(mode)
        })?))
    }
    fn wait(&self) -> bool {
        // SAFETY: Controller reference pins the completion; finite wait only.
        unsafe { bindings::mm_test_wait(self.0, 10000) }
    }
    unsafe fn result(&self) -> [i64; 18] {
        let mut out = [0; 18];
        // SAFETY: Caller observed worker completion; result is then immutable.
        // The destination has exactly the 18 elements written by the C bridge.
        unsafe { bindings::mm_test_result(self.0, out.as_mut_ptr()) };
        out
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        // SAFETY: Releases only controller ownership. Blocked workers retain
        // fixture/MM/taskrefs; no blocking cleanup is performed by this drop.
        unsafe { bindings::mm_test_put(self.0) };
    }
}

#[macros::kunit_tests(rusix_mm_release)]
mod tests {
    use super::*;
    fn run(mode: u32) -> Result<[i64; 18]> {
        let f = Fixture::new(mode)?;
        let done = f.wait();
        // SAFETY: Results are read only after this exact worker acknowledges.
        let r = if done { unsafe { f.result() } } else { [0; 18] };
        // Assertions may terminate KUnit without unwinding; drop first.
        drop(f);
        assert!(done);
        if !done {
            return Err(ETIMEDOUT);
        }
        assert_eq!(&r[..3], &[0, 1, 1]);
        assert_eq!(r[16], 1);
        Ok(r)
    }
    fn released_mapping(r: &[i64; 18]) {
        assert_eq!(r[3], 1);
        assert_eq!(&r[10..15], &[0, 1, 1, 1, 1]);
    }
    #[test]
    fn nonfinal_users_preserve_stack_vma() -> Result {
        let r = run(0)?;
        assert_eq!(&r[4..10], &[1, 2, 1, 1, 2, 1]);
        released_mapping(&r);
        Ok(())
    }
    #[test]
    fn final_users_preserve_retained_storage() -> Result {
        let r = run(1)?;
        released_mapping(&r);
        Ok(())
    }
    #[test]
    fn atomic_async_final_release_drains_work() -> Result {
        let r = run(2)?;
        released_mapping(&r);
        assert_eq!(r[15], 1);
        assert_eq!(r[17], 1);
        Ok(())
    }
    #[test]
    fn fresh_exec_style_storage_drop_accepts_live_users() -> Result {
        let r = run(3)?;
        assert_eq!(&r[3..16], &[0; 13]);
        Ok(())
    }
}
