# rusix

rusix aims to complete a Rust kernel for the VM/server target in
[ADR 0002](docs/adr/0002.md), then migrate selected userspace components.
The ADR owns the compatibility contract, subsystem divergence policy, and target
boundaries. [The roadmap](docs/ROADMAP.md) orders that work.

## Current status

**Phase 0 bootstrap; Phase 1a is in progress.** Most kernel implementation remains
C. The Rust integer-square-root replacement has recorded C/Rust comparisons;
a six-case SMP VM probe now establishes the C RAM-disk driver's initial contract.
There is no Rust BRD driver or completed ordinary-userspace/ext4 workload yet.

The engineering source remains `21a7f44fd0765fcc5194130b28767786eba1d1e7`.
The accepted target is **Linux 6.18.58 LTS**; transition and verification are
pending. Existing results, including the BRD run at `976e2de80`, do not certify
that LTS baseline. The pinned container passes local verification. Hosted CI is
disabled and manual-only under the [execution policy](ci/README.md).

- [Progress and evidence](PROGRESS.md)
- [Migration inventory](docs/MIGRATIONS.md) and [BRD contract/design](docs/BRD.md)
- [Phase 1a/1b gates](docs/PHASE1.md)
- [Setup and test commands](CONTRIBUTING.md)
- [Toolchain](docs/TOOLCHAIN.md) and [agent instructions](AGENTS.md)
- [Publication record](docs/PUBLICATION.md) and [development assistance](docs/ASSISTANCE.md)

The working branch is `rusix/main` in
[rusix-org/rusix](https://github.com/rusix-org/rusix). Edit tracked files directly;
no parent workspace or document synchronization is required. Experimental kernels
and probes run in isolated VMs, not on the host.
