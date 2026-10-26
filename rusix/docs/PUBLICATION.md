# Initial source publication record

**Status: first source publication completed, 2026-10-25.**

First published commit: `5520dd71ea4637bca9e82761463c0df53f3feb46` on
`rusix/main`. GitHub independently returned that branch SHA after the push.
The default branch is `rusix/main`, issues are enabled, and GitHub's README API
selects the rusix `README.md`. The public fork's parent is verified as
`torvalds/linux`. Subsequent documentation commits may advance the branch.

Aaron clarified on 2026-10-25 that the existing kernel build and passing tests
are a sufficient initial layer if the docs are ready. Module/export/CRC, fallback,
other architecture, userspace, and performance checks remain disclosed follow-up
work; they are not additional prerequisites for this first source publication.
This clarification supersedes the earlier stricter checklist in this document.

## Repository and scope

The destination is `https://github.com/rusix-org/rusix`, remote `origin`. GitHub
verified `isFork=true`, parent `torvalds/linux`, and public visibility. Linux is
still remote `upstream`; the inherited `master` branch is kept distinct from
`rusix/main`. No changes are pushed to upstream.

The first public layer contains a real Rust integer-square-root implementation
selected in Rust-enabled kernels, preserved upstream tests, added compatibility
checks, recorded C/Rust comparison evidence, and project/contributor guidance.
Most Linux implementation remains C. This is an experimental source milestone,
not a production release, complete rewrite, or full compatibility claim.

The initial empty standalone repository was retained under
`rusix-org/rusix-empty-placeholder` after GitHub rejected deletion for missing
`delete_repo` permission. Aaron approved replacing that empty repository with
this fork. The placeholder contains no rusix source; it may be deleted manually
by an organization administrator. No broader authentication scope was requested.

## Readiness evidence

- Verified C/Rust kernel comparison: `docs/VERIFICATION.md` and its raw evidence.
  Both kernels pass 26 KUnit cases with identical configurations; original tests
  are unchanged and the linked Rust implementation is confirmed.
- Accepted direction: `docs/ARCHITECTURE.md`, linked from project instructions.
- Contributor guide and source-tree entry points are prepared. Independent review
  checked their setup paths, local links, scope, and limitations; the discovered
  workspace-root checkpatch path was corrected.
- Fresh-checkout reproduction passed against source revision `9047da37a`.
  Restoration followed the contributor guide at that revision in an independent Git worktree;
  tools are shared from the same verified host installation, not claimed as a
  portable or hermetic SDK. Preflight, three native host tests, and nine gate
  regression tests pass. The fresh kernel builds and boots with 26/26 KUnit cases
  passing and the strict result gate satisfied. Evidence is under
  `docs/evidence/publication-check/`. Publication changes after this revision are
  documentation and evidence only; the kernel implementation is unchanged.
- The GitHub fork retains the Linux repository network and full public ancestry.
  The local checkout remains shallow. A full-history fetch was deliberately
  stopped after the fork made it unnecessary for this push; Git connectivity
  verification passed. Future historical investigation may deepen local history.
- Reviewed 77 project-added historical blobs through `9047da37a`: no unexpected
  binary/large artifacts or known credential-pattern matches; inherited license
  files and upstream README are unchanged. This is a bounded repository hygiene
  check, not a formal security/license audit. Final documentation changes are
  checked separately for links, whitespace, and accurate scope.
- There is no hosted CI or independent human-maintainer approval claim. The
  successful push and GitHub branch/default-branch/README checks establish
  publication, not any additional runtime behavior.

No results are inferred from plans. Upstream ancestry is retained in the fork;
publication contains the documented initial layer and clearly exposes remaining
work. The temporary local verification worktree is removed after its evidence
is archived; its kernel image/config are retained under `artifacts/publication-check/`
locally. Evidence path strings reflect where commands originally ran.
