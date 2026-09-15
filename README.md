# Experiment: Cups and food

> Tested with Dodisicus version **3.0.0.0** on 15/09/2026


<img src="https://github.com/user-attachments/assets/4937d2b3-3d01-4833-9fba-cfd960ee0b63" width="250">

> **Experimental branch.** This branch exists to run one experiment and write
> down what it found. For the project itself, see
> [`main`](https://github.com/ViciousSquid/Dosidicus).

---

## The question

**Can an unchanged [Dosidicus](https://github.com/ViciousSquid/Dosidicus) brain
learn to follow food it can no longer see?**

A three-cup shell game. Bait a cup where the squid can see it, shuffle the cups,
hide the food, and let the squid pick one. Three cups means a known chance rate
of 1/3, so "did it learn anything?" gets a number with an error bar instead of an
impression.

The constraint that shapes everything: **no new neurons and no new sensors.** The
squid gets no concept of a cup and no concept of a choice. It swims where its own
network sends it, and the experiment layer watches its ordinary position and
interprets. `can_see_food` keeps its existing meaning throughout — while the food
is under a cup it simply is not among the objects the vision worker is given.

## What it found

| measure | result |
|---|---|
| **Which cup does it go to?** | **No learning.** −1.1 pp against a learning-disabled control over ten seeds and 720 scored trials (p = 0.76). Never significant in any individual seed. |
| **Does it still want to eat once the food is hidden?** | **Real learning.** +7 pp and +19 pp in two independent replications, both p < 0.001, measured with plasticity frozen. |

**The squid does not learn *where* the food went. It does learn to go on
wanting it once it is gone.**

The first result was **predicted in advance** from a reading of the code rather
than discovered by trying and failing. Nothing the world writes into this network
distinguishes one cup from another — every sensor is a scalar with no spatial
content, and no action neuron is directional — so "the food is under the left
cup" is not a proposition this brain can represent, and experience cannot teach a
representation the architecture cannot form.

## → [Read the findings](experiment%20findings/)

| | |
|---|---|
| [**Architectural audit**](experiment%20findings/01-architectural-audit.md) | The capability analysis done before anything was built, and why it made one result a prediction. |
| [**Method and controls**](experiment%20findings/02-method-and-controls.md) | The protocol and every control, with the reasoning for each. |
| [**Results**](experiment%20findings/03-results.md) | All the numbers — per-seed, pooled, both replications. |
| [**What went wrong**](experiment%20findings/04-what-went-wrong.md) | Six artefacts that produced convincing wrong answers, including a false positive that was nearly published. |
| [**Limitations**](experiment%20findings/05-limitations.md) | What this does not show, and what would change the conclusion. |

## Running it

Play it — **Actions → Play: Cup & Food**:

```bash
pip install -r requirements.txt
python main.py
```

Or reproduce the measurements headlessly:

```bash
python headless/cup_experiment_runner.py --seed 200 --seeds 5 --naive 30 --train 50 --eval 50 --no-growth
python -m pytest tests/test_cup_experiment.py tests/test_cup_game_ui.py -q
```

The instrument is the real engine, not a model of it: a real `HeadlessBrain`, the
real `decision_engine.select_action`, and `can_see_food` computed by calling the
shipping `VisionWorker` directly.

## What's on this branch

| path | |
|---|---|
| `experiment findings/` | The findings, and the raw run logs behind them. |
| `src/cup_experiment.py` | Trial logic, records, scoring. Qt-free. |
| `headless/cup_experiment_runner.py` | The reproducible instrument. |
| `src/cup_game_ui.py` | The game in the tank. |
| `tests/test_cup_experiment.py` | 44 controls. |
| `tests/test_cup_game_ui.py` | 12 game-path tests. |
| `docs/cup_experiment.md` | How the thing works, for someone using it. |

One change outside the experiment: `RecordedSynapses.learning_frozen` in
`src/neural_provenance.py`, enforced inside the single method every synaptic
write passes through, so a frozen evaluation block genuinely cannot adapt while
it is being measured.
