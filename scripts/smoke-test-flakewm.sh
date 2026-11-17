#!/usr/bin/env bash
set -euo pipefail

# flakewm binaries
for executable in flakewm startflakewm; do
    command -v "$executable" >/dev/null
done

# Wayland session
test -f /usr/share/wayland-sessions/gxde-flakewm.desktop

# Lock file
python3 - <<'PY'
import json
from pathlib import Path
lock = json.loads(Path('/usr/share/doc/flakewm/upstream-lock.json').read_text())
assert len(lock['components']) == 1
assert 'flakewm' in lock['components']
PY
