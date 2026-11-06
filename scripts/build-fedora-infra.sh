#!/usr/bin/env bash
# Run inside a disposable Fedora 45 container with the repository at /work.
set -euo pipefail
source /etc/os-release
if [[ "$ID" != fedora || "$VERSION_ID" != 45 ]]; then
    echo 'This script requires a Fedora 45 container.' >&2
    exit 1
fi
cd /work
dnf -y install rpm-build redhat-rpm-config dnf5-plugins python3 shadow-utils
for project in gxde-dtk5 gxde-dtk2 gxde-dtk6 gxde-dtk2-qt6; do
    dnf -y copr enable "charofstring/$project"
done
python3 scripts/infra-sources.py prepare --output /work/build/infra-rpmbuild
dnf -y builddep /work/build/infra-rpmbuild/SPECS/gxde-infra.spec
id builder >/dev/null 2>&1 || useradd --create-home builder
chown -R builder:builder /work/build/infra-rpmbuild
runuser -u builder -- rpmbuild -ba --define '_topdir /work/build/infra-rpmbuild' \
    /work/build/infra-rpmbuild/SPECS/gxde-infra.spec
dnf -y install /work/build/infra-rpmbuild/RPMS/$(uname -m)/gxde-infra-*.rpm
rpm -V gxde-infra gxde-infra-devel
runuser -u builder -- bash scripts/smoke-test-infra.sh
