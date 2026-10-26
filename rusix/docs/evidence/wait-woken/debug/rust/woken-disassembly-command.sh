#!/usr/bin/env bash
set -euo pipefail
suite="$1"
profile=completion
if [[ "$suite" == plain ]]; then profile=completion-plain; fi
output="/home/aaron/code/rusix/linux-out/lts-wait-woken-$suite-rust-001"
image_id=$(cat "$output/logs/container-image-id.txt")
build="/out/builds/ci-$profile-rust"
docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges \
  --cpus 2 --memory 1g --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$output,dst=/out,readonly" "$image_id" \
  llvm-objdump-19 --disassemble-symbols=wait_woken,woken_wake_function,woken_wake_bit_function --reloc "$build/kernel/sched/wait_rust.o" > "$output/logs/woken-policy-disassembly.log"
docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges \
  --cpus 2 --memory 1g --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$output,dst=/out,readonly" "$image_id" \
  llvm-objdump-19 --disassemble-symbols=rust_helper_wait_clear_woken_mb,rust_helper_wait_set_woken_after_mb,rust_helper_swait_set_current_state --reloc "$build/rust/helpers/helpers.o" > "$output/logs/woken-primitives-disassembly.log"
