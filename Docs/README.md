
_"What if a Tamagotchi had a neural network and could learn stuff?"_
— [Gigazine](https://gigazine.net/gsc_news/en/20250505-dosidicus-electronicae/)

<p align="left">
  <img src="https://img.shields.io/badge/AI-Neural_Network-9C27B0?style=flat&logo=mindmeister&logoColor=white" height="20" alt="AI">
  <img src="https://img.shields.io/badge/License-GPL_v2-blue.svg?style=flat" height="20" alt="GPL-2.0">
  <img src="https://img.shields.io/badge/Translations-7-228B22?style=flat&logo=google-translate&logoColor=white&labelColor=333333" height="20" alt="Translations">
    <a href="https://buymeacoffee.com/vicioussquid"><img src="https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black" height="20" alt="Buy Me A Coffee"></a>
</p>

# _Dosidicus electronicus_

🦑 _A transparent neural sandbox disguised as a digital pet squid with a neural network you can **see thinking**_

Micro neural engine for small autonomous agents that learn via Hebbian dynamics and grow new structure

- Part **educational neuro tool**, part **sim game**, part **fever dream**
- [Build-your-own neural network ](https://github.com/ViciousSquid/Dosidicus/wiki/Brain-Designer) - learn neuroscience by raising a squid that **might develop irrational fears**
- Custom [simulation engine](https://github.com/ViciousSquid/Dosidicus/wiki/Engine-overview) using Numpy - **No Tensorflow or PyTorch**
- Most AI is a **black box**; Dosidicus is **transparent** - every neuron is visible, stimulatable, understandable.
- Starts with 8 neurons — grows via **neurogenesis** and rewires using **Hebbian learning**.
- Includes `achievements` with **50** to collect!

 <img src="https://github.com/user-attachments/assets/23e98046-23a6-44a1-b4c8-a57abfff5501" width="180">
 
- -----------------------------

---

### Getting Started

| Page | Description |
|------|-------------|
| [Home](getting-started/Home.md) | Project overview |
| [Care Guide](getting-started/Care-Guide.md) | How to look after your squid |
| [Example Squids](getting-started/Example-Squids.md) | Pre-made squid configurations |
| [Changelog](getting-started/Changelog.md) | Version history |

---

### STRINg Simulation Engine

| Page | Description |
|------|-------------|
| [Engine Overview](engine/Engine-Overview.md) | High-level architecture |
| [Decision Engine](engine/Decision-Engine.md) | How the squid makes choices |
| [Data Flow Summary](engine/Data-Flow-Summary.md) | How data moves through the system |
| [Plugin System](engine/Plugin-System.md) | Extending Dosidicus with plugins |
| [Plugin Hooks](engine/Plugin-Hooks.md) | Available hook points |
| [Save File Format](engine/Save-File-Format.md) | Structure of `.squid` save files |
| [config.ini](engine/config.ini.md) | Configuration reference |
| [Multiplayer](engine/Multiplayer.md) | Multiplayer support |

---

### Neural Network

| Page | Description |
|------|-------------|
| [Technical Overview](neural-network/Technical-Overview.md) | Neural network architecture |
| [Hebbian Learning](neural-network/Hebbian-Learning.md) | Weight update algorithm |
| [STDP](neural-network/STDP.md) | Spike-Timing-Dependent Plasticity |
| [Neurogenesis](neural-network/Neurogenesis.md) | Creating new neurons at runtime |
| [Experience Buffer](neural-network/Experience-Buffer.md) | Short/long-term memory experiences |
| [Vision System](neural-network/Vision-System.md) | Food detection via vision cone |
| [Personality](neural-network/Personality.md) | The 7 personality types |
| [AI Accelerator Support](neural-network/AI-Accelerator-Support.md) | Hardware acceleration options |

---

### Brain Tool

| Page | Description |
|------|-------------|
| [Brain Designer](brain-tool/Brain-Designer.md) | GUI for designing custom brains |
| [Brain Trainer (Headless)](brain-tool/Brain-Trainer-Headless.md) | CLI training without a GUI |
| [Network Tab](brain-tool/Network-Tab.md) | Visualising the neuron network |
| [Learning Tab](brain-tool/Learning-Tab.md) | Monitoring learning in real time |
| [Memory Tab](brain-tool/Memory-Tab.md) | Inspecting memory contents |
| [Decisions Tab](brain-tool/Decisions-Tab.md) | Watching decision-making live |
| [Personality Tab](brain-tool/Personality-Tab.md) | Adjusting personality traits |
| [Neuron Laboratory](brain-tool/Neuron-Laboratory.md) | Experimenting with individual neurons |

---

### Source Reference

Documentation for individual source files:

| File | File |
|------|------|
| [main.py](source-reference/main.py.md) | [brain_tool.py](source-reference/brain_tool.py.md) |
| [squid.py](source-reference/squid.py.md) | [brain_widget.py](source-reference/brain_widget.py.md) |
| [tamagotchi_logic.py](source-reference/tamagotchi_logic.py.md) | [brain_worker.py](source-reference/brain_worker.py.md) |
| [memory_manager.py](source-reference/memory_manager.py.md) | [brain_render_worker.py](source-reference/brain_render_worker.py.md) |
| [vision_worker.py](source-reference/vision_worker.py.md) | [brain_neuron_hooks.py](source-reference/brain_neuron_hooks.py.md) |
| [custom_brain_loader.py](source-reference/custom_brain_loader.py.md) | [brain_neuron_outputs.py](source-reference/brain_neuron_outputs.py.md) |
| [designer_window.py](source-reference/designer_window.py.md) | [neurogenesis_show.py](source-reference/neurogenesis_show.py.md) |

---

### Extras

| Page | Description |
|------|-------------|
| [Achievements](extras/Achievements.md) | Unlockable achievements |
| [Easter Eggs](extras/Easter-Eggs.md) | Hidden features |
| [Decoration Window](extras/Decoration-Window.md) | Customising the environment |
| [SaveViewer](extras/SaveViewer.md) | Browser-based save file inspector |
| [UUID](extras/UUID.md) | Squid identity system |
