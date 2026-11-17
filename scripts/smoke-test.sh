#!/usr/bin/env bash
set -euo pipefail
testdir=$(mktemp -d)
trap 'rm -rf "$testdir"' EXIT
for module in dtklog dtkcore dtkgui; do
    test -d "$(pkg-config --variable=libdir "$module")"
    test -d "$(pkg-config --variable=includedir "$module")"
done
cat > "$testdir/CMakeLists.txt" <<'EOF'
cmake_minimum_required(VERSION 3.25)
project(dtk5_consumer LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(Dtk REQUIRED COMPONENTS Core Gui)
add_executable(consumer main.cpp)
target_link_libraries(consumer PRIVATE Dtk::Gui Dtk::Core)
EOF
cat > "$testdir/main.cpp" <<'EOF'
#include <DGuiApplicationHelper>
#include <DObject>
int main() {
    return 0;
}
EOF
cmake -S "$testdir" -B "$testdir/build"
cmake --build "$testdir/build"
"$testdir/build/consumer"
