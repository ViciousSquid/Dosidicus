
_"What if a Tamagotchi had a neural network and could learn stuff?"_ - [Gigazine](https://gigazine.net/gsc_news/en/20250505-dosidicus-electronicae/) , [Hackaday](https://hackaday.com/2025/04/26/digital-squids-behavior-shaped-by-neural-network/)

<p align="left">
  <img src="https://img.shields.io/badge/AI-Neural_Network-9C27B0?style=flat&logo=mindmeister&logoColor=white" height="20" alt="AI">
  <img src="https://img.shields.io/badge/License-GPL_v2-blue.svg?style=flat" height="20" alt="GPL-2.0">
  <img src="https://img.shields.io/badge/Translations-7-228B22?style=flat&logo=google-translate&logoColor=white&labelColor=333333" height="20" alt="Translations">
    <a href="https://buymeacoffee.com/vicioussquid"><img src="https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black" height="20" alt="Buy Me A Coffee"></a>
</p>

# _Dosidicus electronicus_
### Learn neuroscience by [**raising a neural network as a pet**](https://github.com/ViciousSquid/Dosidicus/wiki/Raising-a-Neural-Network-as-a-Pet)
_A transparent cognitive sandbox disguised as a digital pet squid with a neural network you can **see thinking**_


- Part **educational neuro tool**, part **sim game**, part **fever dream**
- Combining 1990s virtual pet nostalgia with modern computational neuroscience.

### [Compiled binaries for Windows, MacOS and Linux](https://github.com/ViciousSquid/Dosidicus/releases)

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

## [Manifesto](https://github.com/ViciousSquid/Dosidicus/wiki/Cognitive-Sandbox-Manifesto-%7C-Artificial-Life-and-Transparent-Neural-Systems) | [Changelog](https://github.com/ViciousSquid/Dosidicus/wiki/changelog) | [Wiki](https://github.com/ViciousSquid/Dosidicus/wiki) (53 pages)

---

## **Why this exists**

Modern AI systems are astonishing—but they're also opaque.

Dosidicus explores a different question:

What if you could understand every neuron inside a learning creature?

The project is designed to make artificial cognition visible.

Instead of hiding intelligence inside millions of parameters, Dosidicus starts with just eight neurons. Every connection can be inspected. Every activation can be visualised. Every learned behaviour can be traced back to experience.

As the squid lives, its brain rewires itself through Hebbian learning, strengthens useful pathways using [STDP](https://github.com/ViciousSquid/Dosidicus/wiki/Spike%E2%80%90Timing%E2%80%90Dependent-Plasticity-(STDP)), and grows entirely new neurons through neurogenesis.

No two brains ever develop the same way.

Every save file becomes a permanent cognitive history.

## As the caretaker you will

- Feed, clean and care for your squid.
- Introduce it to new experiences.
- Watch neurons fire in real time.
- Watch memories form and influence future behaviour.
- Observe fears, habits and preferences emerge.
- Raise a brain unlike anyone else's.

#### Under the hood runs [**STRINg** simulation engine](https://github.com/ViciousSquid/Dosidicus/wiki/Engine-overview):

* Built from scratch in NumPy
* No TensorFlow. No PyTorch. No NEAT.
* Fully visible neuron activations
* Structural growth over time
* Dual memory system
* Headless training mode

Most AI is a black box: Dosidicus lets you see the mind forming - every neuron is visible, stimulatable, understandable.

The squid isn't driven by scripted behaviours—it develops through experience. By watching its brain change over time, you can explore how simple learning rules give rise to increasingly complex behaviour.

Want the full conceptual philosophy behind Dosidicus? Read the [Cognitive Sandbox Manifesto](https://github.com/ViciousSquid/Dosidicus/wiki/Cognitive-Sandbox-Manifesto-%7C-Artificial-Life-and-Transparent-Neural-Systems)

---

## [Share Your Squid](https://github.com/ViciousSquid/Squid-Exchange)

No two squids are wired the same.

- Early interactions permanently alter their structure (good or bad!).
- Tiny differences amplify.
- Habits form. Fears emerge. Personalities drift.

Your squid's brain is a cognitive history - shaped by you.

So [share it](https://github.com/ViciousSquid/Squid-Exchange).

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

-  41,636 lines, one developer, 28 months, GPL 2.0 license

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
