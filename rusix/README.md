# rusix

rusix aims to complete a Rust kernel for the VM/server target in
[ADR 0002](docs/adr/0002.md), then migrate selected userspace components.
The ADR owns the compatibility contract, subsystem divergence policy, and target
boundaries. [The roadmap](docs/ROADMAP.md) orders that work.

## Current status

**Phase 1a remains in progress; most kernel code is still C.** The baseline is
**Linux 6.18.58 LTS**. Rust BRD passes paired block and ordinary-userspace ext4
tests. All fourteen completion.c and ten swait.c entry points have opt-in Rust
implementations, alongside thirteen generic wait entries. Paired C/Rust tests cover
core behavior, ordinary ext4 and pipe/poll/epoll/eventfd consumers.
[PROGRESS.md](PROGRESS.md) links exact source/configuration evidence and remaining
gates, including BRD parameter behavior and the C queue/scheduler dependencies.

The pinned baseline transition preserves earlier main history. Historical
results retain their original source identities. Hosted CI is disabled and manual-only under the
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
