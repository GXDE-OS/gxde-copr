#!/usr/bin/env bash
set -euo pipefail

# gxdm binaries
for executable in gxdm gxdm-emergency-mode gxdmr; do
    command -v "$executable" >/dev/null
done

# gxdm helper in libexec
test -x /usr/lib/gxdm/gxdm-helper || test -x /usr/libexec/gxdm/gxdm-helper
test -x /usr/lib/gxdm/gxdm-settings-agent

# PAM files (Fedora-specific, not upstream Arch-style)
for pam in gxdm gxdm-autologin gxdm-greeter gxdm-rescue; do
    test -f "/etc/pam.d/$pam"
done

# Config
test -f /etc/gxdm/OMG.conf

# systemd services
test -f /usr/lib/systemd/system/gxdm.service
test -f /usr/lib/systemd/system/gxdm-rescue.service

# Greeter session
test -d /usr/share/gxdm/themes || test -d /usr/share/gxdm/translations-qt6

# DBus
test -d /usr/share/dbus-1/system.d
grep -Fqx 'Exec=/usr/lib/gxdm/gxdm-settings-agent' \
    /usr/share/dbus-1/services/top.gxde.DisplayManager.service

# The in-session locker is a separate package from GXDM since 1.3.7.
test ! -e /etc/xdg/autostart/gxdm-lock-classic.desktop

# Lock file
python3 - <<'PY'
import json
from pathlib import Path
lock = json.loads(Path('/usr/share/doc/gxde-display-manager/upstream-lock.json').read_text())
assert len(lock['components']) == 2
assert lock['components']['gxde-display-manager']['tag'] == '1.3.7-gxde2'
assert lock['components']['gxdm-emergency-mode']['tag'] == '1.0.0-gxde2'
PY
