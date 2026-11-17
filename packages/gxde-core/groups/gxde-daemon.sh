#!/usr/bin/env bash
# gxde-daemon: session base services (daemons, menu, sni, globalmenu,
# wayland-gtk-menu, garma, startgxde, transhell).
set -euo pipefail
libdir=$1 jobs=$2 common=$3
. "$common"

# deepin-daemon (Go, GOPATH mode) needs golang-gxde-dev from gxde-infra at
# /usr/share/gocode-gxde. CGo flags mirror AUR's _goenv(); Fedora keeps
# asoundlib.h under alsa/ while the vendored binding includes <asoundlib.h>.
export GO111MODULE=off GOFLAGS='-buildmode=pie -trimpath'
export GOCACHE="$PWD/gocache"
export GOPATH="/usr/share/gocode-gxde${GOPATH:+:$GOPATH}"
export CGO_CPPFLAGS="${CPPFLAGS:-} -I/usr/include/alsa" CGO_CFLAGS="${CFLAGS:-} -std=gnu17"
export CGO_CXXFLAGS="${CXXFLAGS:-}" CGO_LDFLAGS="${LDFLAGS:-}"

_cmake garma
make -C deepin-daemon
for d in dock daemon-manager gtk-theme-inject; do
    cmake -S "gxde-daemon/plugins/$d" -B "build-gxde-daemon-$d" -DCMAKE_BUILD_TYPE=None \
        -DCMAKE_INSTALL_PREFIX=/usr
    cmake --build "build-gxde-daemon-$d"
done
make -C startgxde
_qmake qmake6 deepin-menu
_cmake gxde-sni-server
_cmake gxde-globalmenu-service
_cmake gxde-wayland-gtk-menu

# ---- install ----
cp -a transhell/src/. "$stage/"
make -C deepin-daemon install DESTDIR="$stage" PAM_MODULE_DIR=usr/lib/security
install -Dm755 build-gxde-daemon-dock/gxde-dock-daemon \
    "$stage/usr/libexec/gxde-daemon/dock/gxde-dock-daemon"
install -Dm755 build-gxde-daemon-gtk-theme-inject/gxde-gtk-theme-inject \
    "$stage/usr/libexec/gxde-daemon/gtk-theme-inject/gxde-gtk-theme-inject"
install -Dm755 build-gxde-daemon-daemon-manager/gxde-daemon-manager \
    "$stage/usr/libexec/gxde-daemon/daemon-manager/gxde-daemon-manager"
install -Dm644 gxde-daemon/plugins/dock/translations/*.json \
    -t "$stage/usr/share/gxde-daemon/dock/translations/"
# gxde-daemon debian/install extras (dh_install beyond make install)
( cd gxde-daemon
    install -d "$stage"/usr/{bin,libexec,share/{polkit-1,applications,dbus-1/{services,system-services,system.d}}}
    install -d "$stage"/usr/share/gxde-k9/{system,edging} "$stage"/usr/share/gxde-daemon/{daemon-k9-conf,plugins}
    install -d "$stage/usr/lib/systemd/system"
    cp -a bin/. "$stage/usr/bin/"
    cp -a misc/polkit-1/. "$stage/usr/share/polkit-1/"
    cp -a misc/applications/. "$stage/usr/share/applications/"
    cp -a libexec/gxde-daemon gxde-daemon "$stage/usr/libexec/"
    cp -a dbus/services/. "$stage/usr/share/dbus-1/services/"
    cp -a dbus/system-services/. "$stage/usr/share/dbus-1/system-services/"
    cp -a dbus/system.d/. "$stage/usr/share/dbus-1/system.d/"
    cp -a k9/system/. "$stage/usr/share/gxde-k9/system/"
    cp -a k9/edging/. "$stage/usr/share/gxde-k9/edging/"
    cp -a k9/disable/. "$stage/usr/share/gxde-daemon/daemon-k9-conf/"
    cp -a systemd/system/. "$stage/usr/lib/systemd/system/"
    install -m644 plugins/dock/data/top.gxde.daemon.dock.service "$stage/usr/share/dbus-1/services/"
    install -m644 manifests/*.json "$stage/usr/share/gxde-daemon/plugins/" )
make -C startgxde install DESTDIR="$stage"

# GXDE on Fedora is Wayland-only.  startgxde still installs the historical
# Deepin X11 session entry, which would make display managers offer a GXDE X11
# session that this package set does not support.
rm -f "$stage/usr/share/xsessions/deepin.desktop"
rmdir --ignore-fail-on-non-empty "$stage/usr/share/xsessions" 2>/dev/null || true

normalize_stage
