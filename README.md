"What if a Tamagotchi had a neural network and could learn stuff?"
— [Hackaday](https://hackaday.com/2025/04/26/digital-squids-behavior-shaped-by-neural-network/) , [Hackernews](https://news.ycombinator.com/item?id=43765748)

# _Dosidicus electronicus_
Digital pet squid with a dynamic neural network.

- Part neuroscience simulator, part Tamagotchi, part fever dream
- Hebbian learning & Neurogenesis - squid can create new neurons and become smarter

Combining AI with an electronic pet to transform "play" into "learning."
- [Design your own squid brain](https://github.com/ViciousSquid/Dosidicus/wiki/Brain-Designer) with GUI tools and watch it evolve and learn!
- Learn neuroscience by raising a squid that **might develop irrational fears** (or it might not!)
- Most AI is a **black box**. Dosidicus is **transparent** - every neuron is visible, stimulatable, and understandable.
- Custom [simulation engine](https://github.com/ViciousSquid/Dosidicus/wiki/Engine-overview) using Numpy - **does not use Tensorflow or Pytorch**
 
- -----------------------------

####   💿 Compiled binary for Windows is available on [Releases](https://github.com/ViciousSquid/Dosidicus/releases) page

 🌍 `English`, `Français`, `Español`, `Deutsch`, `中文`, `日本語`, and `Millennial` _("Bestie is literally starving rn")_.


##  Here is [wiki](https://github.com/ViciousSquid/Dosidicus/wiki) | Here is [changelog](https://github.com/ViciousSquid/Dosidicus/wiki/changelog)

----------------------------

<img width="2482" height="980" alt="image" src="https://github.com/user-attachments/assets/02119926-47f7-4bfb-96b9-457d470064e4" />
 <img src="https://github.com/user-attachments/assets/496cec0d-0810-4f47-8618-11165e0dd50d" width="380">

----------------------------

## Project Overview

**Project Name:** Dosidicus

**Description:** A Tamagotchi-style digital pet simulator with an integrated neural network brain. The pet learns, adapts, and requires user interaction for care, feeding, and training. Features customizable neural networks for diverse behaviors and personalities.

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

------------------

### The developer got a tattoo of this project. 
That either means it's good or he's unwell. Either way, it's commitment:

<img src="https://github.com/user-attachments/assets/fe50e8d8-cb76-4b20-830a-ea6af28bb608" width="250">

 <a href="https://www.buymeacoffee.com/vicioussquid" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="38" width="174"></a>

  "It thinks, therefore it inks"

























































































