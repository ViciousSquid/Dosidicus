# Decisions Tab

Behaviour is not chosen by a formula. The network has one **action neuron** per
thing the squid can do, those neurons **inhibit one another**, and whichever
survives that competition is what the squid does — see the
[Decision Engine](../engine/Decision-Engine.md).

So this tab shows the **contest**: what was in it, how hard each competitor was
being driven, what each had to beat, and what the winner suppressed on its way
past. And because the interesting moment is usually the one that has just gone,
it keeps them: a slider scrubs back through the last 240 decisions and replays
any of them.

---

## The header

The behaviour the squid settled on, the descriptive status it produced
("approaching food", "fleeing!"), and the squid's personality.

---

## The timeline

| Control | What it does |
| --- | --- |
| **Live** | follow the squid. New decisions replace the display as they happen. |
| **slider** | untick Live and drag. The whole page — contest, contributions, explanation — replays that moment. |
| **counter** | "13 decisions ago · 9/22", so you know where you are. |

New decisions arriving while you are looking at an old one do not move you off
it.

---

## What was competing

One row per action neuron. Each is drawn against **its own threshold**, marked
on the row, because the actions do not share a scale — a 50 is a strong wish to
flee and a weak wish to eat.

```
        Eat  ████████████████████▌      |          49
 Swim around ████████████████████       |          46 ↓7
        Play ░░░░░░░░░░░░░░░░░░░|░░░░░░░  0 ↓5
     Shelter ░░░░░░░░░░░░░░░░░░|░░░░░░░░  0 ↓5
        Flee ░░░░░░░░░░░░|░░░░░░░░░░░░░░  0 ↓5
```

* The **vertical mark** is the level that action must reach before the squid
  will do it.
* A **↓7** is how hard that action's rivals were pushing it down.
* The winner is picked out in dark green; anything that cleared its own bar is
  green; anything that did not is grey.

Whether an action cleared its bar is the thing you can see without reading
anything.

---

## Why it went that way

Plain English, assembled by the engine from its own snapshot of the tick:

> It chose to go and eat because that neuron reached 49, past the 38 it has to
> clear before the squid will act on it.
>
> What drove it: can see food (+42), hunger (+14).
>
> Nothing else was in contention; the closest was play, which reached 0 of the
> 38 it needed.
>
> Winning it also pushed the alternatives down: swim around (−7), flee (−5).

Every sentence is read off the snapshot — there is **no claim on this page the
network did not make**. A sleeping squid is described as asleep. A squid that
wants nothing says so, rather than having a reason invented for it.

The confidence figure underneath is how far ahead the winner was, once every
competitor was measured against its own threshold.

---

## The supporting cards

| Card | What it tells you |
| --- | --- |
| **What drove …** | each incoming synapse's contribution to the winner, in the same units as the bar above: the source's activation carried through the live weight |
| **What it pushed aside** | the lateral inhibition the winner applied to its rivals, measured |
| **What it could sense** | the sensor readings that produced this |
| **How it was feeling** | the core drives, as distance from the resting level of 50 — which is what the network actually works from |
| **Not available yet** | actions with no pathway driving them, so they were never in the contest at all. The squid has to learn these. |

Colours follow the [Memory tab's](Memory-Tab.md) language throughout: green is
good news, pink is bad, blue is neutral information, amber is worth noticing.
Pills know which stats are better *low*, so a calm squid's anxiety reads green.

---

## What this replaced

The tab used to show a single current winner, a confidence dial, and a bar
chart of "base urges" and "adjusted urges" that went past too fast to read. It
described a pipeline — sense, calculate base urges, apply personality and
memory multipliers, pick the highest — that the engine no longer runs, because
those multipliers are gone: personality is innate synaptic weight now, and
memory reaches behaviour through learning rather than through a table applied
after the fact.

It also only ever showed *now*. By the time you noticed something surprising,
the thing that caused it was three decisions ago and gone.
