# Release003 cache retry — prepared only

Frozen source: `cfc899021ac624d392d0241009374bb40acd3b49`. Parent review is
required before **either** `prepare-caches.py --execute` or `run.sh`. Neither
has been executed during preparation. Destination must not exist before copying:
`linux-out/mm-release-verification-003`.

Seed002 source `42318e69e5f27a2f2363c0fea285cca59f710baf`: C completed build and
80 combined/67 core/4 release cases with postchecks; Rust was stopped137 after
33 improper_ctypes warnings, without Rust runtime acceptance. Retry source
changes only the reviewed pointer-only extern-block comment/allow and PROGRESS.
Removing that exact annotation must reproduce the seed Rust file byte-for-byte.
No cache status is carried forward as new evidence.

Preparation verifies original001 FAIL2 archive70text records and original002
FAIL137 archive188text records, all retained artifact hashes, and inventories
both complete original output trees plus archives before and after copying.
Only each corresponding side's `builds/ci-mm-release-SIDE` is copied; no logs,
boot/fixture outputs, status files or outer temporary directory are inherited.
Regular files preserve bytes/mode/mtime; symlinks preserve target without following.
Unexpected special files are rejected. The one observed interrupted make FIFO
`002/rust/builds/tmp/GMfifo1162` is recorded as metadata only, never opened/copied.

Copied caches are compared in full, then invalidated explicitly: fork preprocessing
and object/cmd, release Rust object/cmd, kernel archive/cmd, root archive/link/kernel
outputs and compressed boot outputs. Each removed entry retains its old hash,
size/mode/mtime in cache-preparation.json. Fresh canonical Kbuild and source/tool
records are mandatory. No source timestamps are changed. Original001/002 and
archives are checked again after each side and at final completion.

Launcher preserves the reviewed release retry's pinned c02 image, shared global
flock, owned-CID signal cleanup, two CPUs/5GiB and KVM two CPUs/512MiB/180s. Actual
postchecks remain in that image with no KVM/network and bounded1CPU/1GiB/5m, using
the existing exact80/67/4 validators, callback/ELF metadata and source/provenance
checks. All003 proof/VM records must be fresh. Current compilation/runtime scope
remains unverified until that separate reviewed execution completes.
