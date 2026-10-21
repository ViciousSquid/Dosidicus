### CANARY - Peer-to-peer evolution *PREVIEW*

`October 2026` [[CANARY]](https://github.com/ViciousSquid/Dosidicus/tree/CANARY) branch - _not yet a release_

#### Squid visit, fight, mate and die - and it stays with them

Every squid is driven by its own network: nothing it does to another squid is scripted, and what happens to it changes it for good. [Story gallery](https://github.com/ViciousSquid/Dosidicus/tree/CANARY/docs/story-gallery) - two networked desktops and an Android visit, captured running.

* **Venturing out:** a squid senses a nearby aquarium (it grows an `aquarium_nearby` sense) and decides with its own network to visit; it comes home when afraid or tired, and always to sleep.
* **Remote minds:** a visitor's body swims in the host's tank while its brain keeps running at home; its own tank says whose tank it is visiting.
* **Social senses are grown, never given:** `can_see_squid`, `squid_nearby` and the social play, fight, flee and aggression neurons grow only from encounters, with provenance. They sit on a new **SOCIAL** band in the Brain Network tab and are pruned like any neuron when they stop being useful.
* **Fights:** started by a grown aggression neuron and won by ability - personality, experience and condition. The object fought over flashes dark red, one cloud covers the scuffle, and a fight leaves a lasting mark.
* **Rocks and poop:** aimed throws powered by the network, with a stray that narrows with practice; a squid closes in when its target is out of reach, and goes for a squid it remembers badly before a nearer stranger. Hits are felt, never explained. Poop does no harm, but it is not a rock.
* **Recognition:** each encounter becomes a memory of that individual squid. New **Social** page in the Memory tab and a social card in the Neuron Laboratory.
* **Mating and inheritance:** a pixel heart beats over a pair that has just mated; the resident lays an egg and, as a parent, stops eating. The hatchling inherits half its weights from each parent, each synapse recorded with the parent it came from.
* **Life and death:** squid can die of neglect, sickness, starvation as a parent, or their injuries. Every dead squid gets a headstone; hover over it for the epitaph (name, age, fights won and lost). An egg hatching is a new game.
* **Achievements:** CIRCLE OF LIFE, Fisticuffs!, Scuffle, Tussle and Slugfest.
* **Consent:** multiplayer asks before it goes on, and warns that encounters change a squid permanently.
* **Android:** the same lifecycle (deaths, headstones, eggs, matings, hatchlings), live visits over Nearby and rock throws. A visit carries on with the Nearby screen closed; Disconnect ends it.
* **Protocol:** documented in [`plugins/multiplayer/docs`](https://github.com/ViciousSquid/Dosidicus/tree/CANARY/plugins/multiplayer/docs) and hardened: no private state on the wire, whole datagrams read, bounded decompression, messages accepted only from a visit's own nodes.
* **Language first:** the language picker appears before anything else starts.
* **Brain Network tab:** "Hebbian Cycle" now counts the cycles the brain has run (saved with it); the countdown to the next one is on the Learning tab. The network scales to fit the Brain Tool window.
* **Releases:** tagged builds for Windows, Windows ARM64, macOS, Linux and Android; signed release APK built by CI.

* **Bug Fixes**

  - Fixed a crash when an egg hatched after a visit.
  - Readable in macOS dark mode (and any dark theme): memory cards, the Neuron Laboratory and the Statistics tab were white text on light backgrounds.
  - Retina Macs: the tank, the squid and everything in it are sized as designed. The window was shrunk while sprites were drawn twice their size, so the squid filled a third of the tank; the Brain Tool no longer opens covering the screen.
  - The Brain Network view scales to fit the Brain Tool instead of being drawn too big and cut off.
  - Host and visiting squid swim on opposite frames, and always animate.
  - Visitors are labelled with their name.

---

### version 3.1.0.0 (Milestone 5) *LATEST RELEASE*

`September 2026`

#### STRINg v3

Major cognitive architecture upgrade.

* **Decision engine:** Completely removed all hard-coded behaviours: squid is now entirely neural network driven
* **Integrated learning:** Hebbian learning, STDP, sleep consolidation, causal learning and plasticity are now core STRINg systems rather than separate learning plugins.
* **Adaptive neurogenesis:** the brain can detect representational deficits and grow neurons to address them.
* **Neural provenance:** synaptic and structural changes retain records of where they came from and why they occurred.
* **Knowledge Tab:** new tools expose learned knowledge, relationships and their provenance in human-readable form.
* **Causal learning:** the squid can learn relationships between its actions and their consequences.
* **Social cognition:** multiplayer encounters can become individual-specific experiences and memories.
* **Remote minds:** visiting squids retain their own brains while interacting with remote environments.
* **Android:** new Android implementation with mobile UI and Nearby multiplayer support.
* **Headless training:** expanded support for running and training squids without the graphical interface.
* **Brain Tool:** redesigned neural anatomy view with CORE, SENSES and ACTIONS rows, animated brain growth and improved neuron inspection.
* **Testing:** substantially expanded organism-level tests covering learning, causality, neurogenesis, persistence, multiplayer and statistics.
* **NEW:** Windows ARM64 binary (made possible by [PyQt5-WinARM64](https://github.com/ViciousSquid/PyQt5-WinARM64))

---

### version 2.6.5.0 (Milestone 4)
`24 July 2026`

* **Bug Fixes**

  - Corrected boolean value handling across neural and tool interfaces.
  - Improved decoration-based vision input and external-state rendering updates.
  - Fixed tooltip binary-neuron detection and connection effect application.
* NEW: [sleep_replay plugin](https://github.com/ViciousSquid/Dosidicus/wiki/Sleep-Replay-&-Consolidation) - memories are replayed/consolidated and weights updated during sleep
* STDP is now enabled by default
* Optimised hot-paths
* Redesigned Decisions tab with confidence gauges, action rankings, drive meters and live thought narration.
* Working macOS and Android debug APK builds (_need testers_)

----------------------------

### version 2.6.3.0
`28 March 2026`

*
* NEW: [Squid Breeder tool](https://github.com/ViciousSquid/Dosidicus/wiki/SquidBreeder.html)
* No changes to any code _(version still reports as 2.6.2)_


----------------------------


### version 2.6.2.0 (Milestone 3)
`7 Mar 2026` `11 Mar 2026`

*
* Adjusted `base_learning_rate` from `0.1` to `0.12`
* Improved tutorial animations
* `sleepiness` now increases more slowly 
* Added an extra digit to score counter
* Fixes throughout the UI for high DPI displays
* NEW: Debug > export neurons and weights
* Added **new system hooks** and [whitelist](https://github.com/ViciousSquid/Dosidicus/blob/2.6.2.0_LatestVersion/plugins/whitelist.txt) to **plugin_manager**
* NEW: [STDP](https://github.com/ViciousSquid/Dosidicus/wiki/Spike%E2%80%90Timing%E2%80%90Dependent-Plasticity-(STDP)) plugin ([m3](https://github.com/ViciousSquid/Dosidicus/milestone/3))
* Learning tab is now STDP aware
* Nuitka binaries for Windows, Linux and MacOS
* Added docker support [ pull #[32](https://github.com/ViciousSquid/Dosidicus/pull/32) ] (_thanks_ **oxyec**)
* Updated [Save Viewer](https://github.com/ViciousSquid/Dosidicus/wiki/SaveViewer.html)

----------------------

### version 2.6.1.2 
`05 Mar 2026`

* 
* Added [Cognitive Sandbox Manifesto](https://github.com/ViciousSquid/Dosidicus/wiki/Cognitive-Sandbox-Manifesto-%7C-Artificial-Life-and-Transparent-Neural-Systems)
* Optional [hardware AI accelerator support via ONNX Runtime](https://github.com/ViciousSquid/Dosidicus/wiki/AI-accelerator-support) - 🔵 _Experimental, disabled by default_
* NEW: [brain_2_keras.py](https://github.com/ViciousSquid/Dosidicus/blob/2.6.3.0_LatestVersion/extras/brain_2_keras.py) in the `extras` folder - _convert a brain.json to Keras v3 _(_ 🔵 _experimental )_
* Improved Brain Tool short-term and long-term memory tabs: **more varied and verbose memories**
* FIXED: BrainTool Hebbian timers weren't in sync [(20)](https://github.com/ViciousSquid/Dosidicus/issues/20)
* FIXED a bug that prevented squid from sleeping sometimes when sleepiness was high _(see below)_
* NEW BUG: sleepiness increases too fast - squid goes to sleep quickly _(see above)_
* NEW: Squid-related educational facts in UI (can be disabled via settings)
* Cleaned up [Wiki](https://github.com/ViciousSquid/Dosidicus/wiki), added `Docs` folder

-------------------------


### version 2.6.1.1
`20 Feb 2026`  [[2.6.1.1__b1220_(milestone-2)]](https://github.com/ViciousSquid/Dosidicus/tree/2.6.1.1__b1220_(milestone-2)) branch

*
* Added `linux_setup.sh`
* Code optimisations & bug fixes

-------------------------

### version 2.6.1.0

`21 Jan 2026`

#### build 1219

*
* Translations for `English`, `French`, `Spanish`, `German`, `Chinese`, `Japanese` and `Millennial`
* _Change language from the Preferences window_

`18 Dec 2025`

#### build 1218 

*
* Integrated Designer into Brain Tool
* Added ability to create custom neurons
* NEW: [Headless brain trainer](https://github.com/ViciousSquid/Dosidicus/tree/2.6.2.0_LatestVersion/headless)
* NEW: Global preferences window
* Added an additional 4 custom brains
* French and Spanish Translations (_does not currently include Designer_)

-------------------

### version 2.6.0.3
`11 Dec 2025`

*
* Added FEED, CLEAN, MEDICINE buttons to UI
* Added 5 example [custom brains](https://github.com/ViciousSquid/Dosidicus/tree/2.6.0.2_latest_release/custom_brains)
* Neuron/font sizes and other UI elements now configurable via config.ini
* FIXED: missing `update_score` method in `StatisticsWindow`
* [Brain Designer](https://github.com/ViciousSquid/Dosidicus/wiki/Brain-Designer) can now import current running brain from Brain Tool
* NEW: Neuron output bindings can be used to create simple IF THEN behaviours for the squid

-------------------

### version 2.6.0.2
`8 Dec 2025`

*
* NEW: [Brain Designer](https://github.com/ViciousSquid/Dosidicus/wiki/Brain-Designer) - create your own custom squid brains!
* NEW: 5 custom brain templates that can be edited however you like [[dir](https://github.com/ViciousSquid/Dosidicus/tree/2.6.0.1_latest_release/custom_brains)]
* NEW: [Example squid](https://github.com/ViciousSquid/Dosidicus/wiki/Example-squids) **Miroslav**

-------------------

### version 2.5.0.0
`3 Dec 2025`

*
* New [Save Viewer](https://github.com/ViciousSquid/Dosidicus/wiki/SaveViewer.html)
* Added 8 additional plant decorations & associated stats
* Brain Network tab now has buttons for Experience Buffer and Neuron Laboratory
* Fixed a bug where the brain state was not being restored properly from save
* Added [showman wrapper](https://github.com/ViciousSquid/Dosidicus/wiki/neurogenesis_show.py) for Neurogenesis
* Code refactoring and removal of legacy cruft (pre version 2.4.X)
* Feature-complete stable code-base 

-------------------

### version 2.4.5.1 _patch_
`25 Nov 2025`

*
* [Engine](https://github.com/ViciousSquid/Dosidicus/wiki/Engine-overview) update - Neurogenesis and hebbian calculations now in own thread so UI remains responsive
* **New**: Improved [multiplayer](https://github.com/ViciousSquid/Dosidicus/wiki/Multiplayer) plugin!!
* **New**: [Achievements](https://github.com/ViciousSquid/Dosidicus/wiki/Achievements) (50 to collect)
* **New**: Full interactive tutorial when starting a new game
* Every squid is born with a `uuid` that stays with him his entire life
* Added [Neuron Laboratory](https://github.com/ViciousSquid/Dosidicus/wiki/Neuron-Laboratory) via the View menu or by double clicking any neuron



-------------------

### version 2.4.5.0
`15 Nov 2025`

*
* Improved [plugin manager](https://github.com/ViciousSquid/Dosidicus/wiki/Plugin-system)
* Massively overhauled and [improved](https://github.com/ViciousSquid/Dosidicus/wiki/neurogenesis_show.py) neurogenesis
* Track statistics such as squid age, distance travelled, total foods eaten, etc
* Improved load/save mechanism (backward compatible with v2.3 saves and earlier)
* Hebbian now trains on 2 active neuron pairs at once
* Redesigned Brain Tool [learning tab](https://github.com/ViciousSquid/Dosidicus/wiki/Learning-Tab)
* Global counters now respect game speed
* Arcade-style (High-Score) system
* Animations throughout the UI


-------------------

### version 2.4.4.1
`04 Sept 2025`

*
* Code cleanup and stability improvements
* WIP: Track statistics such as squid age, distance travelled, total foods eaten, etc
* ADDED: Small chance of squid creating an ink cloud when startled
* ADDED: Experimental [multiplayer](https://github.com/ViciousSquid/Dosidicus/wiki/Multiplayer) plugin

-------------------

### version 2.4.3.0

`June 2024`  [[2.4.3.0__legacy_(milestone-1)]](https://github.com/ViciousSquid/Dosidicus/tree/2.4.3.0__legacy_(milestone-1)) branch

Milestone 1

**Initial public release**

---------------------

### **AUTHOR GOT A TATTOO** to celebrate 1 year of this project!

<img src="https://github.com/user-attachments/assets/fe50e8d8-cb76-4b20-830a-ea6af28bb608" width="250">

  <a href="https://www.buymeacoffee.com/vicioussquid" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>