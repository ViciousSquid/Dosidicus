# Knowledge tab

> *"Why did this weight change from 0.31 to 0.47?"*
> *"Why does this neuron exist?"*
> *"What does the squid know about food?"*

The Knowledge tab answers those, in plain English, from the brain's own record.

It is a **view**. It computes nothing about the network and keeps no copy of
it: every line comes from the provenance ledger the organism writes as it
learns (`src/neural_provenance.py`), the capability monitor neurogenesis
consults (`src/capability.py`), and the live weights the network propagates
through. If the tab says a synapse moved because two things kept happening
together, that is because the mechanism that moved it said so at the time — not
because the UI diffed a snapshot afterwards and guessed.

---

## What it knows

A searchable list of everything the squid has learned. Type a topic (`food`,
`anxiety`, `plant`) to filter. Each card carries the full provenance:

| Field | Meaning |
|-------|---------|
| **Statement** | what it learned, e.g. *"When can see food is high, satisfaction strongly goes up."* |
| **What experience caused it** | the episode or the span of observations behind it |
| **Which action was involved** | the squid's own behaviour, where one is implicated |
| **What consequence followed** | the measured change in its drives |
| **Why the connection changed** | the mechanism and its evidence — correlation, sample count, spike timing, replay |
| **Confidence** | magnitude × consistency × support, as a percentage and a bar |
| **Effect on behaviour** | how much this synapse has actually pushed the squid around, and what it chose next |

Three kinds of item appear:

* **association** — a synapse, and what it means
* **cause and effect** — a contingency between one of the squid's actions and a
  consequence, measured against the background drift
* **new structure** — a neuron that did not exist when the squid was born

**Export…** writes the whole lot to a text file, including what the squid
cannot do yet.

### Narrated vs accounted

Some mechanisms are high-frequency and small: an outcome touches every synapse
that was participating, many times a minute, by thousandths. Those changes are
real and their **totals are exact** — "why is this weight 0.47" still adds up —
but they are not listed one by one, because four hundred lines of "+0.002" bury
the handful of changes that actually tell the squid's story. Anything
structural (a neuron wired in, a synapse pruned, a hand edit, a change that
flips a synapse's sign) is always listed, whatever its size.

## Why this weight?

Pick any synapse. You get its whole recorded life: the running total of what
each mechanism contributed, the individual changes with their evidence, the
experience behind each one, and how much the synapse has pushed its target
around since.

The table below gives the same history row by row.

## Why does this neuron exist?

Pick any neuron.

* a **core drive** — it exists because the squid has a body;
* a **sense organ** — the world writes it, the network reads it;
* a **grown neuron** — the functional deficiency it was born to remedy, the
  evidence for that deficiency, the connections made at its birth, what the
  squid was living through at the time, and how it is wired now;
* a **hand-wired neuron** — added in the Brain Designer or loaded from a custom
  brain.

The same explanation appears in the **Neuron Laboratory** when you double-click
a neuron in the network view.

## What it can't do yet

The live capability diagnosis: every deficit the monitor currently holds, its
severity, what a new neuron would do about it, and whether it has persisted
long enough to earn one. Below that: growth that was considered and stood down
(and why), and the structure grown so far.

This is the same list neurogenesis acts on. Watching it is watching the squid
decide to grow.
