#!/bin/bash
# Usage: tests/run-overlay-option-path.sh [source-root]
#
# Extracts isValidOverlayOptionPath from <source-root>/src/darlingserver.cpp, runs it against paths
# that would change the overlayfs option layout, and checks that main() calls it on the libexec path
# before the option string is built. No darlingserver build and no root are needed.
# <source-root> defaults to this checkout; pass another checkout to test another revision.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "${1:-$here/..}" && pwd)
src="$root/src/darlingserver.cpp"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

awk '/^static bool isValidOverlayOptionPath\(/ {on=1} on {print} on && /^}/ {exit}' "$src" > "$work/extracted.inc"
if ! [ -s "$work/extracted.inc" ]; then
	echo "FAIL: isValidOverlayOptionPath not found in $src"
	exit 1
fi

check=$(grep -nE '^[[:space:]]*if \(!isValidOverlayOptionPath\(libexec' "$src" | head -1 | cut -d: -f1)
build=$(grep -n 'std::string opts = "lowerdir=" + libexec' "$src" | head -1 | cut -d: -f1)
if [ -z "$check" ] || [ -z "$build" ] || [ "$check" -ge "$build" ]; then
	echo "FAIL: libexec is not validated before the overlay option string is built"
	exit 1
fi

${CXX:-c++} -std=c++17 -g -O0 -Wall -fsanitize=undefined -fno-sanitize-recover=undefined \
	-I"$work" -o "$work/t" "$here/host/overlay_option_path_test.cpp"
"$work/t"
