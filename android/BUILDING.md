# Building & developing Dosidicus Mobile

A step-by-step guide to getting an Android build environment working and to the
day-to-day loop for improving the app. There are three ways to get an APK —
start with **Option A** (zero local setup) and move to a local build once you
want to iterate on-device quickly.

---

## Option A — Build in the cloud (GitHub Actions), no local setup

This is the fastest way to a real APK and needs nothing installed on your
machine. A workflow at `.github/workflows/android-build.yml` builds the debug
APK on a GitHub runner (which, unlike a sandbox, can reach Google's SDK
servers).

1. **Push a change under `android/`** (or trigger it manually — see step 2).
   The workflow runs automatically on pushes to `main` and any
   `claude/android-version-*` branch.
2. **Or run it on demand:** on GitHub go to the repo → **Actions** tab →
   **Build Android APK** → **Run workflow** → pick your branch → **Run**.
3. **Watch it build.** The first run takes ~20–40 min (it downloads the Android
   SDK + NDK and cross-compiles NumPy). Later runs are faster thanks to caching.
4. **Download the APK.** When the run finishes green, open it and download the
   **`dosidicus-debug-apk`** artifact at the bottom of the run summary. Unzip it
   to get `dosidicus-0.1.0-*-debug.apk`.
5. **Install on your phone.** Copy the APK to the device and open it (enable
   "install from unknown sources" when prompted), or use `adb install <file>.apk`.

> If a run fails, the workflow uploads a **`buildozer-build-log`** artifact —
> download it to see exactly which step failed.

---

## Option B — Local build on Linux or Windows (WSL2)

Buildozer only builds on Linux/macOS. On **Windows use WSL2** (Ubuntu) — native
Windows is not supported. Inside Ubuntu (native or WSL2):

### 1. System packages
```bash
sudo apt update
sudo apt install -y \
  build-essential git zip unzip openjdk-17-jdk python3-pip python3-venv \
  autoconf libtool pkg-config zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev
```

### 2. Use JDK 17
Buildozer's Android toolchain is happiest on Java 17. Check and select it:
```bash
java -version                 # should say 17.x
sudo update-alternatives --config java   # pick the 17 entry if it isn't default
export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
```

### 3. Python env + Buildozer
```bash
cd android
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install buildozer "Cython==0.29.37"
pip install -r requirements.txt   # kivy/numpy/pillow, for running on desktop too
```

### 4. First build
```bash
buildozer android debug
```
The **first** build downloads the Android SDK, NDK and build-tools into
`~/.buildozer` and compiles NumPy for ARM — budget 20–40 minutes and a few GB of
disk. Subsequent builds are minutes. The APK lands in `android/bin/`.

### 5. Install / run on a device
Enable **Developer options → USB debugging** on the phone, plug it in, then:
```bash
buildozer android deploy run logcat   # installs, launches, streams logs
# or, with the platform-tools adb:
adb install -r bin/dosidicus-*-debug.apk
```

### Windows/WSL2 note
To see a plugged-in phone from inside WSL2 you need `usbipd-win` to attach the
USB device to WSL, or just build in WSL and `adb install` from Windows
PowerShell using the APK on the shared filesystem.

---

## Option C — Local build on macOS

Buildozer runs on macOS (Intel and Apple Silicon), though Linux/WSL is the most
trodden path.
```bash
brew install python autoconf automake libtool pkg-config
brew install --cask temurin@17          # JDK 17
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
cd android
python3 -m venv .venv && source .venv/bin/activate
pip install buildozer "Cython==0.29.37" -r requirements.txt
buildozer android debug
```

---

## The day-to-day development loop

You do **not** need to build an APK to make progress. Most iteration happens on
the desktop, where the exact same engine and Kivy UI run:

1. **Change code** in `dosidicus_mobile/engine/` (the brain/squid/sim) or
   `dosidicus_mobile/ui/` (the Kivy screens).
2. **Test the engine** (fast, no display):
   ```bash
   python tests/test_engine.py
   ```
3. **Run the whole app on desktop** to see the UI:
   ```bash
   python main.py
   ```
   The desktop window behaves like the phone — tap the tank to feed, use the
   care buttons, toggle **Brain**.
4. **Only when packaging**, run `buildozer android debug` (locally or via the
   Actions workflow).

Rule of thumb: engine logic → cover it with a test in `tests/`; UI/visual
changes → eyeball them with `python main.py`; ship → let CI build the APK.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Build dies right after "Downloading …" with a 403 / connection refused | Your network blocks Google's SDK hosts (`dl.google.com`, `services.gradle.org`). Build via **Option A (CI)** or on an unrestricted network. |
| Gradle error mentioning an unsupported Java version | You're on Java 21+. Switch to **JDK 17** (see Option B step 2). |
| `Aidl not found` / SDK license prompts hang | Delete `~/.buildozer` and rebuild; buildozer re-downloads and auto-accepts licenses. |
| Out of disk space | The SDK/NDK need several GB. Free space or run `buildozer android clean`. |
| A recipe won't compile after a dependency bump | Pin it: keep `Cython==0.29.37`, and if needed pin `buildozer` in the install step to a known-good release. |
| Change to `android/` didn't rebuild in CI | The workflow only triggers on paths under `android/**`; use **Run workflow** in the Actions tab to force it. |

---

## Roadmap — growing this from an MVP

The codebase is split so features can be added without disturbing the core:

* **Engine (`engine/`)** is pure Python + NumPy and fully testable. Port more of
  the desktop STRINg engine here (STDP, the dual long/short-term memory system
  from `memory_manager.py`, richer decision weighting). Add a test per feature.
* **UI (`ui/`)** is Kivy. Good next steps:
  * a **memory panel** (surface `brain.recent_events` as a scrolling log),
  * a **neuron inspector** (tap a neuron in the brain view to see its weights),
  * pinch-to-zoom / pan on the brain view for large grown networks,
  * a **new-squid / personality picker** screen.
* **Bigger ports** from the desktop app: the Brain Designer, and the plugin
  system (achievements, multiplayer) — these are intentionally out of the MVP.

Suggested workflow for each improvement: branch → add/port engine logic with a
test → wire it into a Kivy widget → verify with `python main.py` → let the
Actions workflow produce an APK to try on a phone.
