// SPDX-License-Identifier: GPL-2.0-only
//! Literal list-state oracles; these private descriptors never enter global RCU.
use crate::{bindings, ffi::c_void, prelude::*};
struct Fixture(*mut c_void);
impl Fixture {
    fn new() -> Result<Self> {
        // SAFETY: Sleepable controller; C returns one stable owned allocation.
        Ok(Self(crate::error::from_err_ptr(unsafe {
            bindings::rculist_alloc()
        })?))
    }
    fn action(&self, op: u32, dst: u32, src: u32, node: u32, value: u64) -> i64 {
        // SAFETY: Private tests supply in-range identifiers and legal operations;
        // C retains all descriptors/nodes at final addresses until Fixture drop.
        unsafe { bindings::rculist_action(self.0, op, dst, src, node, value) }
    }
    fn seg(&self, which: u32) -> [i64; 34] {
        let mut out = [0; 34];
        // SAFETY: Private valid descriptor index and writable complete output.
        unsafe { bindings::rculist_snapshot(self.0, which, out.as_mut_ptr()) };
        out
    }
    fn simple(&self, which: u32) -> [i64; 19] {
        let mut out = [0; 19];
        // SAFETY: Same stable private context; bounded C observer checks IDs.
        unsafe { bindings::rculist_simple(self.0, which, out.as_mut_ptr()) };
        out
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        // SAFETY: Sole owner, no callbacks submitted to any external subsystem.
        unsafe { bindings::rculist_free(self.0) };
    }
}
struct Runtime(*mut c_void);
impl Runtime {
    fn new(mode: u32) -> Result<Self> {
        // SAFETY: C owns worker/callback references; this receives one controller
        // reference. No experimental guest callback executes on a host kernel.
        Ok(Self(crate::error::from_err_ptr(unsafe {
            bindings::rculist_runtime_start(mode)
        })?))
    }
    fn release(&self) {
        // SAFETY: Retained context; repeatable completion releases SRCU reader.
        unsafe { bindings::rculist_runtime_release(self.0) };
    }
    fn wait(&self) -> bool {
        // SAFETY: Sleepable controller, finite ten-second wait; timeout retains
        // worker and callback ownership rather than freeing callback storage.
        unsafe { bindings::rculist_runtime_wait(self.0, 10000) }
    }
    unsafe fn result(&self) -> [i64; 5] {
        let mut out = [0; 5];
        // SAFETY: Caller observed exact worker completion after all plain writes.
        unsafe { bindings::rculist_runtime_result(self.0, out.as_mut_ptr()) };
        out
    }
}
impl Drop for Runtime {
    fn drop(&mut self) {
        self.release();
        // SAFETY: Releases only controller's reference. C workers and callbacks
        // retain their own references, including after a bounded wait times out.
        unsafe { bindings::rculist_runtime_put(self.0) };
    }
}

#[macros::kunit_tests(rusix_rcu_list)]
mod tests {
    use super::*;
    fn op(f: &Fixture, code: u32, dst: u32, src: u32, node: u32, value: u64) {
        assert_eq!(f.action(code, dst, src, node, value), 0);
    }
    fn enqueue(f: &Fixture, dst: u32, node: u32) {
        op(f, 2, dst, 0, node, 0);
    }
    fn accelerate(f: &Fixture, dst: u32, seq: u64) {
        assert_eq!(f.action(4, dst, 0, 0, seq), 1);
    }
    fn advance(f: &Fixture, dst: u32, seq: u64) {
        op(f, 5, dst, 0, 0, seq);
    }
    fn seg(f: &Fixture, which: u32, fields: [i64; 17], order: &[i64]) {
        let observed = f.seg(which);
        assert_eq!(&observed[..17], &fields);
        assert_eq!(observed[33], order.len() as i64);
        let mut expected = [0; 16];
        for (slot, id) in expected.iter_mut().zip(order.iter()) {
            *slot = *id;
        }
        assert_eq!(&observed[17..33], &expected);
    }
    fn simple(f: &Fixture, which: u32, len: i64, tail: i64, order: &[i64]) {
        let observed = f.simple(which);
        assert_eq!(observed[0], len);
        assert_eq!(observed[1], tail);
        assert_eq!(observed[18], order.len() as i64);
        let mut expected = [0; 16];
        for (slot, id) in expected.iter_mut().zip(order.iter()) {
            *slot = *id;
        }
        assert_eq!(&observed[2..18], &expected);
    }
    fn four(f: &Fixture) {
        enqueue(f, 0, 1);
        accelerate(f, 0, 5);
        advance(f, 0, 5);
        enqueue(f, 0, 2);
        accelerate(f, 0, 10);
        enqueue(f, 0, 3);
        accelerate(f, 0, 20);
        enqueue(f, 0, 4);
    }
    #[test]
    fn simple_fifo_and_both_flush_forms_preserve_tail_identity() -> Result {
        let f = Fixture::new()?;
        simple(&f, 0, 0, 0, &[]);
        assert_eq!(f.action(16, 0, 0, 0, 0), 0);
        op(&f, 15, 0, 0, 1, 0);
        op(&f, 15, 0, 0, 2, 0);
        op(&f, 15, 1, 0, 3, 0);
        op(&f, 17, 1, 0, 4, 0);
        simple(&f, 1, 2, 2, &[1, 2]);
        simple(&f, 0, 1, 4, &[4]);
        assert_eq!(f.action(16, 1, 0, 0, 0), 1);
        assert_eq!(f.action(16, 1, 0, 0, 0), 2);
        simple(&f, 1, 0, 0, &[]);
        op(&f, 17, 1, 0, 0, 0);
        simple(&f, 0, 0, 0, &[]);
        simple(&f, 1, 1, 4, &[4]);
        op(&f, 17, 1, 0, 0, 0);
        simple(&f, 1, 0, 0, &[]);
        Ok(())
    }
    #[test]
    fn init_flags_gp_sentinels_empty_queries_and_count_updates() -> Result {
        let f = Fixture::new()?;
        assert_eq!(f.action(0, 0, 0, 0, 0x80), 0x81);
        seg(
            &f,
            0,
            [0, 0, 129, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            &[],
        );
        assert_eq!(f.action(18, 0, 0, 0, 0x1234), -(bindings::ENOENT as i64));
        op(&f, 1, 0, 0, 0, 0);
        seg(
            &f,
            0,
            [0, 0, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            &[],
        );
        assert_eq!(f.action(0, 0, 0, 0, 0x80), 0x81);
        op(&f, 6, 0, 0, 0, 5);
        op(&f, 7, 0, 0, 0, 0);
        op(&f, 6, 0, 0, 0, (-6i64) as u64);
        for code in [8, 9, 10, 11, 12] {
            op(&f, code, 0, 0, 0, 0);
        }
        assert_eq!(f.action(4, 0, 0, 0, 0), 0);
        advance(&f, 0, 0);
        seg(
            &f,
            0,
            [0, 0, 129, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            &[],
        );
        Ok(())
    }
    #[test]
    fn four_segments_advance_compacts_and_accelerate_merges() -> Result {
        let f = Fixture::new()?;
        four(&f);
        seg(
            &f,
            0,
            [4, 4, 1, 1, 1, 1, 2, 1, 2, 3, 4, 1, 1, 1, 1, 10, 20],
            &[1, 2, 3, 4],
        );
        assert_eq!(f.action(18, 0, 0, 0, 99), 10);
        assert_eq!(f.action(4, 0, 0, 0, 30), 0);
        advance(&f, 0, 10);
        seg(
            &f,
            0,
            [4, 4, 1, 1, 1, 1, 3, 2, 3, 3, 4, 2, 1, 0, 1, 20, 0],
            &[1, 2, 3, 4],
        );
        accelerate(&f, 0, 15);
        seg(
            &f,
            0,
            [4, 4, 1, 1, 1, 1, 3, 2, 4, 4, 4, 2, 2, 0, 0, 15, 0],
            &[1, 2, 3, 4],
        );
        advance(&f, 0, 15);
        seg(
            &f,
            0,
            [4, 4, 1, 1, 0, 1, 0, 4, 4, 4, 4, 4, 0, 0, 0, 0, 0],
            &[1, 2, 3, 4],
        );
        Ok(())
    }
    #[test]
    fn done_extraction_partial_reinsertion_keeps_detached_accounting() -> Result {
        let f = Fixture::new()?;
        for id in [1, 2, 3] {
            enqueue(&f, 0, id);
        }
        accelerate(&f, 0, 5);
        advance(&f, 0, 5);
        enqueue(&f, 0, 4);
        op(&f, 8, 0, 0, 0, 0);
        simple(&f, 0, 3, 3, &[1, 2, 3]);
        seg(
            &f,
            0,
            [4, 1, 1, 0, 1, 4, 4, 0, 0, 0, 4, 0, 0, 0, 1, 0, 0],
            &[4],
        );
        assert_eq!(f.action(16, 0, 0, 0, 0), 1);
        op(&f, 6, 0, 0, 0, (-1i64) as u64);
        op(&f, 11, 0, 0, 0, 0);
        simple(&f, 0, 2, 0, &[]);
        seg(
            &f,
            0,
            [3, 3, 1, 1, 1, 2, 4, 3, 3, 3, 4, 2, 0, 0, 1, 0, 0],
            &[2, 3, 4],
        );
        Ok(())
    }
    #[test]
    fn pending_transfer_retains_source_descriptor_and_separate_count() -> Result {
        let f = Fixture::new()?;
        four(&f);
        op(&f, 9, 0, 0, 0, 0);
        seg(
            &f,
            0,
            [4, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
            &[1],
        );
        simple(&f, 0, 3, 4, &[2, 3, 4]);
        let before = f.simple(0);
        op(&f, 10, 1, 0, 0, 0);
        op(&f, 12, 1, 0, 0, 0);
        assert_eq!(f.simple(0), before);
        seg(
            &f,
            1,
            [3, 3, 1, 0, 1, 2, 2, 0, 0, 0, 4, 0, 0, 0, 3, 0, 0],
            &[2, 3, 4],
        );
        Ok(())
    }
    #[test]
    fn entrain_empty_head_with_positive_count_joins_done() -> Result {
        let f = Fixture::new()?;
        assert_eq!(f.action(3, 0, 0, 1, 0), 0);
        op(&f, 7, 0, 0, 0, 0);
        assert_eq!(f.action(3, 0, 0, 1, 0), 1);
        seg(
            &f,
            0,
            [2, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
            &[1],
        );
        op(&f, 6, 0, 0, 0, (-1i64) as u64);
        op(&f, 8, 0, 0, 0, 0);
        assert_eq!(f.action(16, 0, 0, 0, 0), 1);
        op(&f, 6, 0, 0, 0, (-1i64) as u64);
        seg(
            &f,
            0,
            [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            &[],
        );
        Ok(())
    }
    #[test]
    fn merge_under_cpu_lock_prepends_done_restarts_pending() -> Result {
        let f = Fixture::new()?;
        enqueue(&f, 0, 1);
        accelerate(&f, 0, 5);
        advance(&f, 0, 5);
        enqueue(&f, 0, 2);
        accelerate(&f, 0, 10);
        enqueue(&f, 1, 3);
        accelerate(&f, 1, 5);
        advance(&f, 1, 5);
        enqueue(&f, 1, 4);
        accelerate(&f, 1, 20);
        op(&f, 13, 0, 1, 0, 0);
        seg(
            &f,
            0,
            [4, 4, 1, 1, 1, 3, 2, 1, 2, 2, 4, 2, 1, 0, 1, 10, 0],
            &[3, 1, 2, 4],
        );
        seg(
            &f,
            1,
            [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            &[],
        );
        Ok(())
    }
    #[test]
    fn modular_gp_equality_wrap_and_half_range_ordering() -> Result {
        let f = Fixture::new()?;
        enqueue(&f, 0, 1);
        accelerate(&f, 0, u64::MAX - 3);
        enqueue(&f, 0, 2);
        accelerate(&f, 0, 0);
        enqueue(&f, 0, 3);
        advance(&f, 0, u64::MAX - 4);
        seg(
            &f,
            0,
            [3, 3, 1, 0, 1, 1, 1, 0, 1, 2, 3, 0, 1, 1, 1, -4, 0],
            &[1, 2, 3],
        );
        advance(&f, 0, u64::MAX - 3);
        accelerate(&f, 0, 0);
        advance(&f, 0, 0);
        seg(
            &f,
            0,
            [3, 3, 1, 1, 0, 1, 0, 3, 3, 3, 3, 3, 0, 0, 0, 0, 0],
            &[1, 2, 3],
        );
        enqueue(&f, 1, 4);
        accelerate(&f, 1, 0);
        advance(&f, 1, 1u64 << 63);
        seg(
            &f,
            1,
            [1, 1, 1, 0, 1, 4, 4, 0, 4, 4, 4, 0, 1, 0, 0, 0, 0],
            &[4],
        );
        advance(&f, 1, (1u64 << 63) - 1);
        seg(
            &f,
            1,
            [1, 1, 1, 1, 0, 4, 0, 4, 4, 4, 4, 1, 0, 0, 0, 0, 0],
            &[4],
        );
        Ok(())
    }
    #[test]
    fn real_call_rcu_two_cpu_payloads_complete_before_barrier_return() -> Result {
        let runtime = Runtime::new(0)?;
        let done = runtime.wait();
        // SAFETY: Result fields become immutable before this acknowledgment.
        let observed = if done {
            unsafe { runtime.result() }
        } else {
            [-1; 5]
        };
        drop(runtime);
        assert!(done);
        assert_eq!(observed, [0, 2, 3, 2, 3]);
        Ok(())
    }

    #[test]
    fn real_srcu_reader_blocks_callback_until_release_and_barrier() -> Result {
        use crate::time::{Delta, Instant, Monotonic};
        let runtime = Runtime::new(1)?;
        let start = Instant::<Monotonic>::now();
        let mut ready = false;
        while start.elapsed().as_millis() < 2000 {
            // SAFETY: Controller reference retains the atomic phase storage.
            if unsafe { bindings::rculist_runtime_phase(runtime.0) } == 1 {
                ready = true;
                break;
            }
            crate::time::delay::fsleep(Delta::from_millis(10));
        }
        // SAFETY: Atomic observation; the worker still holds its read-side lock
        // until our release or its five-second fallback deadline.
        let before = unsafe { bindings::rculist_runtime_count(runtime.0) };
        runtime.release();
        let done = runtime.wait();
        // SAFETY: Exact worker acknowledgment precedes all plain result reads.
        let observed = if done {
            unsafe { runtime.result() }
        } else {
            [-1; 5]
        };
        drop(runtime);
        assert!(ready && done && start.elapsed().as_millis() < 5000);
        assert_eq!(before, 0);
        assert_eq!(observed, [0, 1, 1, 1, 0]);
        Ok(())
    }
}
