### _A transparent neural sandbox disguised as a digital pet_

----------------------------------

##  [Manifesto](https://github.com/ViciousSquid/Dosidicus/wiki/Cognitive-Sandbox-Manifesto-%7C-Artificial-Life-and-Transparent-Neural-Systems) |   [Wiki](https://github.com/ViciousSquid/Dosidicus/wiki) | [Changelog](https://github.com/ViciousSquid/Dosidicus/wiki/changelog) 

----------------------------

A micro neural engine for small autonomous agents that learn via Hebbian dynamics and grow new structure when exposed to novelty.

## Getting Started
New to Dosidicus? Start here to understand how to interact with your squid.
* **[Care Guide / Getting Started](../getting-started/Care-Guide.md)**
* **[Personalities](../neural-network/Personality.md)** — How different squid types behave.
* **[Decoration Window](../extras/Decoration-Window.md)** — Managing the squid's environment.

---


### Biological Autonomy
* **[Vision System](../neural-network/Vision-System.md)** — Realistic foraging and food detection.
* **[Hebbian Learning](../neural-network/Hebbian-Learning.md)** — The algorithm behind 30-second learning cycles.
* **[Neurogenesis](../neural-network/Neurogenesis.md)** — How the squid creates new neurons based on environment.
* **[Decision Engine](../engine/Decision-Engine.md)** — Making choices based on hunger, sleep, and memory.

### Engine Architecture & Logic
* **[Engine Overview](../engine/Engine-Overview.md)** — High-level system architecture.
* **[main.py](../source-reference/main.py.md)** — The main simulation loop.
* **[tamagotchi_logic.py](../source-reference/tamagotchi_logic.py.md)** — Core needs and health management.
* **[squid.py](../source-reference/squid.py.md)** — The physical squid class.
* **[Memory System](https://github.com/ViciousSquid/Dosidicus/blob/main/Docs/Memory%20System.md)** & **[memory_manager.py](../source-reference/memory_manager.py.md)** — Managing experiences.

---

## Tools & Configuration
Fine-tune the simulation and monitor the squid's neural activity.

### [The Brain Tool](../brain-tool/Network-Tab.md)
* **[Network Tab](../brain-tool/Network-Tab.md)** | **[Learning Tab](../brain-tool/Learning-Tab.md)**
* **[Memory Tab](../brain-tool/Memory-Tab.md)** | **[Decisions Tab](../brain-tool/Decisions-Tab.md)**
* **[Personality Tab](../neural-network/Personality.md-tab)**

### System Settings
* **[config.ini](../engine/config.ini.md)** — Adjusting simulation parameters.
* **[Save File Format](../engine/Save-File-Format.md)** — Structure of persisted data.
* **[Plugin System](../engine/Plugin-System.md)** — Extending the engine's capabilities.
