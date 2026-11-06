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
# gsettings-qt was retired from Fedora 45. Our COPR rebuilds Fedora's last
# maintained recipe.
dnf -y copr enable charofstring/gxde-dtk5
python3 scripts/dtk5-sources.py prepare --output /work/build/rpmbuild
dnf -y builddep /work/build/rpmbuild/SPECS/gxde-dtk5.spec
id builder >/dev/null 2>&1 || useradd --create-home builder
chown -R builder:builder /work/build/rpmbuild
runuser -u builder -- rpmbuild -ba --define '_topdir /work/build/rpmbuild' /work/build/rpmbuild/SPECS/gxde-dtk5.spec
# Install the three packages together to exercise dependencies and file ownership.
dnf -y install /work/build/rpmbuild/RPMS/$(uname -m)/gxde-dtk5-*.rpm
rpm -V gxde-dtk5 gxde-dtk5-devel gxde-dtk5-widget-devel
# Exercise the installed SDK with a consumer rather than the build-tree metadata.
runuser -u builder -- bash scripts/smoke-test.sh
