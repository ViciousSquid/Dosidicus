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

# App icon; the startup splash is a full title image (icon + tagline + URL) so
# there's a single, branded splash rather than a bare icon then a second screen.
icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png
android.presplash_color = #0a0d17

# WRITE_EXTERNAL_STORAGE: legacy (API 24-28) export to public Downloads (API 29+
# uses MediaStore, no permission). The rest power local peer-to-peer visits via
# Google Nearby Connections (Bluetooth + Wi-Fi + location, per the Nearby docs).
android.permissions = WRITE_EXTERNAL_STORAGE, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE, CHANGE_WIFI_STATE, BLUETOOTH, BLUETOOTH_ADMIN, BLUETOOTH_ADVERTISE, BLUETOOTH_CONNECT, BLUETOOTH_SCAN, ACCESS_COARSE_LOCATION, ACCESS_FINE_LOCATION, NEARBY_WIFI_DEVICES

# Google Nearby Connections (local peer-to-peer). Pulls in Play Services, which
# needs AndroidX; the Java shim in ./java bridges it to Python.
android.gradle_dependencies = com.google.android.gms:play-services-nearby:18.7.0
android.enable_androidx = True
android.add_src = java

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
