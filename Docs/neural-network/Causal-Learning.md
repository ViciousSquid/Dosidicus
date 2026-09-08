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

The consequence is compared against the **baseline drift** of the same drive,
measured over identical windows while that action was not running:

> Hunger fell 24 while eating. Hunger drifts *up* 0.4 otherwise.
> Effect = −24.4.

Without that subtraction the squid would credit "exploring" with the hunger it
accumulates simply by existing. Confidence grows with repetition and with the
size of the effect relative to how variable it is; a single observation is
never confident, however dramatic.

## 4. Temporal credit assignment

When an episode closes with a meaningful valence, that value is broadcast to the
STDP eligibility traces laid down during it. Synapses that were causally active
in the seconds leading up to a good outcome are strengthened; those active
before a bad one are weakened. The change is recorded as `causal_reward` with
the episode attached, so it can name the action, the cue and the consequence.

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
