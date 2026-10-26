# Task constructor retry003 — source preparation only

Frozen source eec5ae3ecd7b9a671157694d0eceaaa89870889e. Compared with002's
0af2, only PROGRESS and the exact reviewed pointer-only improper_ctypes annotation
change. Preparer strips that exact comment/attribute block and requires the old
Rust source bytes back; every other kernel file is unchanged.

After root review, with the shared build slot free:

1. `python3 -B linux-out/task-construction-ffi-retry-draft/prepare-caches.py --execute`
2. `bash linux-out/task-construction-ffi-retry-draft/run.sh`

Each side copies its matching002 kernel-only build tree. C002 completed its build
and five guest cases; Rust002 stopped137 after36 diagnostics. Rust's old vmlinux
and bzImage are inherited C cache, not completed Rust outputs. Full copied file
and symlink inventories are checked before invalidation. Existing fork.i, fork.o,
.fork.o.cmd, built-in.a/.cmd and task_construction_rust.o/.cmd are removed to force
current-source constructor compilation, archive reconstruction and relinking.
No old logs, guest fixtures, statuses or proofs are copied.

The original001 and002 entire raw trees,69-record initial failure archive,
181-record diagnostic archive and each recorded compiled artifact hash are
revalidated before and after copying and after the final pair. Prior evidence
keeps its original source/status. New003 source, build, selection, preprocessing,
tool identity and five-case consumer results must all pass afresh for both sides.

Runner remains serial C then Rust, shared exclusive lock and active-container
check, pinned image, two CPUs/5GiB, network disabled, KVM and owned-CID cleanup.
No copy, compilation, Docker or VM execution has occurred while preparing this
draft. Unsupported ABI diagnostics still fail the unchanged warning gate.
