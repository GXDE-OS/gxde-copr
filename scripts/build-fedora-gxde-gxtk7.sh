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
python3 scripts/gxde-gxtk7-sources.py prepare --package all
id builder >/dev/null 2>&1 || useradd --create-home builder
for package in gxde-bernese gxde-gxtk7; do
    tree="/work/build/$package-rpmbuild"
    dnf -y builddep "$tree/SPECS/$package.spec"
    chown -R builder:builder "$tree"
    runuser -u builder -- rpmbuild -ba --define "_topdir $tree" "$tree/SPECS/$package.spec"
    mapfile -t rpms < <(find "$tree/RPMS" -name '*.rpm')
    dnf -y install "${rpms[@]}"
    rpm -V "$package"
    rpm -q "$package-devel" >/dev/null 2>&1 && rpm -V "$package-devel"
done
