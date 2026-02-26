`neurogenesis_show.py` is the **“showman” layer** that wraps the real `EnhancedNeurogenesis` engine and adds **player-facing spectacle** without touching any of the underlying biology, caps, or cooldown logic. The wrapper is enabled by default (via config.ini) and is meant to make neurogenesis more fun/game-like versus biologically accurate. 

Disable the wrapper and neurogenesis will behave in a **more scientifically accurate way** (better suited for actual biological/neuro experiments)

#### 1. Guarantee the player *sees* a neuron

- If the real engine **would** create a neuron, this wrapper **always lets it spawn** (respects the same caps/cooldowns).  
- If the real engine **would NOT** create one, the showman can still **force an extra “dramatic” neuron** when something cool happens—**but only if showmanship is enabled in config**.


#### 2. Detect “cool moments”

`NeurogenesisEvent` enum + `_detect_dramatic_moment()`  
Monitors every experience context for **visually obvious milestones**:

| Event | Typical Threshold |
|---|---|
| `ANXIETY_SPIKE` | anxiety ≥ 70 |
| `CURIOSITY_EXPLOSION` | curiosity ≥ 75 |
| `HUNGER_SATISFIED` | reward trigger + eating action |
| `MAX_HAPPINESS` | happiness ≥ 85 |
| `SPOTLESS_TANK` | cleanliness ≥ 90 |
| `FIRST_DECORATION_PUSH` | “decoration” or “push” in recent actions |

These are **intentionally permissive**—the goal is “player smiles,” not “perfect biology.”


#### 3. Manual event triggers (achievement integration)

`trigger_event(NeurogenesisEvent.FOO)`  
Lets **external systems** (achievements, tutorials, Easter-egg code) **request** a showman neuron.  
Returns `True` if one was actually spawned (respects cooldown & config flag).


#### 4. Cosmetic upgrades

- **_rename_for_drama()** – replaces auto-generated names like `stress_anxiety_regulation_3` with cinematic ones:  
  `trauma`, `wonder_trigger`, `satisfaction_burst`, `discovery_rush`, …  
- **_burst_color()** – gives the newborn neuron a **10-second gold/crimson/mint “super-pulse”** instead of the normal 5-second blink.  
- **_migrate_neuron()** – atomically renames **every dictionary key, animation tracker, visible set, weight tuple, etc.** so the new pretty name is safe everywhere.


#### 5. Achievement callbacks

`set_callbacks(on_dramatic_neuron=…, on_event_triggered=…)`  
Fires when:  
- a showman neuron is actually spawned, or  
- any `NeurogenesisEvent` is recorded

#### 6. Config-aware passthrough

- Reads `[Neurogenesis] showmanship = True/False` **each time** (hot-switchable).  
- When disabled the class becomes a **transparent proxy**: every call falls straight through to the real engine with zero overhead.  
- Public API surface **mirrors** `EnhancedNeurogenesis` (`create_neuron`, `should_create_neuron`, `get_global_cooldown_remaining`, …) so the rest of the codebase never knows a wrapper exists.


#### 7. Bookkeeping

- `last_showman_creation` – 15-second **cosmetic cooldown** (independent of the real engine’s 60-second biological cooldown).  
- `_triggered_events` set – prevents **exact duplicate** “first” events within the same session.  
- `reset_events()` – clears history for **new game** or **load save**.


### TL;DR
`neurogenesis_show.py` is the **marketing department** of the neuron factory: it **sprinkles confetti** (dramatic names, longer pulses, extra neurons on cool moments) while **never overruling** the real biologist downstairs—unless the player explicitly turns off the show, in which case it **vanishes silently**.