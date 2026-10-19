# Android 3.1.1 CANARY

[Download the signed ARM64 release APK](dosidicus-3.1.1-arm64-release.apk?raw=true)

Android 7.0 or newer (API 24), ARM64. Package `org.vicioussquid.dosidicus`, version code 30101. This is a signed release build. [SHA-256 checksum](SHA256SUMS).

The app uses the shared desktop 3.1 cognitive engine, native mobile controls, editable names and tint, a name badge, and one shared animated fight cloud after the squid approach each other. Brain JSON and desktop save ZIP files can be exchanged with the desktop simulation, Brain Designer and headless trainer. Mobile autosaves use the desktop ZIP sections and retain a mobile extension for its native world.

The new signing key was created because the previous key was reported lost. Export your old pet before uninstalling an APK signed with the lost key: Android cannot install this as an update to that build. This key can update the earlier 3.1.0 APK produced during this work.

Certificate SHA-256: `0bcffa44f72b6e368d58a38ca1c72f388ee1114f04b67fbfc7fbca65164e9c70`.

The private key and password are kept outside the repository. Back them up securely from the build environment's `/workspace/dosidicus-release-signing` directory.

[Actual app gallery and multiplayer recordings](../../docs/canary-gallery/README.md) · [Shared engine details](../ENGINE_3_1.md)

Validation covers the neural engine, save interchange, release signature and ZIP alignment, and native Kivy screen capture. No physical Android device was available for installation testing. The mobile nearby-player interface is separate from the desktop multiplayer protocol; desktop multiplayer lifecycle recordings do not demonstrate Android LAN protocol parity.
