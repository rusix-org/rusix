# Task-fault retry — reviewed, not executed

Root and independent review passed; REVIEWED_LAUNCH_READY is True. Preparation
and launch remain serialized by the shared matrix lock. Final source is
362835315fb594e49374dc2b6d38aa5208769082. The exact reviewed verifier/generator fix
remains bound separately to c59986edf69556715bd1094521c8d8d1a49ebaab.

The earlier pinned generator retry stopped by OOM (137) remains preserved.
Root reports pinned full-generator session 54044 now completed with status 0
under the same 2 GiB limit, with all six packet inputs independently rehashed.
The source checkpoint records this at
linux-task-faults/rusix/docs/evidence/task-fault-calibration-fix. This proves
calibration generation against the retained C kernel only; no new kernel or
fault guest execution has occurred as part of preparing this retry draft.

Fresh output is linux-out/task-fault-verification-002. The preparer copies only
001's completed C kernel build directory; it never copies logs, calibration,
VM evidence or guest fixtures. Rust starts without any cache. It validates the
exact initial-failure manifest, every archived text and retained raw hash,
original whole-output inventory, and exact reviewed source delta before and
after copy. No original output is modified. Only reviewed verifier/test changes
and documentation are allowed; kernel, configuration and guest executable
sources must be unchanged. The explicit fixed-file inventory now includes the reviewed calibration
generator, trace validator and their two host regression files, each bound to
the exact c599 fix commit. Further changes are refused until reviewed.

Cache invalidation includes fork preprocessing/object/command, kernel archive,
linked images/maps, numbered temporary and unstripped link outputs, compressed
images and piggy objects. Fresh re-linking and preprocessing generate new source
identities/proofs. Copied hashes, modes, timestamps, symlink targets and removed
outputs are recorded. Preflight rehashes the entire prepared cache, insists on
fresh logs and empty Rust output, and rejects any surviving invalidated path.
Preparation and launch share the existing matrix flock. Preparation performs
no build/guest work; no cache copy has been run during drafting.

The runner serializes C then Rust in pinned c02 containers (2 CPUs, 5 GiB,
four-hour outer limit), using owned CID cleanup and exact clean source guards.
The fault guest keeps the existing q35/KVM, 512 MiB, two-CPU, 300-second bound
and nokaslr requirement. Pinned postchecks use the same image without KVM;
actual calibration and raw capture/cleanup/config/fixture comparison remain
strict. Initial failed evidence is never relabeled as a passing retry. The
launcher records all five draft file hashes and checks them after each side;
source and original-failure inventories are revalidated after completion.

When the shared matrix slot is free, preparation is:
python3 -B linux-out/task-fault-retry-draft/prepare_caches.py --execute
Then launch would be:
bash linux-out/task-fault-retry-draft/run.sh
Neither command is authorized by the presence of this draft.

Root and independent source/cache/provenance review passed. Source and original
raw/archive inventories were rehashed without mutation. Launch readiness is now
enabled; preparation and launch still require the shared matrix lock. Pinned
postchecks use 2 GiB memory including swap, matching the successful full-generator
recheck; one CPU, no network/KVM and five-minute timeout remain. No retry cache
copy, kernel build or VM has run.
