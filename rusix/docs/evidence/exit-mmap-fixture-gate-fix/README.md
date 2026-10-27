# Teardown fixture verifier corrections

The unchanged kernel source is `0ff7a933c198dda0c3e2c0005e4bb97db3867acc`.
Only four verifier/test files change. The first fix admits exactly one native
fixture archive member only in the validated KUnit context. Retained reinspection
001 then failed because the Rust terminator is not all zero. Its pinned constructor
uses NORMAL speed 3 at offset 24 and SUCCESS status 0. The second fix binds exact
native/generated enums and constructor identity, requiring that canonical 72-byte
record and no relocations; arbitrary NULL callback records remain rejected.

Host stage 001 passes 32 suites/335 cases; final stage 002 passes 32/338, each with
4,034 stable input hashes and the same HEAD before/after. Exact stage snapshots,
logs and hashes are retained. Synthetic models are host regressions, not ELF proof.

Actual retained reinspection 002 passes the complete original nested source,
preprocessor, object/archive/linked and three-case fixture registration/payload
checks. Forty executed tooling modules are separately attributed to their hashes;
original kernel/source/configuration and 4,673 raw inputs remain unchanged.
Both inspections used the pinned image at one CPU/2 GiB with no OOM. The failed
001 and successful 002 statuses/diagnostics are retained alongside the actual
object/linked sentinel diagnosis. No guest or compiler ran during reinspection.

The original matrix failure is referenced by immutable commit and manifest in
manifest.json; it is not copied or converted to a pass. No KUnit VM has run.
Fresh paired ordinary/KUnit verification at a reviewed fix commit is still
required before downstream copy/PFN acceptance. PFN's separate old checker has
the same sentinel assumption and requires reviewed propagation before launch.

Manifest records map logical raw paths to stored files with exact raw and stored
hashes. Large text is deterministically gzip-compressed and identical payloads are
shared. Binary inputs remain on disk and are bound by exhaustive original input
maps and actual ownership proofs; no ELF or recursive historical archive is copied.
