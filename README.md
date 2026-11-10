
_"What if a Tamagotchi had a neural network and could learn stuff?"_ - [Gigazine](https://gigazine.net/gsc_news/en/20250505-dosidicus-electronicae/) , [Hackaday](https://hackaday.com/2025/04/26/digital-squids-behavior-shaped-by-neural-network/)

<p align="left">
  <img src="https://img.shields.io/badge/AI-Neural_Network-9C27B0?style=flat&logo=mindmeister&logoColor=white" height="20" alt="AI">
  <img src="https://img.shields.io/badge/License-GPL_v2-blue.svg?style=flat" height="20" alt="GPL-2.0">
  <img src="https://img.shields.io/badge/Translations-7-228B22?style=flat&logo=google-translate&logoColor=white&labelColor=333333" height="20" alt="Translations">
    <a href="https://buymeacoffee.com/vicioussquid"><img src="https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black" height="20" alt="Buy Me A Coffee"></a>
</p>

> ### #1 `weird` topic project on GitHub — and #2 `simulation-game`.

# _Dosidicus electronicus_
### Learn neuroscience by **raising a neural network as a pet**
_A transparent cognitive sandbox disguised as a digital pet squid with a neural network you can **see thinking**_


- Part **educational neuro tool**, part **sim game**, part **fever dream**
- Combining 1990s virtual pet nostalgia with modern computational neuroscience.

### [Download for Windows, Linux and Android](https://github.com/ViciousSquid/Dosidicus/releases)

```bash
git clone https://github.com/ViciousSquid/Dosidicus.git
cd Dosidicus
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate (Windows)
pip install -r requirements.txt
python main.py
```

<img src="https://github.com/user-attachments/assets/02119926-47f7-4bfb-96b9-457d470064e4" width="900">
<img src="https://github.com/user-attachments/assets/496cec0d-0810-4f47-8618-11165e0dd50d" width="380">

---

## [Manifesto](https://github.com/ViciousSquid/Dosidicus/wiki/Cognitive-Sandbox-Manifesto-%7C-Artificial-Life-and-Transparent-Neural-Systems) | [Changelog](https://github.com/ViciousSquid/Dosidicus/wiki/changelog) | [Wiki](https://github.com/ViciousSquid/Dosidicus/wiki) (57 pages)

---

## **Why this exists**

What if you could understand every neuron inside a learning creature?

The project is designed to make artificial cognition visible.

Instead of hiding intelligence inside millions of parameters, Dosidicus starts with just eight core neurons: seven drives and the one sense a squid cannot live without. The brain is drawn in labelled rows — the drives across the top, the motor bank underneath them (one neuron per thing the squid can do, driven by ordinary synapses rather than by a rule), and the senses below that. Every connection can be inspected. Every activation can be visualised. Every learned behaviour can be traced back to experience.

As the squid lives, its brain rewires itself through Hebbian learning, strengthens useful pathways using [STDP](https://github.com/ViciousSquid/Dosidicus/wiki/Spike%E2%80%90Timing%E2%80%90Dependent-Plasticity-(STDP)), works out which of its own actions cause which consequences, tries out things it was never wired to do and keeps the ones that help, and grows an entirely new neuron when there is something it has no way to represent.

And it can tell you all of it. Every synaptic change and every grown neuron records **why** — the mechanism, the evidence, the experience, the action, the consequence — and the brain tools read that record rather than reconstructing an approximation of it:

> *"Why did this weight change from 0.31 to 0.47?"*
> *"Why does this neuron exist?"*
> *"What does the squid know about food?"*

No two brains ever develop the same way.

## "Why believe it?"

**Not faked:** there is [one learning engine](https://github.com/ViciousSquid/Dosidicus/blob/3.1_LatestVersion/src/plasticity.py) shared by the GUI, the headless trainer, and the test suite — the squid cannot learn differently depending on which interface watches it. Every weight change records its mechanism, evidence, and triggering experience.

## Does it actually get smarter?

It has to be shown, so it is measured. A squid is raised in the headless tank; at intervals a **frozen** copy of its brain - nothing about it can change - is dropped into worlds it has never seen, alongside its own newborn self, and what happens to each is recorded in the squid's real statistics.

What that shows, on eight squid over a 20,000-tick life (`python headless/lifetime.py --seeds 8`):

| Frozen, in unseen worlds | At birth | After 20,000 ticks |
|---|---|---|
| Mean anxiety | 76.1 | 53.1 (every squid between 41 and 59) |
| Food eaten | 10.0 | 10.1 |
| Mean hunger | 33.5 | 34.0 |
| Mean health | 94.3 | 92.5 (seven unchanged; one at 80 - see below) |
| Neurons grown | 0 | the same two in every squid; one squid grew two more |

Nobody told it how. Each squid saw a plant and grew a sense for one (`can_see_plant`); tried sheltering, at first for no reason; found that it helped only when it was frightened *and* a plant was in sight; had no neuron for that combination, so grew one (`anxiety_high_and_sees_plant`); and from then on hid when frightened. Cut the one synapse it learned and the ability is gone. The controls - no plants, exploring without learning from it, no exploring - each remove it too (`tests/test_learning_to_live.py`).

**It is not always right, and is not meant to be.** A squid has no way of knowing what is true; it has what happened to it. One of the eight took to lying down when startled, on its own evidence, and was hurt more for it. A single striking coincidence is enough for a belief - it inks, and another squid that was leaving anyway leaves, and it comes to think ink drives squid off, and to ink when one appears. If the next squid stays, it finds that out too, drops the belief and the habit, and remembers having been wrong. All of it is recorded as what the squid believes and why, never as fact.

Three rules make that possible:

* **What the squid *does* is learned from what came of it.** A synapse into an action neuron is moved only when the action was tried with a cue and without it and turned out differently - never by co-activation, which can only teach a squid to do more of what it already does.
* **A neuron is grown only for something the squid cannot represent**: a thing it perceives and has no sense for, one of its own actions it cannot tell from another, or a combination its own trials show an action depends on. Anything else it lacks is a synapse, and is left to learning.
* **A neuron grown for a combination is silent until everything it stands for is there**, is named for what it means, and is taken back if nothing ever comes to depend on it.

It is a small squid in a small tank, and that is all this claims.

## As the caretaker you will

- Feed, clean and care for your squid.
- Introduce it to new experiences.
- Watch neurons fire in real time.
- Read, in plain English, everything it has learned and what taught it.
- Trace any synapse back to the experience that changed it.
- Watch memories form and influence future behaviour.
- Observe fears, habits and preferences emerge.
- Raise a brain unlike anyone else's.
- Follow its life in **View > Journey**: what it has become, judged on what is true of its brain, and what comes next.

#### Under the hood runs [**STRINg** simulation engine](https://github.com/ViciousSquid/Dosidicus/wiki/Engine-overview):

* Built from scratch in NumPy
* No TensorFlow. No PyTorch - [Read the actual learning engine](https://github.com/ViciousSquid/Dosidicus/blob/3.1_LatestVersion/src/plasticity.py)
* [Wire your own](https://github.com/ViciousSquid/Dosidicus/wiki/Brain-Designer) squid brain, add or erase entire behaviours
* Fully visible neuron activations
* Full provenance: every weight change and every new neuron records its cause
* Structural growth only for what cannot be represented — a new neuron appears for a percept, an action or a combination the brain has no neuron for, never as a patch for a drive
* Motor exploration and outcome-taught action synapses — unwired actions are tried, and wired only when trying them with a cue and without it came out differently
* Honest senses — a plant is something the squid sees through its view cone or does not know about
* Action → consequence learning with temporal credit assignment
* Dual memory system
* Headless training mode, running the identical engine

Most AI is a black box: Dosidicus lets you see the mind forming - every neuron is visible & understandable.

The squid isn't driven by scripted behaviours — it develops through experience. By watching its brain change over time, you can explore how simple learning rules give rise to increasingly complex behaviour.

Want the full conceptual philosophy behind Dosidicus? Read the [Cognitive Sandbox Manifesto](https://github.com/ViciousSquid/Dosidicus/wiki/Cognitive-Sandbox-Manifesto-%7C-Artificial-Life-and-Transparent-Neural-Systems)

---

## [Share Your Squid](https://github.com/ViciousSquid/Dosidicus/tree/SQUID-EXCHANGE)

No two squids are wired the same.

- Early interactions permanently alter their structure (good or bad!).
- Tiny differences amplify.
- Habits form. Fears emerge. Personalities drift.

Your squid's brain is a cognitive history - shaped by you.

So [share it](https://github.com/ViciousSquid/Dosidicus/tree/SQUID-EXCHANGE).

- Export save files and let others explore your squid's neural structure.
- Post screenshots of strange activation patterns and unexpected growth.
- Show bizarre learned behaviors (Why is yours afraid of poop?)
- Compare cognitive histories and trace how experience shaped structure.

- Did yours grow 40 neurons?
- Did it develop a persistent avoidance loop?
- Did you accidentally create a neurotic reward spiral?

Every squid is an experiment.

---

## Docker

Two targets are provided: `headless` (CLI trainer) and `gui` (PyQt5 app with X11).

Headless (recommended for containers):
```bash
docker build -t dosidicus:headless --target headless .
docker run --rm -v ${PWD}/headless_output:/app/output dosidicus:headless --ticks 10000 --output /app/output/trained_brain.json
```

GUI (Linux host with X11 or WSLg):
```bash
docker build -t dosidicus:gui --target gui .
docker run --rm \
  -e DISPLAY=$DISPLAY \
  -e QT_X11_NO_MITSHM=1 \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v ${PWD}/saves:/app/saves \
  -v ${PWD}/logs:/app/logs \
  dosidicus:gui
```

Compose:
```bash
docker compose up --build
docker compose --profile gui up --build
```

WSLg note: If the GUI fails to start with a Qt platform plugin error, try:
```bash
export QT_QPA_PLATFORM=wayland
docker compose --profile gui up --build
```

Note: On Windows without WSLg, you will need an X server and a valid `DISPLAY` value to run the GUI container.

Note: Attempting to build the Docker container on Windows ARM64 will fail because there is no pyqt5 wheel [[32]](https://github.com/ViciousSquid/Dosidicus/pull/32) -  Use the prebuilt binary from [releases](https://github.com/ViciousSquid/Dosidicus/releases/) instead

Troubleshooting (quick):
- If `DISPLAY` is empty in WSL: WSLg is not active. Use WSLg or run an X server on Windows.
- If Docker errors mention `docker_engine`/pipe not found: start Docker Desktop and ensure WSL integration is enabled.
- If GUI still exits with Qt plugin errors: rebuild the image (`docker compose --profile gui build --no-cache`) and retry.

---

## Technical Overview

### Build a macOS DMG installer

In GitHub **Actions**, select **Build (Nuitka)**, then **Run workflow** on
`3.2.0_LatestVersion`. The workflow builds native Apple Silicon and Intel apps,
checks their signatures and startup, then creates and verifies compressed DMGs.
Download `nuitka-macos-arm64-dmg` (Apple Silicon) or `nuitka-macos-x64-dmg`
(Intel) from the run's **Artifacts** section and extract the `.dmg` file.
Open it and drag **Dosidicus.app** onto the **Applications** shortcut, then
eject the disk image and launch the app from Applications.

The **Release all platforms** workflow also includes both versioned DMGs and
their SHA-256 checksums in the release assets. The apps are ad-hoc signed;
Developer ID signing and Apple notarization are not configured. macOS may
require approval under **System Settings → Privacy & Security → Open Anyway**.
Saves and settings are stored in `~/Library/Application Support/Dosidicus`.

- **Dependencies:**
  - Python ^3.9
  - PyQt5 ^5.15 (GUI framework)
  - numpy ^1.21 (neural network computations)
  - **OPTIONAL** onnxruntime or onnxruntime-directml ([more info](https://github.com/ViciousSquid/Dosidicus/wiki/AI-accelerator-support))
- **Core Structure:** Modular codebase in `src/` including brain designer, decision engine, learning algorithms, personality traits, memory management, UI components, and interaction systems. Entry point via `main.py`.

### Key Project Components
- **Plugin System:** Extensible architecture with built-in plugins for achievements (tracking milestones) and multiplayer (networked interactions).
- **Save System:** Persistent saves in `saves/` for pet states, autosaves, and achievement logs.
- **Headless Mode:** Standalone training and simulation in `headless/` for GUI-less operation, ideal for background training or server environments (experimental)
- **Custom Brains:** Library of pre-configured neural networks in `custom_brains/` (e.g., "Plant-Seeker", "Insomniac") for quick behavior setup.
- **Memory Management:** Dual memory system (`_memory/`) with long-term and short-term storage for learning persistence.
- **Examples and Tools:** Example squids, configuration files (`config.ini`), and version tracking.

---

### A year ago I got a **tattoo of this project** to celebrate its first development milestone!

<img src="https://github.com/user-attachments/assets/fe50e8d8-cb76-4b20-830a-ea6af28bb608" width="250">

---

![Visitors](https://api.visitorbadge.io/api/visitors?path=ViciousSquid&label=UNIQUE%20VISITORS&countColor=%2326313f&style=flat)

