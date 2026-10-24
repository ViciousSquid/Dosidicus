# Universal macOS DMG

This build configuration produces `dist/Dosidicus-macos-universal2.dmg`,
containing one universal2 `Dosidicus.app` and an Applications shortcut.
It requires macOS 11 or later on Intel or Apple Silicon. Python, NumPy and
Qt are bundled; users do not need to install dependencies.

## Build with GitHub Actions

Add these changes to a branch on GitHub, then open **Actions → Build macOS
universal DMG → Run workflow** and choose that branch. If the workflow is new,
GitHub must also have its `workflow_dispatch` definition on the default branch
before it appears in the Actions menu.
Pushing to `codex/macos-universal-dmg` also starts the build automatically.

The workflow builds on an Intel macOS runner, verifies all bundled native
files contain both CPU slices, mounts the DMG read-only and starts the app.
A second job repeats verification and startup on an Apple Silicon runner.
Download the `dosidicus-macos-universal2` artifact only after both jobs pass.
The artifact contains the DMG and its SHA-256 checksum. The earlier artifact
with `candidate` in its name has not yet passed the Apple Silicon check.
This workflow uploads build artifacts; it does not publish a GitHub release.

## Build locally on a Mac

Install the **universal2 Python 3.11** package from python.org and Xcode Command
Line Tools. A thin Homebrew Python cannot make this universal2 app.
From the repository root, run:

```bash
bash packaging/macos/build.sh
```

The script creates an isolated environment in `work/macos/venv`, downloads
matching Intel and ARM wheels for PyQt5, Qt and NumPy, and combines them using
`delocate`/`lipo`. PyQt5-sip and the PyInstaller bootloader already ship as
universal2. PyInstaller targets universal2 explicitly, and a separate verifier
rejects any native file missing either architecture. The minimum is macOS 11;
the workflow performs runtime checks on macOS 15, not on macOS 11 itself.

To test a local DMG, mount it read-only and run (choose your Mac's architecture):

```bash
mkdir -p work/macos/mount
hdiutil attach -readonly -nobrowse -mountpoint "$PWD/work/macos/mount" dist/Dosidicus-macos-universal2.dmg
work/macos/venv/bin/python packaging/macos/smoke_test.py work/macos/mount/Dosidicus.app arm64
hdiutil detach "$PWD/work/macos/mount"
```

Use `x86_64` on Intel. The check launches the real Cocoa UI, loads a squid,
waits for the event loop, checks an image and translations, closes the app,
and checks its exit status. Temporary test data is removed afterward.

## Storage and signing

The frozen Mac app uses `~/Library/Application Support/Dosidicus/` for settings,
saves, memories, logs, exports and runtime assets. Existing user settings and
saves survive restarts. The app bundle can stay read-only. The error handler
also preserves startup tracebacks when no QApplication exists, avoiding the
secondary QMessageBox abort seen in the supplied crash report; this does not
establish the original cause of that earlier startup failure.

The script produces an **ad-hoc signed, unnotarized development build**.
For public distribution with normal Gatekeeper acceptance, sign with your
Developer ID certificate and notarize with Apple before distributing the DMG.
No signing certificate or Apple credentials are included.

## Current validation

These files were prepared in a Linux environment. The Python/shell/workflow
syntax and writable-storage regression tests can be checked here. No macOS
app or DMG has been built or launched in this environment. Run the workflow
to obtain and validate the actual installer.
