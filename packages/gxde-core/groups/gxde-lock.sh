#!/usr/bin/env bash
# gxde-lock: in-session lock screen for X11 and Wayland.
set -euo pipefail
libdir=$1 jobs=$2 common=$3
. "$common"

_cmake gxde-lock \
    -DBUILD_NEO_LOCK=ON \
    -DINSTALL_PAM_CONFIGURATION=ON

# startgxde deliberately publishes XDG_CURRENT_DESKTOP=Deepin before it runs
# XDG autostart entries.  Accept that identifier and GXDE's declared desktop
# name, while keeping the locker out of KDE, GNOME and other sessions.
autostart="$stage/etc/xdg/autostart/gxde-lock.desktop"
grep -Fqx 'X-GNOME-Autostart-enabled=true' "$autostart"
sed -i '/^X-GNOME-Autostart-enabled=true$/a OnlyShowIn=GXDE;Deepin;' "$autostart"

normalize_stage
