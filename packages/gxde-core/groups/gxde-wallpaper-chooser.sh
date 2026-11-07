#!/usr/bin/env bash
# gxde-wallpaper-chooser: wallpaper, lock-screen and screensaver chooser.
set -euo pipefail
libdir=$1 jobs=$2 common=$3
. "$common"

_cmake gxde-wallpaper-chooser

# Upstream installs its static embeddable library to the literal `lib`
# directory instead of GNUInstallDirs. Move it to Fedora's architecture libdir.
if [[ $libdir != /usr/lib && -f "$stage/usr/lib/libgxde-wallpicker.a" ]]; then
    install -d "$stage$libdir"
    mv "$stage/usr/lib/libgxde-wallpicker.a" "$stage$libdir/"
fi

normalize_stage
