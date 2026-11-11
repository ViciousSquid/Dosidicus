## Headless Brain Trainer
The trainer for Dosidicus brains: it raises a squid with no tank to draw, on the
same brain modules the game runs (`src/`), so what it trains is what the game plays.

There is one trainer. Use it from the command line, or watch and steer it from a
web page with `--serve`.

## Features

- **No window**: nothing is drawn, so it runs hundreds of ticks a second instead of the game's one
- **The game's own brain**: propagation, learning, growth and action selection are imported from `src/`, not reimplemented
- **Watch it live**: `--serve` shows the brain as it trains, in a browser
- **Custom brains**: load a brain from a JSON file (Brain Designer, the Squid Breeder, or an earlier run)
- **Growth for a reason**: a neuron grows only when the brain meets something it cannot represent, and records why
- **Reproducible**: one `--seed` gives the same trained brain every time
- **Training scenarios**: predefined conditions for different experiments
- **Export**: the trained brain is saved as JSON the game opens

## Installation

Nothing beyond what the game itself needs: Python 3 and NumPy. No window system is needed.
Run it from the repository, since it imports the game's `src/` modules.

```bash
# Make executable (optional)
chmod +x headless_trainer.py
```

## Quick Start

```bash
# Train with default brain for 10,000 ticks
python headless_trainer.py --ticks 10000 --output my_trained_brain.json

# Train a custom brain
python headless_trainer.py --brain my_custom_brain.json --ticks 20000 --output trained.json

# Use a predefined scenario
python headless_trainer.py --brain my_brain.json --scenario stress_test --output stress_trained.json

# List available scenarios
python headless_trainer.py --list-scenarios
```

## Watch it train: `--serve`

```bash
python headless/headless_trainer.py --serve
```

It prints an address (`http://127.0.0.1:8765/`); open it in a web browser. The page shows
the brain as it trains: every neuron glowing with its value, every connection, the squid's
drives over the run, its little world, what it chose to do, and each neuron it grows with
the reason the brain recorded for growing it. From the page you can:

- run, pause, and step 1, 10, 100 or 1000 ticks;
- set the speed, from one tick a second to as fast as it will go;
- intervene from outside (feed, startle, clean). These are recorded as interventions and
  drop any credit the squid's last action was waiting on, so it never learns your feeding
  as something it earned;
- start again from a seed, with a scenario, from a blank brain (the control), or with
  learning off;
- load a brain file and download the trained brain.

`--serve 9000` picks another port; `--brain`, `--seed`, `--blank` and `--scenario` set how
it starts. It listens only on this computer, and stops when you press Ctrl+C in its
terminal. `headless/serve.py` is the server, `headless/trainer.html` the page; both use
only the Python standard library and no outside scripts.

This page replaces the old browser "step trainer" (`extras/StepTrainer.html`) and the
command-builder launcher: those reimplemented or only described the trainer, and had
fallen behind it. To study a squid that has already lived, use `extras/Laboratory.html`.

## Command Line Options

| Option | Short | Description |
|--------|-------|-------------|
| `--brain FILE` | `-b` | Path to brain JSON file to load |
| `--output FILE` | `-o` | Path to save trained brain (auto-generated if not specified) |
| `--ticks N` | `-t` | Number of simulation ticks (default: 10000) |
| `--scenario NAME` | `-s` | Use a predefined training scenario |
| `--list-scenarios` | | List available training scenarios |
| `--progress N` | `-p` | Progress report interval (default: 500, 0=quiet) |
| `--quiet` | `-q` | Minimal output |
| `--learning-rate F` | | Override Hebbian learning rate |
| `--neurogenesis BOOL` | | Enable/disable neurogenesis |
| `--max-neurons N` | | Maximum neurons allowed |
| `--seed N` | | Reproducible run: the same seed, brain and tick count give the same trained brain |
| `--blank` | | Start from a blank 8-neuron brain with no wiring: the control condition |
| `--serve [PORT]` | | Train while you watch, from a page on this computer (default port 8765) |

## Training Scenarios

### `balanced`
Standard balanced training with normal event rates. Good for general-purpose brain development.

### `stress_test`
High anxiety/stress conditions to develop resilience neurons. Includes:
- Reduced food availability
- Increased startle events
- Scripted high-anxiety events

### `reward_rich`
Frequent positive outcomes to develop reward pathways. Includes:
- High food spawn rate
- Reduced negative events
- Scripted feeding events

### `novelty_exploration`
High curiosity environment with new objects. Good for developing exploration behaviors.

### `endurance`
Long-duration (50,000 ticks) training with varied conditions.

## Brain JSON Format

The trainer writes brains as `neurons` and `connections` (with everything the brain has
learned alongside), the format the game and the browser tools read. It also still reads
the older Brain Designer layout:

```json
{
  "metadata": {
    "name": "My Brain",
    "description": "Description of the brain"
  },
  "positions": {
    "hunger": {"x": 127, "y": 81, "is_custom": false},
    "custom_neuron": {"x": 450, "y": 250, "is_custom": true}
  },
  "weights": {
    "hunger,satisfaction": -0.3,
    "happiness,satisfaction": 0.4
  },
  "neuron_shapes": {
    "custom_neuron": "pentagon"
  },
  "output_bindings": []
}
```

### Core Neurons (cannot be removed)
- `hunger`, `happiness`, `cleanliness`, `sleepiness`
- `satisfaction`, `anxiety`, `curiosity`

### Input Sensors
- `can_see_food`, `external_stimulus`
- `can_see_plant` - not present at birth; grown the first time a plant comes within sight
- `is_eating`, `is_sleeping`, `is_sick`, `is_fleeing`, `is_startled`, `pursuing_food`

### Custom Neurons
Any neuron not in the core/sensor lists is treated as a custom neuron and will participate in Hebbian learning with boosted rates.

## Example Workflow

### 1. Create a custom brain in the Brain Designer
Use the [Brain Designer](https://github.com/ViciousSquid/Dosidicus/wiki/Brain-Designer) to create your architecture, then export it as JSON.

### 2. Train the brain headlessly
```bash
# Quick training
python headless_trainer.py -b my_design.json -t 50000 -o trained_v1.json

# Or with a scenario
python headless_trainer.py -b my_design.json -s stress_test -o stress_trained.json
```

### 3. Load the trained brain back into Dosidicus
Use the "Load Brain" button in the [Network tab](https://github.com/ViciousSquid/Dosidicus/wiki/Network-Tab) to load your trained brain.

## Training Tips

1. **Start with balanced training** to establish baseline connections
2. **Use stress_test** if you want resilience neurons for anxiety handling
3. **Use reward_rich** if you want strong satisfaction/happiness pathways
4. **Long training (50k+ ticks)** allows more sophisticated weight patterns to develop
5. **Multiple training rounds** with different scenarios can create well-rounded brains

## Performance

It runs the game's real brain code, so expect hundreds of ticks a second, not tens of
thousands: roughly 500-1,000 on an ordinary computer, a little less while a page is
watching. A 50,000 tick run takes about a minute.


## Integration with Dosidicus-2

The trained brain JSON files are fully compatible with:
- Brain Designer (import/export)
- Main game's "Load Brain" feature
- Save game custom brain storage

## License

Part of Dosidicus-2 project. [GPL-2.0 license](https://github.com/ViciousSquid/Dosidicus/blob/v2.6.1.0__b1218_LatestVersion/LICENSE)


## Measuring whether learning helps: `lifetime.py`

```
python headless/lifetime.py --seeds 6 --life 20000
```

Raises squid in the tank and, at intervals through each life, scores a
**frozen** copy of the brain - it cannot learn or grow during the test - in
worlds it was not raised in, next to its own newborn self. Reported in the
squid's real statistics (hunger, anxiety, happiness, health) and counts of
things its own brain chose to do (food eaten, shelter taken, rests chosen,
collapses). There is no combined score.

Two things make the comparison mean something:

- **The same world.** `TrainingConfig.world_seed` is the world's own random
  stream - where food lands, when a startle comes, where the plants are - and
  is drawn from identically whatever the squid does. Two brains scored on one
  world seed met the same food at the same moments.
- **Frozen.** `learning_enabled=False` stops plasticity, motor exploration,
  consolidation and growth; `frozen_trial` checks afterwards that not a weight
  or a neuron changed, and fails if one did.

The tank itself: plants stand at fixed places and are seen only within sight;
calm comes from choosing to shelter and getting there, and hiding ends a
fright; being dropped by exhaustion costs more than lying down; wanting food
with none in sight sends the squid looking.

`action_discovery_rate` (default 0.03) is how often an unwired action neuron
fires by itself; `action_discovery_teaching=False` is the placebo arm.
