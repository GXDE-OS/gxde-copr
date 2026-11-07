#!/usr/bin/env bash
# gxde-libs: internal network utility library.
set -euo pipefail
libdir=$1 jobs=$2 common=$3
. "$common"

# network-utils .pro hardcodes target.path = $$PREFIX/lib and expands the pc
# libdir at parse time; -after moves both to Fedora's libdir.
_qmake qmake6 gxde-network-utils-qt6 \
    -after "target.path=$libdir" "QMAKE_PKGCONFIG_LIBDIR=$libdir"
normalize_stage
