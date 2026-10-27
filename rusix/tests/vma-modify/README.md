# VMA modification native fixture

Run the unchanged pinned Linux `tools/testing/selftests/mm/merge.c` with five
explicit `-r merge.<case>` filters from `upstream.json`. Its original
`kselftest_harness.h` matches these complete names and excludes other cases.
`vm_util` supplies the native PROCMAP_QUERY topology assertions; no test bodies
are copied or changed. Baseline source/blob hashes bind the seven native inputs.

Guest-only x86-64 PID1 mounts proc, requires exactly one
`rusix.vma_modify_probe=1` token, and runs the child with a cleared environment.
A 60-second watchdog preserves the unreaped leader before process-group cleanup;
PID1 then bounds adopted-descendant reaping. The native harness creates extra
process groups: surviving children cause cleanup failure, and the disposable
VM deadline/poweroff contains them. Never execute these binaries on the host or
in a container. Supply `/proc`, `/dev/console`, `/init` and `/probe` in the archive.

Final formatted fixture sources pass pinned static x86-64 compilation in run
`002`; pre-format run `001` remains separately recorded. Neither guest binary was
executed. The compile archive retains the precompile README; this status-only
update leaves the compiled init and native test inputs unchanged. Actual console
acceptance, linked policy selection and C/Rust VM execution remain pending.
These five success cases do not certify allocation rollback, callback counts,
optional configuration paths or complete MM behavior.

The real local runtime pipeline is `scripts/run-vma-modify.py`, also selected
explicitly through `test-vma-lifecycle-vm.py --vma-modify`. After ancestor
acceptance and launch review, `vma-modify-c` and `vma-modify-rust` run two fresh
boots each: nine existing VMA consumers followed by these five unchanged native
filters. Before each boot, the actual modification selection gate must match the
complete build proof and its saved nested records; historical profiles are not
relabelled. Local CI and container routing now invoke this pipeline.

Native compilation uses three unchanged translation units and checks all seven
baseline identities. It hashes the actual 187 native/system dependencies before
compilation, requires matching emitted dependency files afterward, and records
packages, Rust libraries and static linker inputs. Static x86-64 init/probe files
remain mode 0644 on the host and are executable only inside the guest initramfs.
Each VM is bounded to 512 MiB, two CPUs and 180 seconds. The real runner has not
been executed: host parser/routing tests do not establish kernel or guest parity.
