#!/usr/bin/env bash
set -euo pipefail
# Expectations verified against the installed split packages and Arch ground
# truth (startgxde-git / gxde-core-git file lists) on the Fedora VM.

# Core binaries. The session binary is deepin-session (startgxde module);
# there is no "gxde-session" on Arch either.
for executable in startgxde deepin-session deepin-menu gxde-control-center \
                  gxde-launcher gxde-dock gxde-terminal gxde-top-panel rofd \
                  gxde-app-installer gxde-requ gxde-wallpaper-chooser; do
    command -v "$executable" >/dev/null
done

# deepin-daemon service binaries (under /usr/lib by design, not on PATH)
test -x /usr/lib/deepin-daemon/dde-session-daemon
test -x /usr/lib/deepin-daemon/dde-system-daemon

# Shared libraries actually produced by the split groups
for module in gxde-network-utils-qt6 gxde-bernese-qt6 rofd_ffi dfm6-io \
              dfm6-search deepin-pdfium; do
    found=
    for lib in "/usr/lib64/lib${module}.so"* "/usr/lib/lib${module}.so"*; do
        if [[ -e $lib ]]; then found=1; break; fi
    done
    if [[ -z $found ]]; then
        echo "smoke: missing shared library lib${module}.so*" >&2
        exit 1
    fi
done

# Theme / artwork
test -d /usr/share/icons/gxde
test -d /usr/share/wallpapers/deepin
ls /usr/share/glib-2.0/schemas/*.gschema.xml >/dev/null 2>&1
ls /usr/share/glib-2.0/schemas/ | grep -q deepin

# Session entry: Arch ground truth is xsessions/deepin.desktop from startgxde.
# The GXDE Wayland session entry (gxde-flakewm.desktop) ships in the separate
# flakewm package, not here.
test -f /usr/share/xsessions/deepin.desktop

# Polkit
test -d /usr/share/polkit-1/actions

# DBus services
test -d /usr/share/dbus-1/services
test -d /usr/share/dbus-1/system-services

# systemd units from deepin-daemon
test -d /usr/lib/systemd/system

# rofd
test -f /usr/bin/rofd
test -f /usr/share/applications/rofd.desktop
test -f /usr/share/icons/hicolor/256x256/apps/rofd.png

# gxde-daemon
test -d /usr/libexec/gxde-daemon
test -x /usr/libexec/gxde-daemon/dock/gxde-dock-daemon

# Lock file (shipped as %doc by every split group package)
python3 - <<'PY'
import json
from pathlib import Path
lock = json.loads(Path('/usr/share/doc/gxde-artwork/upstream-lock.json').read_text())
assert len(lock['components']) == 44, len(lock['components'])
assert len(lock['groups']) == 18, len(lock['groups'])
# Branch-pinned modules must record their branch.
for name in ('gxde-sni-server', 'gxde-top-panel-plugins', 'gxde-file-manager',
             'gxde-terminal', 'rofd'):
    assert lock['components'][name].get('branch'), f'{name} missing branch'
PY
