# Neuron Laboratory

> **Double-click any neuron** in the network view to open it here.

The Laboratory answers one question at a time about one neuron, in the order
somebody actually asks them. Every answer is read from the brain's own record —
the provenance ledger the organism writes as it learns, the capability monitor
neurogenesis consults, and the live weights the network propagates through.
Nothing on the page is computed by the Laboratory, so it cannot tell you a
story the squid would not tell you itself.

<img src="https://github.com/user-attachments/assets/84506732-4613-423a-9268-ce4e474612b2" width="600">

---

## Deep Inspector — six questions

### What is this?

What kind of neuron it is and, crucially, **who writes it each tick**. Four
roles, and they are not interchangeable:

| Role | Written by |
|------|-----------|
| a **sense organ** | the world; no synapse may point at it, because the world would overwrite whatever the synapse put there |
| a **core drive** | the squid model; the network reaches it by modulation, a small nudge each tick |
| a **neuron the squid grew** | the network, every tick, from the synapses pointing at it |
| **an action the squid can notice itself performing** | what the squid is currently doing — the same arrangement as a sense organ |

Plus what it reads right now *in words* ("well above its resting level", not
just `73`), how many times it has been meaningfully active since it was born,
whether it has been deepened rather than duplicated, and whether it is part of
a problem the brain has not solved yet.

### Why does this neuron exist?

The birth record: the functional deficiency it was grown to remedy, in plain
English, the connections made at its birth, what the squid was living through
at the time — and, underneath, **the measurements behind that diagnosis**. A
diagnosis without its evidence is an assertion.

A core drive gets an honest answer too ("it exists because the squid has a
body"), and so does a sense organ.

### What does it stand for?

The interesting one, and the one that is *measured* rather than asserted.

The capability monitor already keeps, for every recurring situation and every
action the squid performs, how the whole network behaves while it holds. The
separation between this neuron's activation then and its activation the rest of
the time is Cohen's *d*, and a neuron with a large *d* for one situation and a
small one for everything else is, in the only sense the network has, a detector
for that situation:

> • while the squid is doing **wiggle**, it rises to 86 (otherwise 52) —
> **unmistakable**, d = 4.65, seen 94 times
> • when **can see food and anxiety-low**, it rises to 71 (otherwise 54) —
> **clear**, d = 0.94, seen 31 times

This is the same statistic the representation detector uses to decide whether
the brain can tell a situation apart at all, read from the same streaming
totals — so what the Laboratory says a neuron means and what neurogenesis
believes about it can never disagree.

A neuron that stands for nothing is told so, rather than being given a story.

### What do its connections mean?

Each synapse as a sentence rather than a row in a table:

> When **anxiety reduction** is above its resting level it pushes **anxiety**
> down, decisively (weight −0.90); below resting level it does the opposite.
> *Most of that value (−0.90) came from a neuron being grown for it.*

The second line is the ledger's running total: which mechanism is responsible
for the weight being the number it is. An externally driven neuron is told why
nothing drives it and why nothing may.

### What has it actually done?

Not what it *could* do — what it has done. For every synapse onto the squid's
physiology, the recorded influence: how many points it has actually pushed that
drive, over how many ticks in which it was doing anything at all. For an action
representation, what the squid has concluded that action causes, with its
confidence and how many times it has seen it.

At the end, and clearly labelled as a projection rather than a record, what the
neuron would contribute on the next tick if nothing else changed.

### What has changed here, and why

Every recorded change to every synapse this neuron touches, with the mechanism
and the evidence behind each one.

---

## Live Overview

What the brain currently cannot do, straight from the capability monitor, with
each deficit's severity and how close it is to earning a neuron — ready to grow
structure, still being watched, or already shrinking under ordinary learning.
Below it, what has actually been grown and what it was grown for, and where the
engine stood down instead of growing.

This card used to show progress bars filling toward novelty, stress and reward
thresholds. Those counters stopped deciding anything in v4.0 — growth is driven
by persistent capability deficits now — so the bars were filling up toward
numbers that no longer meant anything.

Alongside it, the neuron budget as a meter that turns amber and then red as the
brain fills toward `max_neurons`, whether pruning is on, and how long is left
on the growth cooldown.

---

## The window

The Laboratory opens at up to 1280×900, sized to the screen it is opening on,
and the cards flow into **two columns** so the extra width is used rather than
left as margin. "What is this?" and "Why does this neuron exist?" take the full
width, because everything else answers a detail of those two.

Cards are coloured by what they say, in the same palette the
[Memory tab](Memory-Tab.md) uses — a neuron that is part of an unsolved problem
is pink, the origin card is the blue the Memory tab gives neurogenesis, what a
neuron has done is amber, and the teaching card is gold. A page of uniform white
panels told you nothing about which one to read first.

---

## Edit Sandbox

Unlocking the sandbox gives full manual control of neuron values, so you can
hold a neuron at a value and watch what the rest of the network does about it.

<img src="https://github.com/user-attachments/assets/72f4e759-82b5-4e55-9f2b-23324a91bf82" width="450">
