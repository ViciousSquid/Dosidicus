# Dosidicus Mobile (Android / Kivy port)

A touch-first Android version of **Dosidicus electronicus** — the digital pet
squid with a neural network you can *watch* think. This is a ground-up
reimplementation of the presentation layer in **Kivy** (the desktop app is
PyQt5, which cannot run on Android), wrapped around a faithful, GUI-free port of
the original **STRINg** cognitive engine.

You raise a squid: feed it, clean its tank, play with it, let it sleep — and its
8-neuron brain rewires itself through Hebbian learning and grows entirely new
neurons through neurogenesis. Tap **Brain** to watch every neuron fire and every
connection strengthen in real time. No two squids develop the same way, and the
whole cognitive history is saved between launches.

<p align="center">
  <img src="docs/screenshots/tank.png" width="360" alt="Tank view">
  <img src="docs/screenshots/brain.png" width="360" alt="Brain view">
</p>
<p align="center"><em>Tank view (raise your squid) &nbsp;·&nbsp; Brain view (watch it think — gold rings mark neurons grown by neurogenesis)</em></p>

---

## Why a reimplementation and not a repackage

The desktop app is ~46k lines of PyQt5. PyQt5 has no Android target, so the Qt
UI (brain widget, designer, memory tabs, plugins) can't be shipped in an APK.
What *is* portable is the cognitive core — the maths of learning, neurogenesis,
personality and decision-making. This port therefore:

* **reuses the engine logic** by porting it into a clean `engine/` package that
  imports **only** Python + NumPy (no Qt, no Kivy), and
* **rebuilds the UI** in Kivy as a phone-friendly, touch-driven interface.

## Project layout

```
android/
├── main.py                      # Kivy entry point (python main.py)
├── buildozer.spec               # Android APK build config
├── requirements.txt             # desktop dev deps
├── assets/                      # squid sprites (reused from the desktop images/)
├── tests/test_engine.py         # engine unit tests (no GUI needed)
└── dosidicus_mobile/
    ├── engine/                  # PORTABLE cognitive core — no PyQt5, no Kivy
    │   ├── constants.py         # the 7 core neurons + sensors  (from brain_constants.py)
    │   ├── personality.py       # personality types + learning modifiers
    │   ├── brain.py             # NeuralBrain: Hebbian learning + neurogenesis + NumPy propagation
    │   ├── squid.py             # needs dynamics, care actions, neural decision engine
    │   └── simulation.py        # tick loop + world (food/poop) + save/load
    └── ui/                      # Kivy presentation layer
        ├── tankview.py          # the aquarium: squid, food, poop (tap to feed)
        ├── brainview.py         # the live, inspectable neural network
        ├── stats.py             # the seven need/emotion bars
        └── app.py               # app shell, Clock loop, care buttons, autosave
```

## How the desktop engine maps onto the port

| Desktop (`src/`)                | Mobile (`dosidicus_mobile/engine/`) | Notes |
|--------------------------------|--------------------------------------|-------|
| `brain_constants.py`           | `constants.py`                       | Same 7 core neurons + `can_see_food`; positions kept on a virtual canvas so the brain view rescales to any screen. |
| `personality.py`, `personality_traits.py`, learning modifiers in `learning.py` | `personality.py` | Same 7 personalities and per-personality learning/stat modifiers. |
| `learning.py` (`HebbianLearning`) | `brain.py`                        | `strengthen_connection`, `learn_from_eating/playing/cleaning/curiosity/anxiety` ported; adds a continuous, framerate-independent Hebbian rule. |
| `neurogenesis.py` + brain_widget growth | `brain.py`                    | Novelty/stress/reward triggers grow new neurons that wire into the network. Runs on an internal simulation clock (not wall-clock) so it behaves the same in tests and fast-forward. |
| `decision_engine.py` (v4.0)    | `squid.py` (`Squid.decide`)          | Neural-first weighting of eat/explore/play/comfort/sleep with personality flavour. |
| `tamagotchi_logic.py` (update loop, food) | `simulation.py`           | Needs drift, food/poop, eating, save/load — the Qt scene/graphics are gone. |
| `brain_widget.py` (visualiser) | `ui/brainview.py`                    | Neurons as heat-mapped circles, weighted colour-coded connections, gold rings on grown neurons. |

### What's in this MVP
Raising loop (feed/clean/play/sleep + tap-to-feed), 7 live core stats, sickness,
the full brain (Hebbian learning + neurogenesis) with a live visualiser, the
neural decision engine, 7 personalities, and persistent JSON saves.

### Not in this first pass
Brain Designer, plugins (achievements/multiplayer), the memory tabs, custom
brains and the tutorial. The engine is structured so these can be layered on.

## Run on desktop (fastest way to try it)

```bash
cd android
pip install -r requirements.txt
python main.py
```

Tap the tank to drop food, use the care buttons, and hit **Brain** to watch the
network learn. Leave it running and you'll see connections thicken and — after a
few minutes of engaged (or neglected) care — new neurons appear.

## Run the engine tests (no display required)

```bash
cd android
python tests/test_engine.py        # or: python -m pytest tests
```

## Build the Android APK

**See [BUILDING.md](BUILDING.md) for the full step-by-step guide** (cloud build,
local Linux/WSL/macOS, deploying to a phone, and the dev loop).

Two quick paths:

* **No local setup — build in the cloud.** Push a change under `android/` (or use
  the Actions tab → *Build Android APK* → *Run workflow*). The
  [`android-build.yml`](../.github/workflows/android-build.yml) workflow builds
  the debug APK on a GitHub runner and uploads it as the `dosidicus-debug-apk`
  artifact.
* **Local build** (Linux/WSL/macOS, downloads the SDK/NDK on first run):
  ```bash
  cd android
  pip install buildozer "Cython==0.29.37"
  buildozer android debug          # APK lands in android/bin/
  buildozer android deploy run logcat   # install + launch on a connected device
  ```

Notes:
* First build is slow (it fetches the SDK, NDK, and builds NumPy for ARM); use
  **JDK 17** — newer JDKs can break the Gradle step.
* `numpy` and `pillow` build via their python-for-android recipes — already
  listed in `buildozer.spec`'s `requirements`.
* Saves are written to the app's private data directory, so no storage
  permission is required.

## Design notes

* **Framerate-independent learning.** The Hebbian update and counter decay scale
  by `dt`, so a phone at 30/60 fps and the test-suite fast-forward learn at the
  same real-world rate.
* **Experience-driven neurogenesis.** New neurons are triggered by *lived*
  events — novelty (new food entering perception), reward (eating/play), and
  sustained stress (high anxiety) — not by routine ticking. That's why an
  engaged squid grows `reward` neurons while a neglected one grows `defense`
  neurons.
* **Everything persists.** The squid's stats, position, personality, every
  weight and every grown neuron serialise to JSON and reload on next launch.
