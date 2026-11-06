#!/usr/bin/env bash
# Build and install one gxde-extra package in a disposable Fedora container.
set -euo pipefail
name=${1:?package name required}
source /etc/os-release
if [[ $ID != fedora || $VERSION_ID != 45 ]]; then
    echo 'Requires a Fedora 45 container' >&2
    exit 1
fi
cd /work
python3 - "$name" <<'PY'
import json, sys
manifest = json.load(open('packages/gxde-extra/manifest.json'))
assert sys.argv[1] == 'gxde-extra' or sys.argv[1] in manifest, f'Unknown gxde-extra package: {sys.argv[1]}'
PY
dnf -y install rpm-build redhat-rpm-config dnf5-plugins python3 shadow-utils
for project in gxde-dtk5 gxde-dtk2 gxde-dtk6 gxde-dtk2-qt6 gxde-infra gxde-core gxde-extra; do
    dnf -y copr enable "charofstring/$project"
done
spec="/work/build/$name-rpmbuild/SPECS/$name.spec"
if [[ ! -f $spec ]]; then
    python3 scripts/gxde-extra-sources.py prepare --package "$name"
fi
dnf -y builddep "$spec"
id builder >/dev/null 2>&1 || useradd --create-home builder
chown -R builder:builder "/work/build/$name-rpmbuild"
runuser -u builder -- rpmbuild -ba --define "_topdir /work/build/$name-rpmbuild" "$spec"
mapfile -t rpms < <(find "/work/build/$name-rpmbuild/RPMS" -name '*.rpm')
test "${#rpms[@]}" -gt 0
dnf -y install "${rpms[@]}"
rpm -V "$name"
