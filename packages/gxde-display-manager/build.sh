#!/usr/bin/env bash
# Build gxde-display-manager (cmake) and gxdm-emergency-mode (cargo offline).
# Run from spec %build with two args: %{_libdir} and %{_smp_build_ncpus}.
set -euo pipefail
libdir=$1
jobs=$2
stage="$PWD/stage"
mkdir -p "$stage"

# ---- gxde-display-manager (cmake, Qt6) ----
# -DINSTALL_PAM_CONFIGURATION=OFF: Fedora uses its own PAM files (password-auth
#   / postlogin / pam_selinux), not Arch's system-login. The spec installs
#   Fedora-specific PAM files in %install.
# -DCMAKE_INSTALL_LIBEXECDIR=lib/gxdm: matches AUR, helpers go to /usr/lib/gxdm.
# Keep system Qt6/DTK packages discoverable through the standard prefix.
cmake -S gxde-display-manager -B build -G Ninja \
    -DCMAKE_INSTALL_PREFIX=/usr \
    -DCMAKE_INSTALL_LIBDIR="${libdir#/usr/}" \
    -DCMAKE_INSTALL_LIBEXECDIR=lib/gxdm \
    -DCMAKE_BUILD_TYPE=None \
    -DCMAKE_PREFIX_PATH=/usr \
    -DBUILD_WITH_QT6=ON \
    -DBUILD_CLASSIC_GREETER=ON \
    -DBUILD_MAN_PAGES=ON \
    -DINSTALL_PAM_CONFIGURATION=OFF \
    -DUID_MIN=1000 \
    -DUID_MAX=60513
cmake --build build --parallel "$jobs"
DESTDIR="$stage" cmake --install build

# Extra config not installed by cmake (matches AUR package()).
install -Dm644 gxde-display-manager/data/configs/OMG.conf "$stage/etc/gxdm/OMG.conf"

# ---- gxdm-emergency-mode (cargo, offline) ----
# The vendor/ dir and .cargo/config.toml were extracted in %prep.
# --offline --frozen: no network, use vendored crates only.
export CARGO_HOME="$PWD/cargo-home"
( cd gxdm-emergency-mode && \
    cargo build --offline --frozen --release )
install -Dm755 gxdm-emergency-mode/target/release/gxdm-emergency-mode \
    "$stage/usr/bin/gxdm-emergency-mode"
install -Dm755 gxdm-emergency-mode/scripts/gxdmr "$stage/usr/bin/gxdmr"
install -Dm644 gxdm-emergency-mode/data/gxdm-rescue.service \
    "$stage/usr/lib/systemd/system/gxdm-rescue.service"
# Fix /usr/sbin -> /usr/bin in the service file (matches AUR sed).
sed -i 's|/usr/sbin/gxdm-emergency-mode|/usr/bin/gxdm-emergency-mode|' \
    "$stage/usr/lib/systemd/system/gxdm-rescue.service"
