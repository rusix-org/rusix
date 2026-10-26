# rusix

rusix aims to complete a Rust kernel for the VM/server target in
[ADR 0002](docs/adr/0002.md), then migrate selected userspace components.
The ADR owns the compatibility contract, subsystem divergence policy, and target
boundaries. [The roadmap](docs/ROADMAP.md) orders that work.

## Current status

**Phase 1a implementation and verification are in progress.** Most kernel code
remains C. This branch is based on **Linux 6.18.58 LTS**. Its required math
compatibility tests pass. [Paired x86_64 q35 evidence](docs/evidence/brd-q35/manifest.json)
at `9d1c1ca5dd` covers C/Rust BRD block6, ordinary ext4 six cases, six parameter
boots and five partition cases, with identical fixture archives and only BRD
selection differing in configuration. Nine Rust ownership tests also pass.
Negative-parameter behavior, remaining C parameter/interface code and core
integration gaps prevent a Phase 1a completion claim; see [PROGRESS.md](PROGRESS.md).

The published main branch remains on its earlier verified source until this
transition passes review gates. Historical results retain their original source
identities. Hosted CI is disabled and manual-only under the
[execution policy](ci/README.md).

- [Progress and evidence](PROGRESS.md)
- [Migration inventory](docs/MIGRATIONS.md) and [BRD contract/design](docs/BRD.md)
- [Phase 1a/1b gates](docs/PHASE1.md)
- [Setup and test commands](CONTRIBUTING.md)
- [Toolchain](docs/TOOLCHAIN.md) and [agent instructions](AGENTS.md)
- [Publication record](docs/PUBLICATION.md) and [development assistance](docs/ASSISTANCE.md)

The integration branch is `rusix/lts-6.18`; published work is on `rusix/main` in
[rusix-org/rusix](https://github.com/rusix-org/rusix). Edit tracked files directly;
no parent workspace or document synchronization is required. Experimental kernels
and probes run in isolated VMs, not on the host.
