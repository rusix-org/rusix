// SPDX-License-Identifier: GPL-2.0-only
//! RCU sync protocol observations from retained, private process workers.
use crate::{bindings, ffi::c_void, prelude::*};
struct Fixture(*mut c_void);
impl Fixture {
    fn new(mode: u32) -> Result<Self> {
        // SAFETY: C returns one controller reference to final-address storage;
        // every worker independently retains it through its last access.
        Ok(Self(crate::error::from_err_ptr(unsafe {
            bindings::rcusync_start(mode)
        })?))
    }
    fn wait(&self) -> bool {
        // SAFETY: Sleepable controller, finite wait; no RCU barrier here.
        unsafe { bindings::rcusync_wait(self.0, 20000) }
    }
    unsafe fn result(&self) -> [i64; 16] {
        let mut out = [0; 16];
        // SAFETY: Caller observed exact orchestrator completion. All participant
        // writes completed before its publication; destination has 16 elements.
        unsafe { bindings::rcusync_result(self.0, out.as_mut_ptr()) };
        out
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        // SAFETY: Repeated release is safe. Drop releases only this reference;
        // timed-out workers and uncertain teardown retain storage and taskrefs.
        unsafe {
            bindings::rcusync_release(self.0);
            bindings::rcusync_put(self.0);
        }
    }
}
#[macros::kunit_tests(rusix_rcu_sync)]
mod tests {
    use super::*;
    fn run(mode: u32) -> Result<[i64; 16]> {
        let f = Fixture::new(mode)?;
        let done = f.wait();
        // SAFETY: Only the completion-success branch reads published results.
        let result = if done { unsafe { f.result() } } else { [0; 16] };
        // KUnit assertions may terminate a test without unwinding Rust locals.
        // Release controller ownership before any assertion, including timeout.
        drop(f);
        assert!(done);
        if !done {
            return Err(ETIMEDOUT);
        }
        assert_eq!(result[0], 0);
        assert_eq!(&result[1..4], &[0, 0, 1]);
        assert_eq!(&result[12..], &[0, 0, 0, 1]);
        Ok(result)
    }
    #[test]
    fn initializer_and_nested_public_protocol() -> Result {
        let r = run(0)?;
        assert_eq!(&r[4..12], &[2, 1, 2, 2, 2, 1, 1, 1]);
        Ok(())
    }
    #[test]
    fn held_reader_blocks_first_and_queued_enter() -> Result {
        let r = run(1)?;
        assert_eq!(&r[4..10], &[1, 1, 1, 0, 1, 2]);
        Ok(())
    }
    #[test]
    fn exit_reuse_replay_and_worker_destructor() -> Result {
        let r = run(2)?;
        assert_eq!(&r[4..12], &[3, 0, 3, 1, 4, 0, 0, 0]);
        Ok(())
    }
    #[test]
    fn synthetic_callback_state_transitions() -> Result {
        let r = run(3)?;
        assert_eq!(&r[4..12], &[3, 0, 2, 1, 0, 0, 3, 0]);
        Ok(())
    }
    #[test]
    fn percpu_rwsem_reader_writer_handoff() -> Result {
        let r = run(4)?;
        assert_eq!(&r[6..11], &[1, 0, 1, 1, 0x1234]);
        Ok(())
    }
}
