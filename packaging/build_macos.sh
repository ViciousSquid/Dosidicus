#!/usr/bin/env bash
set -e

pip install pyinstaller dmgbuild

pyinstaller packaging/pyinstaller.spec

mkdir -p dmg
cp -r dist/dosidicus dmg/Dosidicus.app

hdiutil create -volname Dosidicus \
  -srcfolder dmg \
  -ov -format UDZO Dosidicus.dmg
