#!/usr/bin/env bash
# Run as root INSIDE a disposable Fedora container, with the repository at /work.
set -euo pipefail
source /etc/os-release
if [[ "$ID" != fedora || "$VERSION_ID" != 45 ]]; then
    echo 'This script requires a disposable Fedora 45 container.' >&2
    exit 1
fi
cd /work
dnf -y install rpm-build redhat-rpm-config dnf5-plugins python3 shadow-utils cmake pkgconf-pkg-config
dnf -y copr enable charofstring/gxde-dtk5
python3 scripts/dtk2-sources.py prepare --output /work/build/dtk2-rpmbuild
dnf -y builddep /work/build/dtk2-rpmbuild/SPECS/gxde-dtk2.spec
id builder >/dev/null 2>&1 || useradd --create-home builder
chown -R builder:builder /work/build/dtk2-rpmbuild
runuser -u builder -- rpmbuild -ba --define '_topdir /work/build/dtk2-rpmbuild' /work/build/dtk2-rpmbuild/SPECS/gxde-dtk2.spec
# Install the three packages together to exercise dependencies and file ownership.
dnf -y install /work/build/dtk2-rpmbuild/RPMS/$(uname -m)/gxde-dtk2-*.rpm
rpm -V gxde-dtk2 gxde-dtk2-devel gxde-dtk2-widget-devel
# Exercise the installed SDK with a consumer rather than the build-tree metadata.
runuser -u builder -- bash scripts/smoke-test-dtk2.sh
