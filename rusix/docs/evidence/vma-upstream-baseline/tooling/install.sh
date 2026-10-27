#!/bin/bash
set -euo pipefail
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends liburcu-dev
dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' | sort > /opt/rusix/vma-packages.lock
pkg-config --modversion liburcu > /opt/rusix/vma-liburcu-version.txt
rm -rf /var/lib/apt/lists/*
