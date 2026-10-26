# Approved BRD parameter correction

Guest-only PID 1 fixture for [ADR 0003](../../docs/adr/0003.md). Run through
`rusix/ci/run-container.sh` with `brd-fixed-c` versus `brd-rust`, or their ext4
profiles, using the pinned local container. Never execute the guest binary on
the host or as container init.

The strict runner requires 26 fresh boots per implementation: twelve signed
max_part boundaries with zero and two preallocated disks, then configured
defaults and legacy octal sizing. Six ordered cases verify parameter values,
major registration, initial devices, on-demand mapping, independent direct I/O
and capacity bounds. Actual absent disks receive the same I/O checks. A missing,
extra, reordered, failed or diagnostic-containing case fails the run.

The original six-variant C suite and its fixture remain unchanged. Its historical
high-positive result belongs to pristine Linux; fixed-C and Rust use the approved
contract. Compilation and host gate tests do not establish guest runtime parity.
