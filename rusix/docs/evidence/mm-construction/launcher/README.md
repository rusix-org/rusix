# Prepared MM construction pair — NOT RUN

Frozen source `00c4ef1c190349a671a2a72ce4736c6bfb58210e` in
`linux-mm-construction`. Pinned ext4 toolchain/fixture image:
`sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63`.
Root review is required before execution. No Docker, kernel build, cache copy or
VM was started to prepare these files.

`run.sh` invokes canonical `rusix/ci/run.sh` for `mm-construction-c`, then
`mm-construction-rust`, in fresh `linux-out/mm-construction-verification-001/c`
and `/rust` outputs. It refuses an existing root, acquires the shared
`.wait-owner-remaining.lock`, rejects another source-mounted kernel container,
and requires KVM and the exact local image ID. Each container gets two CPUs and
5 GiB memory/swap total, no network/capabilities, read-only source/Git metadata and
a four-hour timeout. The canonical guest uses a 180-second timeout, q35/KVM,
qemu64, SMP2 and 512 MiB. Owned CID cleanup preserves interruption exits130/143.
No cache is reused or copied; no prior build is attributed to this candidate.

`prepared-source.json` records the committed tree and tracked project,
constructor, fork/Kbuild/Kconfig input hashes. Launch rechecks source cleanliness,
snapshots the same inputs, and saves the guest C/Rust sources before compilation.
Source and launcher hashes are rechecked after execution. An EXIT failure after
a successful container remains a launcher/matrix failure.

Postchecks require build/CI/container success, exact source identities and clean
status, configuration snapshots, no compiler/config/objtool diagnostics, and the
exact four build hashes (config, bzImage, vmlinux, map). They rehash the complete
MM selection dependency inventory, require retained Rust task construction,
and compare build/runtime selection proof. Guest source-before hashes must equal
the recorded compiled inputs, with exact source and artifact inventories; the
copied guest kernel must match the actual build. Saved QEMU argv must match the
entire literal bounded command, including the MM token and artifact paths.

The five required cases, in order, are:

- anonymous_private_fork_cow
- child_mapping_survives_parent_unmap
- repeated_fork_exec_reap
- mdwe_inherited_fork_exec
- mdwe_no_inherit_fork_exec

Pair acceptance additionally requires only CONFIG_RUSIX_MM_CONSTRUCTION_RUST
differs between resolved configurations. Both retain Rust task/core/BRD policy.
Guest init/probe/initramfs hashes, source inventories, image/package locks and
compiler/readelf/QEMU versions must match. Success requires both launcher exits,
final matrix.exit=0 and pair-result.json; result JSON alone is insufficient.

Scope remains ordinary address-space/COW/exec/MDWE consumers. Allocation-failure,
optional lifecycle and broad compatibility coverage are not claimed. Publication
archival is separate; retain failed outputs and use a reviewed fresh retry root.

Preparation checks: shell/Python syntax and read-only frozen-source/fresh-output
preflight passed. Post-run checks have not been exercised against an MM build.

Root refreshed the source after the reviewed archive-binding fix. The older
prepared-source.json is historical; root-preflight.json and root-review.json
bind the current source and executable launcher. No run has started.
