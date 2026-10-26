// SPDX-License-Identifier: GPL-2.0-or-later
// Translation of Linux 6.18.58 kernel/rcu/sync.c.
// Copyright (c) 2015, Red Hat, Inc.
// Original author: Oleg Nesterov <oleg@redhat.com>.

//! Reader fast-path gating through the original RCU sync state machine.
//!
//! Storage remains C-owned and address-stable through explicit destruction.
//! Foreign scalar accesses retain their plain/marked C operations; no Atomic
//! overlay or shared/exclusive Rust reference is created. The GP engine, locks,
//! wait-entry initializer and macro primitives remain unfinished C dependencies.
//! This module provides no safe storage-ownership or sleepable Drop interface.

use bindings::{
    rcu_sync_read_int as read_int, rcu_sync_read_int_once as read_int_once,
    rcu_sync_write_int as write_int, rcu_sync_write_int_once as write_int_once,
};
use core::ptr::addr_of_mut;
use kernel::{
    bindings::{self, rcu_sync as Sync},
    ffi::c_int,
    types::Opaque,
};
use pin_init::stack_pin_init;

// Exact private enum from pinned sync.c; these are not public header constants.
const GP_IDLE: c_int = 0;
const GP_ENTER: c_int = 1;
const GP_PASSED: c_int = 2;
const GP_EXIT: c_int = 3;
const GP_REPLAY: c_int = 4;

/// # Safety
/// Caller owns exclusive uninitialized/quiescent storage at its final address.
/// Previous locks, waiters, callbacks and readers must no longer access it.
// SAFETY: Selected unique definition preserves the original pointer/void C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_sync_init(rsp: *mut Sync) {
    // SAFETY: Exclusive writable byte storage; reproduce original memset including
    // padding before initializing the lock. Never read an uninitialized struct.
    unsafe { core::ptr::write_bytes(rsp.cast::<u8>(), 0, core::mem::size_of::<Sync>()) };
    // SAFETY: Fully zeroed final-address storage; helper preserves queue's original
    // init macro name and permanent lock-class key, including !LOCKDEP behavior.
    unsafe { bindings::rcu_sync_wait_init(rsp) };
}

/// # Safety
/// Caller serializes state with gp_wait.lock and holds the object at its final
/// address through callback completion/replay and eventual rcu_sync_dtor. The
/// embedded callback is not already queued except in its own replay invocation.
unsafe fn submit(rsp: *mut Sync) {
    // SAFETY: This exact callback recovers the containing retained object. No
    // owned reference is acquired; original caller lifetime remains mandatory.
    unsafe { bindings::rcu_sync_hurry(addr_of_mut!((*rsp).cb_head), Some(rcu_sync_func)) };
}

/// # Safety
/// Head names a live Sync.cb_head at its original address. This is either the
/// corresponding queued RCU callback or the first entrant's synchronous call
/// after synchronize_rcu. Caller retains the object until callback/replay ends.
unsafe extern "C" fn rcu_sync_func(head: *mut bindings::callback_head) {
    // SAFETY: Caller supplies the embedded field of the same live container.
    let rsp = unsafe { kernel::container_of!(head, Sync, cb_head) };
    // SAFETY: All scalar observations remain in C; count/state mutations use the
    // embedded ordinary spinlock. irqsave preserves callback OR process context.
    unsafe {
        let state = addr_of_mut!((*rsp).gp_state);
        let count = addr_of_mut!((*rsp).gp_count);
        let queue = addr_of_mut!((*rsp).gp_wait);
        let lock = addr_of_mut!((*queue).lock);
        bindings::rcu_sync_warn_callback_idle(read_int_once(state) == GP_IDLE);
        bindings::rcu_sync_warn_callback_passed(read_int_once(state) == GP_PASSED);
        let flags = bindings::wait_spin_lock_irqsave(lock);
        if read_int(count) != 0 {
            write_int_once(state, GP_PASSED);
            bindings::__wake_up_locked(queue, bindings::TASK_NORMAL, 1);
        } else if read_int(state) == GP_REPLAY {
            write_int_once(state, GP_EXIT);
            submit(rsp);
        } else {
            write_int_once(state, GP_IDLE);
        }
        bindings::wait_spin_unlock_irqrestore(lock, flags);
    }
    // No access after final unlock: destruction may proceed once it is observed.
}

/// # Safety
/// Retained initialized address-stable object; current task may sleep, IRQs are
/// enabled, and no lock held here may be needed by the wait/GP machinery. Each
/// successful entry must be paired with exit; destruction excludes new entrants.
// SAFETY: Selected unique definition preserves the original pointer/void C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_sync_enter(rsp: *mut Sync) {
    // SAFETY: Raw projections only; caller retains this storage throughout waiting.
    let (state, count, queue, lock) = unsafe {
        let queue = addr_of_mut!((*rsp).gp_wait);
        (
            addr_of_mut!((*rsp).gp_state),
            addr_of_mut!((*rsp).gp_count),
            queue,
            addr_of_mut!((*queue).lock),
        )
    };
    // SAFETY: Exact IRQ-enabled entry contract: lock_irq/unlock_irq, not irqsave.
    let previous = unsafe {
        bindings::wait_spin_lock_irq(lock);
        let previous = read_int(state);
        if previous == GP_IDLE {
            write_int_once(state, GP_ENTER);
            bindings::rcu_sync_warn_enter_count(read_int(count) != 0);
        }
        write_int(count, read_int(count).wrapping_add(1));
        bindings::wait_spin_unlock_irq(lock);
        previous
    };
    if previous == GP_IDLE {
        // SAFETY: Sleepable caller; this first entrant waits for an actual GP,
        // then synchronously applies the same callback transition before return.
        unsafe {
            bindings::synchronize_rcu();
            rcu_sync_func(addr_of_mut!((*rsp).cb_head));
        }
        return;
    }

    // Exact wait_event expansion: might_sleep then initial condition test. There
    // is no waiter or finish_wait if this initial observation is already true.
    // SAFETY: Sleepability check and marked state observation on retained storage.
    unsafe { bindings::rcu_sync_might_sleep() };
    if unsafe { read_int_once(state) } >= GP_PASSED {
        return;
    }
    stack_pin_init!(let waiter = Opaque::ffi_init(|entry: *mut bindings::wait_queue_entry| {
        // SAFETY: Exclusive uninitialized final-address local. init_wait_entry
        // supplies current, autoremove callback, zero flags and self-links.
        unsafe { bindings::init_wait_entry(entry, 0) };
    }));
    loop {
        // SAFETY: Pinned waiter and queue live until finish. This constant
        // uninterruptible mode has no signal-error branch in ___wait_event.
        unsafe {
            bindings::prepare_to_wait_event(
                queue,
                waiter.get(),
                bindings::TASK_UNINTERRUPTIBLE as c_int,
            );
        }
        // SAFETY: First loop condition follows preparation, exactly as C.
        if unsafe { read_int_once(state) } >= GP_PASSED {
            break;
        }
        // SAFETY: No queue lock held; prepare installed current's sleep state.
        unsafe { bindings::schedule() };
        // SAFETY: Baseline macro tests again after schedule, before re-preparing.
        if unsafe { read_int_once(state) } >= GP_PASSED {
            break;
        }
    }
    // SAFETY: Waiter remains pinned until restored RUNNING and detached; current
    // task does not return or expose stack storage before this mandatory cleanup.
    unsafe { bindings::finish_wait(queue, waiter.get()) };
}

/// # Safety
/// Retained live object and matching entry; incoming IRQs enabled, ordinary lock
/// may be acquired. Object must outlive pending callback/replay and later dtor.
// SAFETY: Selected unique definition preserves the original pointer/void C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_sync_exit(rsp: *mut Sync) {
    // SAFETY: Caller retains object. Count is serialized, state retains mixed C
    // access protocol. Invalid-count warnings do not change original arithmetic.
    unsafe {
        let state = addr_of_mut!((*rsp).gp_state);
        let count = addr_of_mut!((*rsp).gp_count);
        let lock = addr_of_mut!((*rsp).gp_wait.lock);
        bindings::rcu_sync_warn_exit_idle(read_int_once(state) == GP_IDLE);
        bindings::wait_spin_lock_irq(lock);
        bindings::rcu_sync_warn_exit_count(read_int(count) == 0);
        let remaining = read_int(count).wrapping_sub(1);
        write_int(count, remaining);
        if remaining == 0 {
            if read_int(state) == GP_PASSED {
                write_int_once(state, GP_EXIT);
                submit(rsp);
            } else if read_int(state) == GP_EXIT {
                write_int_once(state, GP_REPLAY);
            }
        }
        bindings::wait_spin_unlock_irq(lock);
    }
}

/// # Safety
/// Process-context sleepable teardown with IRQs enabled, no remaining matched
/// entries and no concurrent/new users. Storage remains live until this call
/// drains callbacks; this is explicit teardown, not a context-independent Drop.
// SAFETY: Selected unique definition preserves the original pointer/void C ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn rcu_sync_dtor(rsp: *mut Sync) {
    // SAFETY: External lifetime exclusion plus embedded lock serialize callback
    // transition. Final plain state observation follows the original RCU barrier.
    unsafe {
        let state = addr_of_mut!((*rsp).gp_state);
        let count = addr_of_mut!((*rsp).gp_count);
        let lock = addr_of_mut!((*rsp).gp_wait.lock);
        bindings::rcu_sync_warn_dtor_passed(read_int_once(state) == GP_PASSED);
        bindings::wait_spin_lock_irq(lock);
        bindings::rcu_sync_warn_dtor_count(read_int(count) != 0);
        if read_int(state) == GP_REPLAY {
            write_int_once(state, GP_EXIT);
        }
        let previous = read_int(state);
        bindings::wait_spin_unlock_irq(lock);
        if previous != GP_IDLE {
            bindings::rcu_barrier();
            bindings::rcu_sync_warn_dtor_idle(read_int(state) != GP_IDLE);
        }
    }
}
