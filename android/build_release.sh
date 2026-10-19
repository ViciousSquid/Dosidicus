#!/usr/bin/env bash
# Build the shared engine into an APK, then sign without exposing passwords to
# Buildozer's verbose environment diagnostics. Requires the Android SDK tools.
set -euo pipefail
cd "$(dirname "$0")"
python prepare_apk.py
# Signing is performed after the build, never in the logged p4a environment.
unset P4A_RELEASE_KEYSTORE P4A_RELEASE_KEYSTORE_PASSWD P4A_RELEASE_KEYALIAS P4A_RELEASE_KEYALIAS_PASSWD
buildozer android release
if [[ -z "${DOSIDICUS_KEYSTORE:-}" || -z "${DOSIDICUS_STOREPASS_FILE:-}" ]]; then
    echo "Unsigned release APK created in android/bin. Set DOSIDICUS_KEYSTORE and DOSIDICUS_STOREPASS_FILE to sign."
    exit 0
fi
: "${ANDROID_SDK_ROOT:?Set ANDROID_SDK_ROOT to the Android SDK directory}"
build_tools="$(find "$ANDROID_SDK_ROOT/build-tools" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -1)"
unsigned="$(find bin -maxdepth 1 -name '*-release-unsigned.apk' | sort | tail -1)"
[[ -n "$unsigned" ]] || { echo "No unsigned release APK found" >&2; exit 1; }
version="$(sed -n 's/^version = //p' buildozer.spec)"
output="bin/dosidicus-${version}-arm64-release.apk"
"$build_tools/zipalign" -f -p 4 "$unsigned" "$output.aligned"
key_password_args=()
if [[ -n "${DOSIDICUS_KEYPASS_FILE:-}" && "$DOSIDICUS_KEYPASS_FILE" != "$DOSIDICUS_STOREPASS_FILE" ]]; then
    key_password_args=(--key-pass "file:$DOSIDICUS_KEYPASS_FILE")
fi
"$build_tools/apksigner" sign --ks "$DOSIDICUS_KEYSTORE" \
    --ks-key-alias "${DOSIDICUS_KEY_ALIAS:-dosidicus}" \
    --ks-pass "file:$DOSIDICUS_STOREPASS_FILE" \
    "${key_password_args[@]}" \
    --out "$output" "$output.aligned"
rm "$output.aligned"
"$build_tools/apksigner" verify --verbose --print-certs "$output"
"$build_tools/zipalign" -c -p 4 "$output"
