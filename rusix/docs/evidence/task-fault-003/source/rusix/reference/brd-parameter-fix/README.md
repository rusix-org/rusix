# BRD parameter selected-fix oracle

[ADR 0003](../../docs/adr/0003.md) approves the behavior change. This directory
preserves the submitted proposal and defines a separate C comparison; it does
not change `drivers/block/brd.c` or its immutable baseline gate.

Samuel Moelius submitted “brd: normalize non-positive max_part before rounding
it up” on 2026-06-08. Message ID:
`20260608235932.1233876.a0685c37c761.brd-negative-max-part-zero-minors@trailofbits.com`.
Acceptance or an upstream merged commit has not been verified. Original email
attribution is retained; its sign-off is the submitter's, not certification of
our Rust translation.

Retrieved 2026-10-26 from two mirrors:

- [Patchew mbox](https://patchew.org/linux/20260608235932.1233876.a0685c37c761.brd-negative-max-part-zero-minors%40trailofbits.com/mbox), saved as `patchew.mbox`.
- [linux-block raw message](https://lore-kernel.gnuweeb.org/linux-block/20260608235932.1233876.a0685c37c761.brd-negative-max-part-zero-minors@trailofbits.com/raw), saved as `mirror.raw`.

Canonical lore retrieval returned HTTP 403. MIME-decoding these quoted-printable
and 8bit messages produced identical patch bytes; email signatures were not
independently cryptographically verified. `provenance.json` records raw-message,
decoded-body and original-patch hashes. Decoded bodies can be reconstructed with
Python `email.parser.BytesParser(policy=email.policy.default)` and
`get_payload(decode=True)`; the raw messages remain authoritative inputs.

`upstream-proposal.patch` is the unchanged extracted diff. `baseline.patch`
adapts only the two hunk old/new line coordinates by +1 for the pinned release;
context and changed lines are identical. The generator checks that exact
transformation before applying the adapted patch at exact coordinates, with no
fuzz, offset search, extra files or whitespace normalization. `manifest.json`
pins baseline, both patches and generated-source SHA256. The expected output was
also checked byte-for-byte against GNU patch applied to a separate scratch output.
That check is not compilation or runtime evidence.

With explicit `CONFIG_RUSIX_BRD_C_PARAMETER_FIX=y`, Kbuild generates
`drivers/block/brd_parameter_fixed.c` in the output tree and compiles it as a
component of BRD. Built-in composites flatten into the archive, so the selected
member is `brd_parameter_fixed.o`, with `KBUILD_MODNAME=brd`; no composite `brd.o`
is produced. This preserves builtin parameter names. Default C selection still
compiles pristine `brd.c`. Rust and patched-C selection are mutually exclusive.
The oracle is builtin-only and default-off.

The generator validates all hashes before parsing/applying, then validates the
output hash and atomically replaces the generated file. Its `--check` mode only
verifies an existing generated source. Build evidence must identify the
`brd-c-parameter-fix` implementation, record all inputs and the defining object,
and reject pristine C/Rust objects in that selection. Generated source is not
checked in. Normalization policy alone changes; parameter parsing and storage
are outside this fix.
