
_"What if a Tamagotchi had a neural network and could learn stuff?"_
— [Gigazine](https://gigazine.net/gsc_news/en/20250505-dosidicus-electronicae/)

<p align="left">
  <img src="https://img.shields.io/badge/AI-Neural_Network-9C27B0?style=flat&logo=mindmeister&logoColor=white" height="20" alt="AI">
  <img src="https://img.shields.io/badge/License-GPL_v2-blue.svg?style=flat" height="20" alt="GPL-2.0">
  <img src="https://img.shields.io/badge/Translations-7-228B22?style=flat&logo=google-translate&logoColor=white&labelColor=333333" height="20" alt="Translations">
    <a href="https://buymeacoffee.com/vicioussquid"><img src="https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black" height="20" alt="Buy Me A Coffee"></a>
</p>

# _Dosidicus electronicus_

🦑 _A transparent cognitive sandbox disguised as a digital pet squid with a neural network you can **see thinking**_

Micro neural engine for small autonomous agents that learn via Hebbian dynamics and grow new structure

- Part **educational neuro tool**, part **sim game**, part **fever dream**
- [Build-your-own neural network ](https://github.com/ViciousSquid/Dosidicus/wiki/Brain-Designer) - learn neuroscience by raising a squid that **might develop irrational fears**
- Custom [simulation engine](https://github.com/ViciousSquid/Dosidicus/wiki/Engine-overview) using Numpy - **No Tensorflow or PyTorch**
- Most AI is a **black box**; Dosidicus is **transparent** - every neuron is visible, stimulatable, understandable.
- Starts with 8 neurons — grows via **neurogenesis** and rewires using **Hebbian learning**.
- Includes `achievements` with **50** to collect!
  
 
- -----------------------------
```
  Run main.py with Python 3.9 or greater after installing dependencies (requirements.txt)

```

 ### Windows Download: see [Releases](https://github.com/ViciousSquid/Dosidicus/releases) page

**Linux** users can try the experimental bash setup: :

```bash

curl -sSL https://raw.githubusercontent.com/ViciousSquid/Dosidicus/2.6.1.2_LatestVersion/linux_setup.sh | bash

```
 
----------------------------------

##  Here [is the wiki](https://github.com/ViciousSquid/Dosidicus/wiki) | Here [is changelog](https://github.com/ViciousSquid/Dosidicus/wiki/changelog) 

----------------------------

<img width="2482" height="980" alt="image" src="https://github.com/user-attachments/assets/02119926-47f7-4bfb-96b9-457d470064e4" />
 <img src="https://github.com/user-attachments/assets/496cec0d-0810-4f47-8618-11165e0dd50d" width="380">



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

--------------------------------------


### A year ago I got a **tattoo of this project** to celebrate its first development milestone!

<img src="https://github.com/user-attachments/assets/fe50e8d8-cb76-4b20-830a-ea6af28bb608" width="250">


---------------------------

**My dream**: Countless weird, neurotic, differently wired GPL squids living in sandboxes across the internet. (_**NOT** Skynet!_)

















