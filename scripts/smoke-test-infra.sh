#!/usr/bin/env bash
set -euo pipefail
for executable in gxde-k9 dde-open gxde-movie; do
    command -v "$executable" >/dev/null
done
for module in disomaster-qt6 libgxmr libgxmr-qt6 udisks2-qt6 treeland-protocols; do
    pkg-config --exists "$module"
done
test -e /usr/share/xdg-desktop-portal/portals/gxde.portal
test -e /usr/share/glib-2.0/schemas/90_deepin-default-gsettings.gschema.override
test -e /usr/lib/tmpfiles.d/gxde-k9.conf
rpm -q polkit-pkla-compat >/dev/null
# /var/lib/polkit-1 is intentionally not traversable by regular users.  Check
# the RPM manifest instead of turning a permissions error into a false missing
# file report.
rpm -ql gxde-infra | grep -Fqx \
    /var/lib/polkit-1/localauthority/10-vendor.d/com.deepin.api.device.pkla
python3 - <<'PY'
import json
from pathlib import Path
lock = json.loads(Path('/usr/share/doc/gxde-infra/upstream-lock.json').read_text())
assert len(lock['components']) == 16
assert lock['components']['deepin-keyring']['tag'] == 'branch:master'
PY
