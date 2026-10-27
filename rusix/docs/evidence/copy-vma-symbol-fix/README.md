# Copy-VMA namespace fix checkpoint

Run 001 at 4d145044e0 ended with status 2. C passed nine ordinary and five
native cases and its postcheck. Rust compiled its objects but failed linking:
the new VMA accessor collided with the inherited MM-copy policy rusix_copy_mm.
No Rust copy-VMA guest ran. The matrix remains failed.

The private accessor is renamed rusix_copy_vma_mm; its field access and the
existing MM-copy policy are unchanged. Namespace and actual-preprocessed getter
checks reject the observed collision. All 36 host suites (380 cases) and the
independent source review pass. The fix has not been rebuilt or run in a VM.

This compact pause record retains failure logs, C receipts and exact fix/host
inputs. Full original outputs remain in linux-out/copy-vma-verification-001.
It is not a complete matrix archive or paired acceptance result.
