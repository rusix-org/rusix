# Reviewed fresh teardown verification retry

Candidate: `8b6ab8382784f5873e416d5bdadae62b4565bb2d`, clean fix worktree.
Independent and root launch review passed; readiness is enabled for the fresh run.

Exact continuity covers config8ec → docs247 → lifecycle0ff → fix13 → docs8b.
All kernel, configuration and fixture code remains byte-identical to config8ec.
The last segment adds only progress/runtime evidence and the seven exact records
already promised by the existing config manifest. Config and lifecycle archives
are now read from the Git-complete candidate checkout with their original hashes.
The initial packaging discovery is retained in initial-preflight-failure.json.

The mandatory retained-C prerequisite validates actual terminal combined79 and
isolated3 runtime results: raw console reparse, exact gates and commands, original
source/kernel/config, resource limits and complete before/after inputs. Its kernel
source remains `0ff7a933c198dda0c3e2c0005e4bb97db3867acc`; corrected checker code
is attributed to `13e0ddc71a57d7576e9cc6f34603bd96d5bbfa08`. Those retained results
do not claim a kernel built from 8b. Original failed matrix001 remains failed.
Lifecycle terminal evidence is independently required as well.

This fresh retry uses output mm-exit-mmap-verification-002: four fresh kernels,
ordinary C/Rust nine cases each and KUnit C/Rust combined79 plus isolated3 per side
(six total guest boots). Pinned c02 image, shared heavy lock, two build CPUs/5GiB,
bounded two-CPU/512MiB VMs and pinned postchecks remain. No cache copies or hosted
CI. All original failures, retained inspections and retained-C runtime remain
untouched. Exact fresh config/object/fixture and paired runtime proof is required
before downstream acceptance. Source/config/lifecycle/retained-C read-only review
records are saved separately; they are not this candidate's runtime results.

Preflight validates all 14 reviewed files against root-ready.json. Launch snapshots
those 14 plus root-ready.json; every pinned postcheck uses the same exact inventory
and existing after-hash checks. The retained-C prerequisite is captured and compared
both before and after the fresh matrix alongside lifecycle and configuration checks.
