# Android 3.1 engine and release

Android now imports the desktop cognitive implementation rather than maintaining
its own learning, propagation and decision rules. The Kivy UI and tank/body
adapter remain mobile-specific.

The shared implementation includes:

- `src/portable_brain.py`: the headless data adapter, also imported by the CLI trainer.
- `src/brain_constants.py`: newborn drives, sensors, motor neurons, innate synapses,
  motor competition, thresholds and bindings.
- `src/propagation.py`: transfer function, external action representations and
  learned influences on physiology.
- `src/plasticity.py`: signed Hebbian learning and directional STDP.
- `src/neural_provenance.py`, `causal_learning.py`, `capability.py`: the actual
  evidence, action/outcome credit, and persistent deficits that justify growth.
- `src/neurogenesis.py`: functional growth, regulation, specialization and pruning.
- `src/consolidation.py` and `sleep_consolidation.py`: waking evidence and sleep replay.
- `src/memory_manager.py`: memory storage, promotion and expiration; Android supplies
  an in-memory store and simulation clock.
- `src/neuron_binding.py`: the same threshold, edge and cooldown conditions used
  by desktop actuators.
- `plugins/achievements/achievements_data.py`: the shared achievement definitions.

Cognitive ticks run once per simulated second, independently of render FPS.
The body follows its selected neural action every frame. There are no Android
hunger/personality/memory score multipliers deciding the winner. Parallel reflexes
and custom neuron bindings can also drive the body. Visiting squids run their
imported networks rather than a scripted food/rock priority list.

## Brain interchange

The menu has **Export brain (.json)** and **Import brain (.json / .zip)** separately
from exporting/importing the whole squid. JSON imports accept Desktop Designer
`neurons`/`connections`, trainer `positions`/`weights`, and game brain-state data.
They preserve directed inhibitory/excitatory synapses, positions, activations,
shapes, bindings, represented actions, functional growth and learning history.
Validation finishes before replacing the current brain. Importing a brain keeps
the pet, tank, lifetime statistics and memories.

On desktop, use the Network tab's **Load Brain** button to load an Android brain
JSON. The desktop loader now restores its cognitive history as well as its
structure. Export the desktop Designer brain to JSON to load it on Android.
Whole-squid ZIP exports include desktop-shaped `game_state.json` and
`brain_state.json`, plus a separate `mobile_state.json` for exact mobile round trips.
Old Android saves are migrated to the motor bank without erasing learned weights.

All four applications use `src/brain_io.py` to read brain JSON and the authoritative
`brain_state.json` inside save ZIPs. Designer Save and Export preserve cognitive
history and do not silently wire orphan neurons. Mobile autosaves now use the same
ZIP writer as desktop SaveManager (`src/save_archive.py`); old `squid_save.json`
files are read and migrated to `squid_save.zip`. Desktop edits to the public save
sections override any older mobile extension. The interoperability matrix exercises
the real desktop save/get/set APIs, Designer save/load, and trainer file API.

Use **Name & colour** in the mobile menu to name the squid and preview a tint.
Cancel restores its previous tint; Natural restores the original artwork. The
resident has a name badge, and names/tints survive desktop/mobile save interchange.
Nearby advertisements use the chosen name. A single animated fight cloud covers
the two nearby squids after they approach each other.

The first on-screen encounter grows one persistent novelty-class concept named
**Social** or **Encounter**. Its provenance records **“Other squid encountered!”**,
the visible-peer signal and initial connections. A positive perception-to-concept
synapse drives it, with an initial positive connection to Anxiety. Experience
can strengthen or weaken this association. Repeated encounters reuse it, ordinary pruning retains it,
and the name, birth record and learned weights travel through all brain formats.
A fresh newborn brain starts without this concept.

Android reads selected document URIs through ContentResolver, supporting scoped
storage and cloud file providers. Exports use Downloads and the Android share
sheet. On API 24–28, legacy Downloads access still requires storage permission.

## Mobile tools

The Network view draws directed arrows and separate reciprocal connections;
double-tap a neuron to inspect its recorded origin and weights. The Knowledge,
Growth, Learning and Decisions tabs show the real engine's records. The mobile
Brain Designer edits directed weights, creates/removes custom neurons, binds
outputs, and provides Undo. Simulation pauses while editing. A persistent footer
keeps Undo and Save accessible on small displays. Medicine is available in the menu.

## Test and capture

```bash
python -m pip install -r requirements.txt pytest
QT_QPA_PLATFORM=offscreen python -m pytest tests android/tests -q

# Run the touch UI on a desktop:
python -m pip install -r android/requirements.txt
python android/main.py

# Capture actual phone-sized Kivy screenshots to a separate directory:
python android/tools/capture_gallery.py /tmp/dosidicus-gallery
# On a Linux machine without a display, Mesa/SDL can use:
# SDL_VIDEODRIVER=offscreen LIBGL_ALWAYS_SOFTWARE=1 <command above>
```

Tests compare the mobile adapter with the shared desktop rules, exercise
plasticity and physiology, import the real desktop JSON formats, use the actual
desktop loader in the reverse direction, verify save/history/binding round trips,
and start the staged engine with Qt/Kivy imports forbidden.

## Build and signing

Use JDK 17, Buildozer 1.6.0 and the native tools listed in BUILDING.md. The spec
pins the python-for-android 2026.05.09 release commit. **Run
`python android/prepare_apk.py` before invoking Buildozer.** This stages the
actual desktop sources, translations, shared achievement definitions and mobile
UI into `android/.buildozer/mobile-source`; it also writes a SHA-256 source manifest.
The resulting APK contains that staged code, not an older independent engine.
Both GitHub Actions workflows stage and test it before building.

```bash
cd android
python prepare_apk.py
buildozer android release
```

`android/build_release.sh` can build and then sign using `DOSIDICUS_KEYSTORE`,
`DOSIDICUS_STOREPASS_FILE`, `DOSIDICUS_KEY_ALIAS` (default `dosidicus`) and optional
`DOSIDICUS_KEYPASS_FILE`. Set `ANDROID_SDK_ROOT` to the SDK directory. Passwords
are read from files by apksigner after compilation, so they are not passed into
Buildozer's verbose build environment diagnostics. The script verifies the
signature and alignment. Without signing configuration it produces an unsigned
release APK and reports that explicitly.

A new release signing identity was requested because the original key was lost.
An installation signed with the old key cannot be updated with the new key.
Export the squid first, uninstall the old app, install the new APK, then import
the squid ZIP. Back up the new keystore and its password securely for future
updates; neither belongs in Git.

This change does not reproduce Qt windows or load desktop Qt plugins in Kivy.
Desktop LAN discovery and Android Nearby Connections remain separate transports.
UI rendering and engine tests on Linux do not establish Android device behavior;
installation, document-provider access, sensor input and Nearby permissions must
also be tested on a phone before distribution.
