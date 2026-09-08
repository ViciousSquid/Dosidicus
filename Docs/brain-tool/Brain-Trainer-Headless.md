A headless training tool is included in the `headless` folder. This can be used to train brains in a time-accelerated environment 

* **Headless Operation**: No GUI required, runs purely on CPU
* **Accelerated Time**: thousands of ticks per second (vs ~1 tick/second in real-time)
* **The same engine as the game**: propagation, plasticity, spike timing, causal
  learning, sleep consolidation, capability diagnosis and neurogenesis are all
  imported from `src/`, so a brain trained here behaves identically when the
  squid runs it. None of those modules needs Qt.
* **Capability-driven neurogenesis**: new structure appears when the network
  persistently cannot represent, regulate or express something — the same
  question the game asks.
* **Provenance**: the trainer records why every weight moved and why every
  neuron exists, the same as the game does
  (`brain.explain_weight(...)`, `brain.explain_neuron(...)`).
* **Training Scenarios**: Predefined scenarios for different training goals
* **Export Trained Brains**: Save trained brains back to JSON for use in the main game

### A note on time

One tick is one second of the squid's life. The trainer advances simulated
seconds with the ticks, and the neurogenesis engine reads that clock instead of
the wall clock, so `neurogenesis_cooldown` means what it says even when 1 500
ticks run per real second. Before v4.0 the trainer had its own propagation
(no neutral baseline, a 0.1 timestep, clamped to −100…100), its own Hebbian
rule (a non-negative product, so a trained brain could not contain a single
inhibitory synapse) and its own growth thresholds — a brain trained here was
simply not the same object the game ran.

Documentation for this tool can be found here: https://github.com/ViciousSquid/Dosidicus/blob/v2.6.1.0__b1218_LatestVersion/headless/README_headless_trainer.md

#### Still experimental, but it now trains the same brain the game runs.


#### `headless_launcher.html` is a user-friendly launcher for this tool: drag and drop or Browse for a brain and then select how to train it and for how long

<img src="https://github.com/user-attachments/assets/3fdc4814-85ca-434f-a7c8-ef311131377b" width="800">