### version 2.6.1.2
`23 Feb 2026`

* Optional [hardware AI accelerator support via ONNX Runtime](../neural-network/AI-Accelerator-Support.md) - _Experimental, disabled by default_

* NEW: [brain_to_keras.py](https://github.com/ViciousSquid/Dosidicus/blob/2.6.1.2_LatestVersion/extras/brain_to_keras.py) (from the dev branch) in the `extras` folder - _attempts to convert a Dosidicus brain.json to Keras v3 (experimental)_

* Improved Brain Tool short-term and long-term memory tabs: **more varied and verbose memories**
* **Random Humboldt squid facts** can occasionally appear in status bar
* FIXED: BrainTool Hebbian timers weren't in sync [(20)](https://github.com/ViciousSquid/Dosidicus/issues/20)
* FIXED squid now properly goes to sleep when sleepiness=max

-------------------------


### version 2.6.1.1
`20 Feb 2026`

### Milestone 2
* Added `linux_setup.sh`
* Code optimisations & bug fixes

-------------------------

### version 2.6.1.0

`21 Jan 2026`

#### build 1219
* Translation files for 7 languages: _English_, _French_, _Spanish_, _German_, _Chinese_, _Japanese_, _Millennial_
* [Stable release for Windows](https://github.com/ViciousSquid/Dosidicus/releases/tag/v2.6.1.0)

`18 Dec 2025`

#### build 1218 **Milestone 2** Release 
* Integrated Designer into Brain Tool
* Added ability to create custom neurons
* NEW: [Headless brain trainer](https://github.com/ViciousSquid/Dosidicus/blob/v2.6.1.0__b1218_LatestVersion/headless/README_headless_trainer.md) with accelerated time epochs
* NEW: Global preferences window
* Added an additional 4 custom brains
* French and Spanish Translations (_does not currently include Designer_)

-------------------

### version 2.6.0.3
`11 Dec 2025`

* Added FEED, CLEAN, MEDICINE buttons to UI
* Added 5 example [custom brains](https://github.com/ViciousSquid/Dosidicus/tree/2.6.0.2_latest_release/custom_brains)
* Neuron/font sizes and other UI elements now configurable via config.ini
* FIXED: missing `update_score` method in `StatisticsWindow`
* [Brain Designer](../brain-tool/Brain-Designer.md) can now import current running brain from Brain Tool
* NEW: Neuron output bindings can be used to create simple IF THEN behaviours for the squid

-------------------

### version 2.6.0.2
`8 Dec 2025`

* NEW: [Brain Designer](../brain-tool/Brain-Designer.md) - create your own custom squid brains!
* NEW: 5 custom brain templates that can be edited however you like [[dir](https://github.com/ViciousSquid/Dosidicus/tree/2.6.0.1_latest_release/custom_brains)]
* NEW: [Example squid](../getting-started/Example-Squids.md) **Miroslav**

-------------------

### version 2.5.0.0
`3 Dec 2025`

* New [Save Viewer](../extras/SaveViewer.md)
* Added 8 additional plant decorations & associated stats
* Brain Network tab now has buttons for Experience Buffer and Neuron Laboratory
* Fixed a bug where the brain state was not being restored properly from save
* Added [showman wrapper](../source-reference/neurogenesis_show.py.md) for Neurogenesis
* Code refactoring and removal of legacy cruft (pre version 2.4.X)
* Feature-complete stable code-base 

-------------------

### version 2.4.5.1 _patch_
`25 Nov 2025`

* [Engine](../engine/Engine-Overview.md) update - Neurogenesis and hebbian calculations now in own thread so UI remains responsive
* **New**: Improved [multiplayer](../engine/Multiplayer.md) plugin!!
* **New**: [Achievements](../extras/Achievements.md) (50 to collect)
* **New**: Full interactive tutorial when starting a new game
* Every squid is born with a `uuid` that stays with him his entire life
* Added [Neuron Laboratory](../brain-tool/Neuron-Laboratory.md) via the View menu or by double clicking any neuron



-------------------

### version 2.4.5.0
`15 Nov 2025`

* Improved [plugin manager](../engine/Plugin-System.md)
* Massively overhauled and [improved](../source-reference/neurogenesis_show.py.md) neurogenesis
* Track statistics such as squid age, distance travelled, total foods eaten, etc
* Improved load/save mechanism (backward compatible with v2.3 saves and earlier)
* Hebbian now trains on 2 active neuron pairs at once
* Redesigned Brain Tool [learning tab](../brain-tool/Learning-Tab.md)
* Global counters now respect game speed
* Arcade-style (High-Score) system
* Animations throughout the UI


-------------------

### version 2.4.4.1
`04 Sept 2025`

* Code cleanup and stability improvements
* WIP: Track statistics such as squid age, distance travelled, total foods eaten, etc
* ADDED: Small chance of squid creating an ink cloud when startled
* ADDED: Experimental [multiplayer](../engine/Multiplayer.md) plugin

-------------------

### version 2.4.3

Milestone 1

**Initial stable release**

### **AUTHOR GOT A TATTOO** to celebrate 1 year of this project!

<img src="https://github.com/user-attachments/assets/fe50e8d8-cb76-4b20-830a-ea6af28bb608" width="250">

  <a href="https://www.buymeacoffee.com/vicioussquid" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>