#!/usr/bin/env bash
# Package the PyInstaller macOS build as a drag-to-install disk image.
#
# Usage: scripts/package_macos.sh [dist-dir] [out-dir]
#   dist-dir defaults to dist (it must hold ARGUS.app from `pyinstaller ARGUS.spec`)
#   out-dir  defaults to dist
#
# Output: ARGUS-macos-arm64.dmg (unversioned, so releases/latest/download links
# stay valid). The image holds ARGUS.app and a link to /Applications.
set -euo pipefail

dist=$(cd "${1:-dist}" && pwd)
out=$(cd "${2:-dist}" && pwd)
app="$dist/ARGUS.app"
test -d "$app" || { echo "missing $app; run pyinstaller first" >&2; exit 1; }

staging=$(mktemp -d)
trap 'rm -rf "$staging"' EXIT
cp -R "$app" "$staging/"
ln -s /Applications "$staging/Applications"

hdiutil create -volname Argus -srcfolder "$staging" -ov -format UDZO "$out/ARGUS-macos-arm64.dmg" >/dev/null
echo "Wrote $out/ARGUS-macos-arm64.dmg"
