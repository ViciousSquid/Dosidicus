# Building & developing Dosidicus Mobile

A step-by-step guide to getting an Android build environment working and to the
day-to-day loop for improving the app. Pick the path that fits you: **Option A**
(cloud build, zero local setup), **Option B** (Windows via WSL2, step by step),
**Option C** (native Linux), or **Option D** (macOS). If you just want the APK,
use Option A; set up a local build when you want to iterate on-device.

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

## Option B — Local build on Windows, step by step (WSL2)

**Buildozer cannot build on native Windows** (no cmd/PowerShell build, no
MSYS2/Cygwin path that works reliably). The supported route is **WSL2** — a real
Ubuntu Linux running inside Windows 10/11. You do everything below *inside* that
Ubuntu, and the finished `.apk` is a normal file you copy to your phone. Budget
~1 GB for WSL + Ubuntu and several GB for the Android SDK/NDK, and ~20–40 min for
the first build.

### Step 1 — Install WSL2 + Ubuntu
Open **PowerShell as Administrator** (Start → type "PowerShell" → *Run as
administrator*) and run:
```powershell
wsl --install -d Ubuntu-22.04
```
This enables WSL2 and installs Ubuntu. **Reboot** if it asks you to. On first
launch Ubuntu opens a terminal and asks you to create a **UNIX username and
password** — remember the password; `sudo` needs it. (Already have WSL? Make sure
it's v2 with `wsl -l -v`; if Ubuntu shows `VERSION 1`, run
`wsl --set-version Ubuntu-22.04 2`.)

From now on, run everything in the **Ubuntu** terminal (Start → "Ubuntu"), not
PowerShell.

### Step 2 — Update Ubuntu and install the build toolchain
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  build-essential git zip unzip openjdk-17-jdk python3-pip python3-venv \
  autoconf automake libtool libtool-bin libltdl-dev autopoint gettext \
  pkg-config zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev
```
> The **full autotools set** (`automake`, `libtool-bin`, `libltdl-dev`,
> `autopoint`) matters: python-for-android rebuilds `libffi` with `autoreconf`,
> and without those packages it dies with
> `possibly undefined macro: LT_SYS_SYMBOL_USCORE`.

### Step 3 — Make Java 17 the default
Buildozer's Gradle step breaks on Java 21+. Confirm 17 is active:
```bash
java -version                              # should print 17.x
sudo update-alternatives --config java     # if not, pick the 17 entry
export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
```

### Step 4 — Get the code (clone inside the Linux filesystem!)
Clone into your WSL **home** directory (`~`), **not** `/mnt/c/...`. Building on
the Windows drive (`/mnt/c`) is extremely slow and hits case-sensitivity/permission
bugs.
```bash
cd ~
git clone https://github.com/ViciousSquid/Dosidicus.git
cd Dosidicus/android
```

### Step 5 — Python environment + Buildozer
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install buildozer "Cython==0.29.37"
pip install -r requirements.txt   # kivy/numpy/pillow — also lets you run on the desktop
```

### Step 6 — Build the APK
```bash
buildozer android debug
```
- The first run downloads the Android SDK/NDK into `~/.buildozer` and compiles
  Python + NumPy + Kivy for ARM — **20–40 min**. Later builds are minutes.
- If it prints an **Android SDK license** wall of text ending in `Accept? (y/N):`,
  type **`y`** and press Enter (repeat for each license). Non-interactive? run
  `yes | buildozer android debug`.
- The result appears as **`android/bin/dosidicus-0.1.0-arm64-v8a_armeabi-v7a-debug.apk`**.

### Step 7 — Put the APK on your phone
Two easy ways:

**A. Copy the file across (no cables).** From WSL your files are reachable in
Windows Explorer at `\\wsl$\Ubuntu-22.04\home\<your-unix-user>\Dosidicus\android\bin\`.
Copy the `.apk` to your phone (USB drive, Google Drive, email to yourself…), open
it on the phone, and allow **"install from unknown sources"** when prompted.

**B. Install over USB with adb.** Enable **Developer options → USB debugging** on
the phone, plug it in, then either:
```bash
buildozer android deploy run logcat   # installs, launches, streams logs
```
For USB to work *inside WSL2* you must attach the device with
[`usbipd-win`](https://learn.microsoft.com/windows/wsl/connect-usb): in an admin
PowerShell run `usbipd list`, then `usbipd bind --busid <id>` and
`usbipd attach --wsl --busid <id>`. If that's fiddly, just use method **A**, or
run `adb install -r <path-to-apk>` from **Windows** PowerShell (install
"platform-tools" on Windows) pointing at the APK under `\\wsl$\...`.

### WSL gotchas
- **Build in `~`, never `/mnt/c`** (speed + correctness).
- Out of space? `buildozer android clean` clears the app build; deleting
  `~/.buildozer` forces a fresh SDK/NDK download.
- To reclaim RAM after a big build: `wsl --shutdown` from PowerShell.

---

## Option C — Local build on native Linux

Same as the Windows steps above minus WSL — run Steps 2–6 directly on Ubuntu/Debian
(`sudo apt install …`, JDK 17, venv, `buildozer android debug`). The APK lands in
`android/bin/`; deploy with `buildozer android deploy run logcat`.

## Option D — Local build on macOS

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
| Gradle error mentioning an unsupported Java version | You're on Java 21+. Switch to **JDK 17** (Windows Step 3). |
| `possibly undefined macro: LT_SYS_SYMBOL_USCORE` while building libffi | Missing autotools m4 macros. Install the full set: `sudo apt install automake libtool libtool-bin libltdl-dev autopoint gettext`. |
| `Aidl not found`, or the license text hangs at `Accept? (y/N)` | The SDK licenses weren't accepted. Type `y`, or run `yes \| buildozer android debug`. |
| Painfully slow build / weird permission errors on Windows | You're building under `/mnt/c`. Clone and build inside the WSL home dir (`~`) instead. |
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
