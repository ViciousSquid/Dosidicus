#!/usr/bin/env bash
set -e

pip install pyinstaller

pyinstaller packaging/pyinstaller.spec

# Create AppDir
mkdir -p AppDir/usr/bin
cp -r dist/dosidicus/* AppDir/usr/bin/

# Download AppImage tool
wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool-x86_64.AppImage

./appimagetool-x86_64.AppImage AppDir Dosidicus.AppImage
