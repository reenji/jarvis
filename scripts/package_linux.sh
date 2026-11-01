#!/usr/bin/env bash
# Package the PyInstaller Linux build as a .deb and a portable .tar.gz.
#
# Usage: scripts/package_linux.sh <version> [dist-dir] [out-dir]
#   dist-dir defaults to dist (it must hold ARGUS/ from `pyinstaller ARGUS.spec`)
#   out-dir  defaults to dist
#
# Output (unversioned names, so releases/latest/download links stay valid):
#   ARGUS-linux-x86_64.deb     installs to /usr/lib/argus, /usr/bin/argus and an
#                              app-menu entry that opens the desktop window
#   ARGUS-linux-x86_64.tar.gz  portable folder; run ./argus/ARGUS
set -euo pipefail

version=${1:?usage: package_linux.sh <version> [dist-dir] [out-dir]}
dist=$(realpath "${2:-dist}")
out=$(realpath "${3:-dist}")
root=$(cd "$(dirname "$0")/.." && pwd)
bundle="$dist/ARGUS"
test -x "$bundle/ARGUS" || { echo "missing $bundle/ARGUS; run pyinstaller first" >&2; exit 1; }

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Portable archive.
cp -a "$bundle" "$work/argus"
tar -C "$work" -czf "$out/ARGUS-linux-x86_64.tar.gz" argus

# Debian package.
pkg="$work/deb"
install -d "$pkg/DEBIAN" "$pkg/usr/lib" "$pkg/usr/bin" \
  "$pkg/usr/share/applications" "$pkg/usr/share/icons/hicolor/256x256/apps"
cp -a "$bundle" "$pkg/usr/lib/argus"
ln -s ../lib/argus/ARGUS "$pkg/usr/bin/argus"
python3 "$root/scripts/make_windows_icon.py" --png "$pkg/usr/share/icons/hicolor/256x256/apps/argus.png" >/dev/null

cat > "$pkg/usr/share/applications/argus.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Argus
Comment=AI desktop assistant
Exec=/usr/lib/argus/ARGUS desktop
Icon=argus
Terminal=false
Categories=Utility;
StartupWMClass=ARGUS
EOF

installed_kb=$(du -sk "$pkg/usr" | cut -f1)
cat > "$pkg/DEBIAN/control" <<EOF
Package: argus
Version: $version
Section: utils
Priority: optional
Architecture: amd64
Installed-Size: $installed_kb
Depends: libc6 (>= 2.35), libgl1, libegl1, libglib2.0-0, libfontconfig1, libdbus-1-3, libxkbcommon-x11-0, libxcb-cursor0, libportaudio2
Maintainer: reenji <141559536+reenji@users.noreply.github.com>
Homepage: https://github.com/reenji/jarvis
Description: Argus AI desktop assistant
 Desktop assistant with voice and text, plus the argus terminal command.
EOF

dpkg-deb -Zzstd --build --root-owner-group "$pkg" "$out/ARGUS-linux-x86_64.deb" >/dev/null
echo "Wrote $out/ARGUS-linux-x86_64.deb and $out/ARGUS-linux-x86_64.tar.gz"
