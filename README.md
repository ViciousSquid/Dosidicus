What if a Tamagotchi had a neural network and could learn stuff?
# _Dosidicus electronicus_
Digital pet squid with a dynamic neural network.

- Part educational neuro tool and part sim game
- Features Hebbian learning, Neurogenesis and a retro aesthetic

- [Design your own squid brain](https://github.com/ViciousSquid/Dosidicus/wiki/Brain-Designer) with GUI tools and watch it evolve and learn!
- Entirely custom [simulation engine](https://github.com/ViciousSquid/Dosidicus/wiki/Engine-overview) - **does not use Tensorflow or Pytorch**
- Supports (optional) [hardware AI accelerators via ONNX Runtime](https://github.com/ViciousSquid/Dosidicus/wiki/AI-accelerator-support) (experimental)
- Rejects the standard "black box" approach in favour of transparent, biologically inspired learning.

- -----------------------------

###   💿 Compiled binaries for Windows are available on [Releases](https://github.com/ViciousSquid/Dosidicus/releases) page

###  user guide and technical stuff can be found on the [wiki](https://github.com/ViciousSquid/Dosidicus/wiki)

<img width="2482" height="980" alt="image" src="https://github.com/user-attachments/assets/02119926-47f7-4bfb-96b9-457d470064e4" />
 <img src="https://github.com/user-attachments/assets/496cec0d-0810-4f47-8618-11165e0dd50d" width="380">


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

Thank you for your interest in my project! Please fork and contribute!
































































