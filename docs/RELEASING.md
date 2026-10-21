# Multi-platform releases

[Release all platforms](../.github/workflows/release.yml) builds the selected
commit into these six installable distributions:

| Platform | Artifact |
| --- | --- |
| Windows x64 | `Dosidicus-VERSION-windows-x64.zip` |
| Windows ARM64, compiled natively | `Dosidicus-VERSION-windows-arm64.zip` |
| macOS Apple Silicon | `Dosidicus-VERSION-macos-arm64.zip` |
| macOS Intel | `Dosidicus-VERSION-macos-x64.zip` |
| Linux x64 | `Dosidicus-VERSION-linux-x64.tar.gz` |
| Android ARM64 | `Dosidicus-VERSION-android-arm64.apk` |

A release also includes `SHA256SUMS` and `release-info.json` with the source
commit and workflow run. Linux archives preserve executable permissions.

## Signing configuration

Set repository secrets in **Settings → Secrets and variables → Actions**:

- `ANDROID_KEYSTORE_BASE64`: base64 of the existing release keystore.
- `ANDROID_KEYSTORE_PASSWORD`: the keystore password.
- `ANDROID_KEY_ALIAS`: optional; defaults to `dosidicus`.
- `ANDROID_KEY_PASSWORD`: optional when it is the same as the store password.

Reuse the key created for Android 3.1.0/3.1.1/3.1.2. Its private files are in
`/workspace/dosidicus-release-signing` in the original build environment. Transfer
them securely to repository secrets and keep a private backup. Never commit the
keystore or its password. The workflow fails before building if the required
signing secrets are absent; it does not publish an unsigned APK.

The Windows archives are not Authenticode-signed. The macOS apps are ad-hoc
signed, without Apple notarization. Android uses the configured release key.

## Start a release

Once this workflow is on the default branch, open **Actions → Release all
platforms → Run workflow**, select the source branch (for example `CANARY`),
enter a new tag such as `v3.1.3-canary.1`, and choose whether it is a prerelease.

The workflow creates the tag at the exact selected commit when publishing.
It rejects an existing tag that points to a different commit. It never moves
an existing tag or overwrites an existing release.

Alternatively, push a version tag pointing to a commit containing the workflow:

```bash
git switch CANARY
git pull --ff-only
git tag -a v3.1.3-canary.1 -m 'Dosidicus 3.1.3 Canary 1'
git push origin v3.1.3-canary.1
```

Tag pushes with a `-suffix` produce prereleases; plain tags such as `v3.1.3`
produce stable releases. The tag must use `vMAJOR.MINOR.PATCH` with an optional
prerelease suffix. The workflow synchronizes the desktop version, Android
version name and mobile package version. Android's version code is
`MAJOR * 10000 + MINOR * 100 + PATCH` (minor and patch must be below 100).

## Publication and validation

The existing desktop, native WinARM64 and Android workflows are reusable jobs.
All use the caller's commit. The Android job runs the shared desktop/mobile test
suite. Desktop jobs smoke-test their compiled applications; the ARM64 job also
checks the PE architecture of the executable and every bundled DLL/PYD. Android
signing verifies the APK signature and ZIP alignment.

The publish job runs only after every build succeeds. It requires exactly one
of each expected platform artifact, calculates SHA-256 checksums, uploads to a
**draft** release, checks the uploaded names and sizes, then publishes the draft.
Build or upload failures cannot leave a partially published release. A failure
during publication can leave a draft for inspection; remove that draft before
retrying the whole workflow with the same tag.

Runtime packaging copies an explicit list of app assets and source plugins.
Git configuration, build caches, saved pets and the APKs committed under
`android/releases` are excluded from desktop distributions.

Local checks for workflow changes:

```bash
actionlint
python -m pytest tests/test_release_support.py -q
```

The actionlint configuration includes the official `windows-11-vs2026-arm` and
`macos-15-intel` hosted labels for compatibility with older actionlint versions.
