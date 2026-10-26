// SPDX-License-Identifier: GPL-2.0
//! Host-only ownership/state experiment; no scheduler or kernel implementation.
//! Counter transitions follow Linux v6.18.58 kernel/sched/completion.c.
use std::sync::{Arc, Mutex};

#[derive(Default)]
struct Owner(Arc<Mutex<u32>>);

// A producer or waiter holds storage alive even after its initiating owner exits.
// This deliberately models allocated Rust callers, not C's stack layout.
#[derive(Clone)]
struct Endpoint(Arc<Mutex<u32>>);

impl Owner {
    fn endpoint(&self) -> Endpoint {
        Endpoint(self.0.clone())
    }

    // Exclusive owner access alone is insufficient: outstanding endpoints must
    // also be gone. No raw C handles exist in this restricted model.
    fn reset(&mut self) -> Result<(), ()> {
        let state = Arc::get_mut(&mut self.0).ok_or(())?;
        *state.get_mut().unwrap() = 0;
        Ok(())
    }
}

impl Endpoint {
    fn complete(&self) {
        let mut done = self.0.lock().unwrap();
        *done = done.saturating_add(1);
    }

    fn complete_all(&self) {
        *self.0.lock().unwrap() = u32::MAX;
    }

    // False means no token at this instant. It is neither a timeout result nor
    // a model of queue enrollment, scheduling, signals, or wait return codes.
    fn try_consume(&self) -> bool {
        let mut done = self.0.lock().unwrap();
        if *done == 0 {
            return false;
        }
        if *done != u32::MAX {
            *done -= 1;
        }
        true
    }
}

#[test]
fn counting_tokens_are_consumed_once() {
    let endpoint = Owner::default().endpoint();
    assert!(!endpoint.try_consume());
    endpoint.complete();
    endpoint.complete();
    assert!(endpoint.try_consume());
    assert!(endpoint.try_consume());
    assert!(!endpoint.try_consume());
}

#[test]
fn saturation_is_permanent_until_quiescent_reset() {
    let mut owner = Owner::default();
    let endpoint = owner.endpoint();
    *endpoint.0.lock().unwrap() = u32::MAX - 1;
    endpoint.complete();
    endpoint.complete();
    assert!(endpoint.try_consume());
    assert_eq!(*endpoint.0.lock().unwrap(), u32::MAX);
    assert_eq!(owner.reset(), Err(()));
    drop(endpoint);
    assert_eq!(owner.reset(), Ok(()));
    assert!(!owner.endpoint().try_consume());
}

#[test]
fn broadcast_covers_current_and_future_endpoints() {
    let owner = Owner::default();
    let first = owner.endpoint();
    first.complete_all();
    assert!(first.try_consume());
    assert!(owner.endpoint().try_consume());
    assert!(first.try_consume());
}

#[test]
fn cancelled_waiter_does_not_destroy_producer_storage() {
    let owner = Owner::default();
    let waiter = owner.endpoint();
    let producer = owner.endpoint();
    let storage = Arc::downgrade(&owner.0);
    drop(waiter); // Models abandoning a handle, not kernel wait cancellation.
    drop(owner);
    producer.complete();
    assert!(storage.upgrade().is_some());
    drop(producer);
    assert!(storage.upgrade().is_none());
}

#[test]
fn concurrent_consumers_cannot_duplicate_tokens() {
    let owner = Owner::default();
    let producer = owner.endpoint();
    for _ in 0..128 {
        producer.complete();
    }
    let workers: Vec<_> = (0..4)
        .map(|_| {
            let endpoint = owner.endpoint();
            std::thread::spawn(move || {
                let mut consumed = 0;
                while endpoint.try_consume() {
                    consumed += 1;
                }
                consumed
            })
        })
        .collect();
    assert_eq!(
        workers.into_iter().map(|w| w.join().unwrap()).sum::<u32>(),
        128
    );
    assert!(!producer.try_consume());
}
