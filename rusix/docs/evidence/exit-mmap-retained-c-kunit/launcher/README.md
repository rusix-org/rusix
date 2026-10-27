# Disabled retained C teardown KUnit runtime

Two new boots exercise the existing kernel at original frozen source 0ff7a933:
combined 79 cases followed by isolated three teardown cases, using the original
strict parser/gate and original boot script. The complete corrected reinspection
002 must pass and every pinned source, raw build and inspection input must remain
unchanged before and after. The corrected verifier is separately attributed;
this does not claim a newly built fixed-source kernel or repair matrix 001.

Only new output is writable. Shared kernel-work lock, pinned c02 image, two CPUs,
2 GiB RAM with no extra swap, no network/capabilities, KVM only; each QEMU is
512 MiB/two CPUs/180 seconds, outer container bounded to eight minutes. Logs,
commands, consoles, strict parse/gate exits and actual Docker inspect are retained.
An unconditional host audit follows every terminal container outcome, including
timeout or OOM; its separate exit and logs preserve the original container exit.
A still-running owned container is stopped before that audit. Failed inspection
or changed pinned inputs makes the launcher fail.
No compiler or guest executable is run on the host. A failed first boot stops
the sequence and preserves failure evidence. Readiness is false; root and
independent review are required before enabling or running.
