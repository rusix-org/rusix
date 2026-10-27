# Retained native C teardown KUnit runtime

Both real KVM boots passed: 79 required combined cases and three isolated teardown
cases, through the unchanged original parser and strict gates. Actual container
resources were two CPUs/2 GiB with no extra swap or OOM; each guest used 512 MiB,
two CPUs and a 180-second timeout. Only fresh output was writable.

The retained kernel was built at original source 0ff7a933c198, with C teardown.
Corrected verifier 13e0ddc71a57 separately established the complete object/linked
and fixture proof before these boots. All 5,469 pinned source, raw artifact,
inspection and parser inputs matched before/after and archive-time checks.

The original matrix failure and both reinspection attempts remain in prior
archives referenced by manifest/commit. No old records are recursively copied.
This archive retains only this runtime's outputs and launcher snapshot, including
its exhaustive prerequisite hash inventory. Binary kernel/object files remain
on disk and are referenced by hashes. No rebuild or Rust teardown KUnit result
is claimed; complete paired-matrix acceptance still requires a fresh retry.
