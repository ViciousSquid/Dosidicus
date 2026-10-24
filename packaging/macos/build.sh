#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../.."

if [[ "$(uname -s)" != Darwin ]]; then
  echo "Build on macOS using the universal2 Python 3.11 installer from python.org." >&2
  exit 1
fi
MACOS_PYTHON="${MACOS_PYTHON:-/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11}"
lipo "$MACOS_PYTHON" -verify_arch x86_64 arm64
mkdir -p work/macos dist
"$MACOS_PYTHON" -m venv work/macos/venv
MACOS_VENV_PYTHON="$PWD/work/macos/venv/bin/python"
"$MACOS_VENV_PYTHON" -m pip install -r packaging/macos/requirements-build.txt
"$MACOS_VENV_PYTHON" packaging/macos/prepare_wheels.py

ICONSET="$PWD/work/macos/Dosidicus.iconset"
mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" images/icons/squidblack.png --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z "$double" "$double" images/icons/squidblack.png --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o work/macos/Dosidicus.icns
"$MACOS_VENV_PYTHON" -m PyInstaller --noconfirm --clean --workpath work/macos/pyinstaller packaging/macos/Dosidicus.spec
"$MACOS_VENV_PYTHON" packaging/macos/verify_bundle.py dist/Dosidicus.app

STAGE="$PWD/work/macos/dmg-stage"
rm -rf "$STAGE"
mkdir -p "$STAGE"
ditto dist/Dosidicus.app "$STAGE/Dosidicus.app"
ln -s /Applications "$STAGE/Applications"
cp packaging/macos/INSTALL.txt "$STAGE/INSTALL.txt"
cp LICENSE "$STAGE/LICENSE.txt"
hdiutil create -ov -volname Dosidicus -srcfolder "$STAGE" -format UDZO -fs HFS+ dist/Dosidicus-macos-universal2.dmg
hdiutil verify dist/Dosidicus-macos-universal2.dmg
(cd dist && shasum -a 256 Dosidicus-macos-universal2.dmg > Dosidicus-macos-universal2.dmg.sha256)
