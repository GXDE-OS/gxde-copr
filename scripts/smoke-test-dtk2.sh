#!/usr/bin/env bash
set -euo pipefail
pkg-config --exists dframeworkdbus dtkwidget
root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
cat > "$root/CMakeLists.txt" <<'CMAKE'
cmake_minimum_required(VERSION 3.25)
project(gxde_dtk2_consumer LANGUAGES CXX)
find_package(Qt5 REQUIRED COMPONENTS Widgets)
find_package(PkgConfig REQUIRED)
pkg_check_modules(DTK2 REQUIRED IMPORTED_TARGET dtkwidget)
add_executable(consumer main.cpp)
target_link_libraries(consumer PRIVATE PkgConfig::DTK2 Qt5::Widgets)
CMAKE
cat > "$root/main.cpp" <<'CPP'
#include <DApplication>
#include <DPushButton>
int main(int argc, char **argv) {
    Dtk::Widget::DApplication app(argc, argv);
    Dtk::Widget::DPushButton button("DTK2 Fedora");
    return button.text().isEmpty();
}
CPP
cmake -S "$root" -B "$root/build"
cmake --build "$root/build"
# DTK2's StartupNotificationMonitor unconditionally asks libxcb for a screen;
# Qt's offscreen/minimal backends therefore dereference a null XCB connection.
# Compilation/linking is the headless smoke test; runtime is covered inside the
# real GXDE Wayland session through XWayland.
