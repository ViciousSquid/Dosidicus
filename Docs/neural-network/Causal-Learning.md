# Causal learning — what the squid's own actions cause

Correlation is not causation, and until v4.0 the squid only had correlation:
plasticity noticed that two neurons moved together, and that was the whole of
its understanding. A creature that only correlates cannot answer *"what did I
do that made that happen?"* — the difference between noticing that food and
satisfaction co-occur and knowing that **eating** produces the satisfaction.

`src/causal_learning.py` supplies the missing half.

## 1. Action episodes

Every time the squid commits to a behaviour — eating, exploring, throwing,
seeking a plant, fleeing, sleeping — an episode opens, recording the **cue**:
the sensors that were far from neutral plus the drives that were most extreme.

Continuing the same behaviour is one episode. Returning to it later, after the
previous bout's outcome window has closed, is a fresh observation — and a
contingency needs repeated observations before the squid believes it.

## 2. The outcome window

The episode stays open for `outcome_window` seconds (default 6). When it
closes, the change in every drive over that window is the measured
**consequence**, and a weighted sum of those changes is its **valence**.

## 3. Contingency, not co-occurrence

Two corrections separate a contingency from a coincidence.

**Baseline drift.** The consequence is compared against how the same drive
moves over identical windows while that action is *not* running:

> Hunger fell 24 while eating. Hunger drifts *up* 0.4 otherwise.

Without it the squid would credit "exploring" with the hunger it accumulates
simply by existing.

**Cue competition.** Actions overlap constantly — a squid is exploring while it
notices food while it drifts — so every expiring episode is settled *together*,
by shared prediction error:

```
error  = observed change − what every action in scope already predicts
target = this action's own current estimate + error
```

Two actions that always co-occur end up **splitting** the effect. That is the
honest answer: nothing can separate perfectly confounded causes, and inventing
a split would be worse than admitting the tie. The moment one of them happens
without the other, its estimate is corrected toward nothing and the real cause
absorbs the effect.

Every estimate is read before any of them moves, so settlement does not depend
on which episode's window happens to expire first.

**Extinction.** An episode settles every drive the action already has an
expectation about, not only the ones that visibly moved. *"I did that and the
thing I expected did not happen"* is the observation that corrects a mistaken
belief; discarding it because the change was too small to display meant a
coincidence, once learned, could never be unlearned.

Confidence grows with repetition and with the size of the effect relative to
how variable it is; a single observation is never confident, however dramatic.

## 4. Temporal credit assignment

An episode's **valence is the surprise**, not the raw change: the part of the
outcome that the actions in scope did not already predict. An outcome the squid
expects teaches it nothing, which is the whole content of prediction-error
learning and what keeps the reward channel honest. Scoring the raw change
instead made almost every episode "rewarding" — the drives always drift a
little — so reward fired constantly and swamped the correlational rule that
carries what the squid actually experienced.

That value is then broadcast to the eligibility traces laid down during the
episode (see [STDP](STDP.md)). Synapses that were participating in the run-up
to a good outcome are strengthened; those participating before a bad one are
weakened. One outcome carries a **fixed budget** of plasticity shared among the
synapses that earned it, so making eligibility broader does not make learning
stronger — if the whole network was active when something good happened, no
synapse in particular is responsible.

The change is recorded as `causal_reward` with the episode attached, so it can
name the action, the cue and the consequence.

## 5. What it produces

**Knowledge**, in the squid's own words:

> When it eats, hunger goes down by about 24 points (seen 9 times).
> Learned from: it eating while can see food was 100 … and then hunger fell 24
> Why: the same thing happened 9 times, and it does not happen when the squid is
> doing something else (background drift +0.4)

**Deficits.** A contingency the squid is confident about, with no synaptic
pathway from the cue to the outcome, is an *expression* deficit — it has
learned something it has no structure to act on — and that is one of the
reasons a new neuron gets grown. See [Neurogenesis](Neurogenesis.md).

## 6. Persistence

Contingencies, baselines and recent episodes are saved with the squid, so it
does not have to rediscover what eating does every time you load the game.

## Configuration

`CausalConfig` in `src/causal_learning.py`: `outcome_window`,
`min_valence_for_reward`, `reward_gain`, `max_reward_delta`, `cue_size`,
`min_confidence_to_teach`.
