#!/usr/bin/env bash
# Package an already signed, smoke-tested Nuitka app. Requires macOS tools.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: bash tools/build_macos_dmg.sh /path/to/Dosidicus.app output.dmg" >&2
  exit 2
fi

APP="$1"
DMG="$2"
test -x "$APP/Contents/MacOS/Dosidicus"
codesign --verify --deep --strict --verbose=2 "$APP"

TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/dosidicus-dmg.XXXXXX")"
MOUNT_POINT="$TEMP_DIR/mount"
MOUNTED=0
cleanup() {
  if [[ "$MOUNTED" == 1 ]]; then
    # Leave the temporary directory intact if the volume cannot be detached.
    hdiutil detach "$MOUNT_POINT" -force || return
  fi
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

mkdir "$TEMP_DIR/staging" "$MOUNT_POINT"
# ditto preserves the bundle's permissions and framework symlinks.
ditto "$APP" "$TEMP_DIR/staging/Dosidicus.app"
ln -s /Applications "$TEMP_DIR/staging/Applications"

hdiutil create -volname Dosidicus -fs HFS+ -format UDZO \
  -srcfolder "$TEMP_DIR/staging" "$DMG"
hdiutil verify "$DMG"

# Inspect the actual read-only image, including the install shortcut and signature.
hdiutil attach -readonly -nobrowse -mountpoint "$MOUNT_POINT" "$DMG"
MOUNTED=1
test -x "$MOUNT_POINT/Dosidicus.app/Contents/MacOS/Dosidicus"
test -L "$MOUNT_POINT/Applications"
test "$(readlink "$MOUNT_POINT/Applications")" = /Applications
codesign --verify --deep --strict --verbose=2 "$MOUNT_POINT/Dosidicus.app"
hdiutil detach "$MOUNT_POINT"
MOUNTED=0
