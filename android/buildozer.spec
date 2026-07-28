[app]

# Dosidicus Mobile - a digital pet squid with a visible neural network.
title = Dosidicus
package.name = dosidicus
package.domain = org.vicioussquid

# Package the whole android/ tree (main.py, dosidicus_mobile/, assets/).
source.dir = .
source.include_exts = py,png,jpg,json,ttf,txt
source.include_patterns = assets/*,dosidicus_mobile/*

version = 0.1.0

# Runtime requirements. numpy + pillow have python-for-android recipes.
# plyer powers the "Import squid" native file picker.
requirements = python3,kivy==2.3.1,numpy,pillow,plyer,android

# Portrait-only touch app.
orientation = portrait
fullscreen = 0

# App icon / splash reuse the original squid artwork.
icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/icon.png

# Saves live in the app's private data dir. WRITE_EXTERNAL_STORAGE is only used
# on legacy Android (API 24-28) to drop exported squids into the public
# Downloads folder; on API 29+ that goes through MediaStore and needs no
# permission (the system ignores this one there).
android.permissions = WRITE_EXTERNAL_STORAGE

# API / NDK levels (defaults known to work with kivy 2.3.1 + p4a).
android.api = 33
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True

# SDL2 bootstrap is what Kivy uses.
p4a.bootstrap = sdl2

[buildozer]

log_level = 2
warn_on_root = 1
