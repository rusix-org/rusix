# Initial source publication gate

**Status: HOLD — do not push yet.** Aaron requested this hold on 2026-10-25.

The public repository `https://github.com/rusix-org/rusix` was created empty at
Aaron's request. It is `origin` for the local Linux-derived repository; the
original Linux remote remains `upstream`. GitHub reported public visibility,
`isEmpty=true`, and no default branch after creation. No code has been pushed.

Creating a public repository and publishing source are separate actions. Do not
bypass the hold by creating files/commits through an API, pushing a different
branch, uploading a release, or publishing artifacts elsewhere. Continue local
implementation, verification, documentation, and commits.

## Required before the first push

Aaron's conditions are an initial working layer and updated documentation and
contribution guidelines. The following are the concrete readiness checks for the
initial kernel migration layer; they do not shrink the overall rewrite objective.

- [x] Pinned Linux-derived history and actual Rust replacement in a kernel path.
- [x] Clean committed C/Rust comparison, preserved upstream tests, added boundary
  coverage, and captured x86_64 VM evidence for the first replacement.
- [ ] Complete the first layer's remaining module/export/CRC and fallback checks,
  or explicitly resolve the initial release scope with Aaron rather than quietly
  declaring unfinished verification complete.
- [x] Accepted architectural direction documented and linked from project guidance.
- [ ] Public-facing repository entry point and contributor guide accurately
  explain layout, build/test commands, dependencies, review expectations, current
  limitations, attribution, and upstream maintenance.
- [ ] Reproduce the contributor path from a fresh checkout of the intended
  publication revision. Distinguish tested platforms from unsupported setups.
- [ ] Review project-facing docs, migration inventory, and progress against
  current evidence. Inherited Linux documentation remains attributed upstream;
  rusix changes and limits must be clear.
- [ ] Audit the intended first-push history/artifacts for correct provenance,
  licenses, unintended binaries, credentials/private data, and misleading claims.
  Resolve the initial shallow checkout's history/publication requirements.
- [ ] Record the exact publication candidate, readiness results, and remaining
  limitations here before the hold can be considered satisfied.

No gate is satisfied merely by planning it, creating an empty repository, or
writing a passing-looking checklist. Cite the actual commands/results. There is
no hosted CI or public source review yet; do not claim otherwise.

The current hold is Aaron's explicit instruction, not a tool approval failure.
If the meaning of the initial working layer needs to change, obtain clarification
before publishing. Never treat this document as authorization to waive a condition.
