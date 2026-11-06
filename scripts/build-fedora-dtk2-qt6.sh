#!/usr/bin/env bash
# Run as root INSIDE a disposable Fedora container, with the repository at /work.
set -euo pipefail
source /etc/os-release
if [[ "$ID" != fedora || "$VERSION_ID" != 45 ]]; then
    echo 'This script requires a disposable Fedora 45 container.' >&2
    exit 1
fi
cd /work
dnf -y install rpm-build redhat-rpm-config dnf5-plugins python3 shadow-utils
dnf -y copr enable charofstring/gxde-dtk5
dnf -y copr enable charofstring/gxde-dtk6
dnf -y copr enable charofstring/gxde-dtk2-qt6
python3 scripts/dtk2-qt6-sources.py prepare --output /work/build/dtk2-qt6-rpmbuild
dnf -y builddep /work/build/dtk2-qt6-rpmbuild/SPECS/gxde-dtk2-qt6.spec
id builder >/dev/null 2>&1 || useradd --create-home builder
chown -R builder:builder /work/build/dtk2-qt6-rpmbuild
runuser -u builder -- rpmbuild -ba --define '_topdir /work/build/dtk2-qt6-rpmbuild' /work/build/dtk2-qt6-rpmbuild/SPECS/gxde-dtk2-qt6.spec
dnf -y install /work/build/dtk2-qt6-rpmbuild/RPMS/$(uname -m)/gxde-dtk2-qt6-*.rpm
rpm -V gxde-dtk2-qt6 gxde-dtk2-qt6-devel
runuser -u builder -- bash scripts/smoke-test-dtk2-qt6.sh
