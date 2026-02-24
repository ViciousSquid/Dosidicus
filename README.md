

"What if a Tamagotchi had a neural network and could learn stuff?"
— [Gigazine](https://gigazine.net/gsc_news/en/20250505-dosidicus-electronicae/) , [Hackaday](https://hackaday.com/2025/04/26/digital-squids-behavior-shaped-by-neural-network/)

# _Dosidicus electronicus_

<p align="left">
  <img src="https://api.visitorbadge.io/api/VisitorHit?user=ViciousSquid&repo=Dosidicus&countColor=%237B1E7A&style=flat" height="20" alt="Visitors">
  <img src="https://img.shields.io/badge/License-GPL_v2-blue.svg?style=flat" height="20" alt="GPL-2.0">
    <img src="https://img.shields.io/badge/AI-Neural_Network-9C27B0?style=flat&logo=mindmeister&logoColor=white" height="20" alt="AI">
  <img src="https://img.shields.io/badge/Languages-7-228B22?style=flat&logo=google-translate&logoColor=white&labelColor=333333" height="20" alt="Translations">
    <a href="https://buymeacoffee.com/vicioussquid"><img src="https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black" height="20" alt="Buy Me A Coffee"></a>
</p>

#### Digital pet squid with a dynamic neural network and a retro vibe

- Part **educational neuro tool**, part **sim game**, part **fever dream**
- 🦑 [Design your own tiny GPL squid brain](https://github.com/ViciousSquid/Dosidicus/wiki/Brain-Designer) and watch it evolve and learn!
- Learn neuroscience by raising a squid that **might develop irrational fears** (or it might not!)
- Most AI is a **black box**; Dosidicus is **transparent** - every neuron is visible, stimulatable, understandable.
- Custom [simulation engine](https://github.com/ViciousSquid/Dosidicus/wiki/Engine-overview) with using Numpy - **does not use Tensorflow or Pytorch**

  
 
- -----------------------------

####   💿 Compiled binary for Windows is available on [Releases](https://github.com/ViciousSquid/Dosidicus/releases) page

There is a linux setup script: [linux_setup.sh](https://github.com/ViciousSquid/Dosidicus/blob/2.6.1.2_LatestVersion/linux_setup.sh) (untested! please test it!)



##  Here [is wiki](https://github.com/ViciousSquid/Dosidicus/wiki) | Here [is changelog](https://github.com/ViciousSquid/Dosidicus/wiki/changelog) 

----------------------------

<img width="2482" height="980" alt="image" src="https://github.com/user-attachments/assets/02119926-47f7-4bfb-96b9-457d470064e4" />
 <img src="https://github.com/user-attachments/assets/496cec0d-0810-4f47-8618-11165e0dd50d" width="380">

------------------

### A year ago I got a **tattoo of this project** to celebrate its first development milestone!

<img src="https://github.com/user-attachments/assets/fe50e8d8-cb76-4b20-830a-ea6af28bb608" width="250">


-----------------------------------


## Project Overview

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

















