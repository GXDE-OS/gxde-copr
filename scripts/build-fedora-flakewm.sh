#!/usr/bin/env bash
# Run inside a disposable Fedora 45 container with the repository at /work.
set -euo pipefail
source /etc/os-release
if [[ ("$ID" != fedora && "$ID" != evernight) || "$VERSION_ID" != 45 ]]; then
    echo 'This script requires a Fedora 45 compatible container.' >&2
    exit 1
fi
cd /work
dnf -y install rpm-build redhat-rpm-config dnf5-plugins python3 shadow-utils
python3 scripts/flakewm-sources.py prepare --output /work/build/flakewm-rpmbuild
dnf -y builddep /work/build/flakewm-rpmbuild/SPECS/flakewm.spec
id builder >/dev/null 2>&1 || useradd --create-home builder
chown -R builder:builder /work/build/flakewm-rpmbuild
runuser -u builder -- rpmbuild -ba --define '_topdir /work/build/flakewm-rpmbuild' \
    /work/build/flakewm-rpmbuild/SPECS/flakewm.spec
dnf -y install /work/build/flakewm-rpmbuild/RPMS/$(uname -m)/flakewm-*.rpm
rpm -V flakewm
runuser -u builder -- bash scripts/smoke-test-flakewm.sh
