#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Invoked only by the guarded guest PID1. Never run on the host/container.
set -eu
export LC_ALL=C
fail() { printf 'RUSIX_EXT4_FAIL workload %s\n' "$1" >&2; exit 1; }
[ "${RUSIX_BRD_EXT4_GUEST:-}" = 1 ] || fail authorization
[ "${PPID:-0}" = 1 ] || fail parent
case " $(cat /proc/cmdline) " in
    *" rusix.brd_ext4=1 "*) ;;
    *) fail command-line ;;
esac
trap 'fail command' 1 2 3 15
# set -e failures propagate to PID1, which emits the required failure marker.
[ "$(blockdev --getsize64 /dev/ram0)" = 67108864 ] || fail capacity
[ "$(blockdev --getss /dev/ram0)" = 512 ] || fail sectors
(cd /expected && sha256sum -c SHA256SUMS)
mkfs.ext4 -F -q -b 4096 -L rusix-test \
    -U 7b86675e-9aa0-4da8-972b-000000000001 \
    -E lazy_itable_init=0,lazy_journal_init=0 /dev/ram0
printf 'RUSIX_EXT4_PASS mkfs\n'
mount -n -t ext4 -o nosuid,nodev /dev/ram0 /mnt/test
cd /mnt/test
cp /expected/payload payload
chmod 640 payload
ln payload hardlink
truncate -s 1048576 sparse
dd if=/expected/payload of=sparse bs=4096 seek=8 count=4 conv=notrunc status=none
sync payload sparse
# Exercise ext4 direct I/O separately from buffered file writes.
dd if=/expected/payload of=direct bs=4096 oflag=direct conv=fsync status=none
dd if=direct of=/expected/direct-read bs=4096 iflag=direct status=none
cmp /expected/payload /expected/direct-read
rm direct
sha256sum -c /expected/SHA256SUMS
[ "$(stat -c %a payload)" = 640 ] || fail mode
[ "$(stat -c %h payload)" = 2 ] || fail links
[ "$(stat -c %i payload)" = "$(stat -c %i hardlink)" ] || fail inode
[ "$(stat -c %b sparse)" -lt 2048 ] || fail sparse-allocation
printf 'RUSIX_EXT4_PASS initial_write\n'
cd /
umount -n /mnt/test
mount -n -t ext4 -o nosuid,nodev /dev/ram0 /mnt/test
cd /mnt/test
sha256sum -c /expected/SHA256SUMS
cmp payload hardlink
[ "$(stat -c %a payload)" = 640 ] || fail persisted-mode
printf 'RUSIX_EXT4_PASS remount_read\n'
# Truncate and overwrite an existing hardlinked inode, then rename and unlink.
cat /expected/sparse > payload
cmp payload hardlink
mv payload renamed
rm hardlink
printf 'temporary\n' > remove-me
rm remove-me
[ "$(stat -c %h renamed)" = 1 ] || fail surviving-link
sha256sum -c /expected/FINAL.sha256
sync renamed sparse
printf 'RUSIX_EXT4_PASS mutate\n'
cd /
umount -n /mnt/test
mount -n -t ext4 -o ro,nosuid,nodev /dev/ram0 /mnt/test
cd /mnt/test
sha256sum -c /expected/FINAL.sha256
[ ! -e payload ] && [ ! -e hardlink ] && [ ! -e remove-me ] || fail removed-names
[ "$(stat -c %a renamed)" = 640 ] || fail final-mode
printf 'RUSIX_EXT4_PASS final_read\n'
cd /
umount -n /mnt/test
e2fsck -f -n /dev/ram0
printf 'RUSIX_EXT4_PASS fsck\n'
