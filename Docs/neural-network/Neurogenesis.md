`neurogenesis.py` is the brains’ stem-cell layer: it decides when, why, and how new neurons appear, makes sure they are immediately functional, keeps the network within size & specialization limits, and cleans up the least useful ones—all through a single, auditable pipeline.

#### Unified neuron creation
* `create_neuron()` – the only public entry-point used by the UI, BrainWorker, save-load, etc.
* `create_functional_neuron()` – internal helper that always produces a FunctionalNeuron.
* All neurons are converted into FunctionalNeuron objects

#### Context-aware experience tracking
* `ExperienceContext` – a snapshot of why the neuron is being made (trigger type, brain state, environment, outcome, recent actions).
* `ExperienceBuffer` – rolling FIFO buffer (≈ 50 experiences) that counts how often each specific / parent / core pattern recurs; used to decide when a neuron should actually be spawned.
* `NeurogenesisTriggerSystem` – state-delta detection (novelty spikes, stress surges, reward rebounds).

#### Functional specialization & wiring
* Every neuron gets a specialization string (feeding_satisfaction, filth_avoidance, object_investigation, …) derived from the context.
* `get_functional_connections()` – returns a weighted connection list to existing neurons so the new cell is immediately useful instead of random.
* `_make_reciprocal_connections()` – guarantees that any outgoing connection ≥ 0.2 gets a matching incoming link so the new neuron can activate/be activated.

#### Placement & visuals
* `_calculate_functional_position()` – places the neuron near the neurons it will influence, not at random.
* `_set_neuron_appearance()` – shape (diamond / square / triangle) and color palette encode type and specialization so users can “read” the brain at a glance.

#### Soft & hard limits
* Per-type caps (max_per_type) – e.g. max 3 stress, 5 novelty, 4 reward.
* Per-specialization caps (max_per_specialization) – prevents 20 identical “hunger_stress_response” clones.
* Global neuron cap (max_neurons) – total network size ceiling.
* Cooldown – minimum seconds between any creation event.
* Pattern-recurrence thresholds – neuron spawns only after a pattern has repeated 2–5× (depending on specificity).

#### Strengthening instead of duplication
If a cap is hit, the system boosts an existing neuron (strength_multiplier, utility_score) rather than creating a redundant one.

#### Pruning & housekeeping
* `intelligent_pruning()` – removes the lowest-utility neuron that is > 5 min old, considering activation recency, uniqueness of specialization, and total synaptic weight.
* `_rebuild_new_neurons_details_for_lab()` – guarantees the Laboratory “newest neurogenesis neurons” card always has origin data.

#### State integration & runtime updates
* `update_neuron_activations()` – every tick, functional neurons compute their value from incoming weights; stress neurons collectively suppress anxiety (bi-directional feedback).
* Emits pulse animations for weights ≥ 0.15 (can be disabled).

#### Persistence & save/load
* `to_dict()` / `from_dict()` – serializes the entire `ExperienceBuffer`, every `FunctionalNeuron`, counters, and creation history.
* `ensure_all_neurons_functional()` – on load, converts any legacy neurons discovered in [brain_widget](../source-reference/brain_widget.py.md) into FunctionalNeuron instances so the system stays unified.

#### Achievement hooks
`set_achievement_callbacks()` – lets the Achievements module receive “neuron created” and “neuron leveled” events for trophies.