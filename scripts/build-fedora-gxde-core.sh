#!/usr/bin/env bash
# Run inside a disposable Fedora 45 container with the repository at /work.
# Builds the split gxde-core packages in dependency-wave order; each wave's
# RPMs are installed before the next so intra-project BuildRequires
# (gxde-libs-devel, gxde-dock-devel, gxde-app-management-devel) resolve.
set -euo pipefail
source /etc/os-release
if [[ "$ID" != fedora || "$VERSION_ID" != 45 ]]; then
    echo 'This script requires a Fedora 45 container.' >&2
    exit 1
fi
cd /work
dnf -y install rpm-build redhat-rpm-config dnf5-plugins python3 shadow-utils
for project in gxde-dtk5 gxde-dtk2 gxde-dtk6 gxde-dtk2-qt6 gxde-infra gxde-gxtk7; do
    dnf -y copr enable "charofstring/$project"
done
python3 scripts/gxde-core-sources.py prepare --group all
id builder >/dev/null 2>&1 || useradd --create-home builder

WAVES=(
    'gxde-artwork gxde-libs gxde-daemon gxde-polkit-agent gxde-installer
     gxde-screensaver gxde-terminal gxde-compressor gxde-launcher
     gxde-session-ui gxde-app-management'
    'gxde-dock gxde-control-center'
    'gxde-top-panel gxde-file-manager'
    'gxde-search gxde-wallpaper-chooser'
    'gxde-core'
)
for wave in "${WAVES[@]}"; do
    for g in $wave; do
        dnf -y builddep "/work/build/$g-rpmbuild/SPECS/$g.spec"
        chown -R builder:builder "/work/build/$g-rpmbuild"
        runuser -u builder -- rpmbuild -ba \
            --define "_topdir /work/build/$g-rpmbuild" \
            "/work/build/$g-rpmbuild/SPECS/$g.spec"
    done
    rpms=()
    for g in $wave; do
        while IFS= read -r f; do rpms+=("$f"); done < <(find "/work/build/$g-rpmbuild/RPMS" -name '*.rpm')
    done
    dnf -y install "${rpms[@]}"
    for g in $wave; do
        rpm -V "$g"
        rpm -q "$g-devel" >/dev/null 2>&1 && rpm -V "$g-devel"
    done
done
runuser -u builder -- bash scripts/smoke-test-gxde-core.sh
