# Tool-assisted development record

The initial rusix work is AI-assisted and has not yet received outside human
maintainer review. This record supports the inherited Linux generated-content
guidance; it is not a sign-off, license certification, or substitute for review.

## Scope and instructions

Aaron requested a Linux fork progressively rewritten into Rust, strong project
instructions and progress tracking, preservation of upstream tests, and a base
that outside contributors can scrutinize. Aaron then accepted Linux-compatible
external behavior with Rust-native internals and incremental subsystem migration.
He authorized parallel agents for independent work. The public repository was
created at his request, with source publication initially held pending readiness. Aaron later clarified
that the existing built/tested kernel layer is sufficient once docs are ready,
and approved using a GitHub-recognized Linux fork.

## Assistance used

Codex produced the initial Rust integer-square-root translation, supplementary
tests, build/verification scripts, and project documentation, while inspecting
the pinned Linux source and preserving its attribution. Sub-agents independently
reviewed arithmetic/ABI behavior, module export selection, and verification
tooling. Review findings led to additional 32-bit tests, stricter result gates,
immutable evidence handling, and clearer source/configuration provenance.

Later sub-agent tasks investigated the GCD/LCM dependency cluster, drafted the
contributor guide, and prepared/reviewed a VM-only Rust init plus C module ABI
probe. The module fixture's compilation and source review are not runtime results.

## Verification and responsibility

Executed tests and limitations are recorded in `VERIFICATION.md`, `PROGRESS.md`,
and the archived evidence. Tools included Git, rustc/rustfmt, Clang/LLVM, kernel
Kbuild/KUnit, QEMU, Python harnesses, and kernel checkpatch. GitHub CLI initially created an empty public repository, then created the
authorized Linux fork after retaining the empty placeholder under another name.
The first source push followed the documented readiness checks; GitHub verified
the resulting branch SHA and default branch. The publication record tracks the
exact source-push result separately from runtime verification.

Agent agreement is not independent human approval. No human DCO certification
has been added by the agents. Before public submission, the human submitter must
understand and review the work, follow the inherited contribution/licensing
requirements, and disclose relevant assistance in submission descriptions.
