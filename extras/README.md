# The laboratory: tools for studying squid

Everything here opens in a web browser by double-clicking it. Nothing is
installed, nothing is uploaded, and no internet connection is needed: the
tools read the files you give them and the page forgets them when it closes.

A squid's save is a zip in the game's `saves` folder, named after the squid's
uuid. Since 3.5 it carries the squid's whole life in order, which is what
these tools show.

| You want to | Open |
|---|---|
| Follow one squid's life, or compare several | `Laboratory.html` |
| See everything inside one save, file by file | `SaveViewer.html` |
| Breed two squid and hatch the child in the game | `SquidBreeder.html` |
| Watch a brain being trained, tick by tick | `python headless/headless_trainer.py --serve` |
| Study one neuron in a living squid, and change it | the Neuron Laboratory, inside the game |

## Laboratory.html

Add one save or many with *Add saves*.

- **Specimens**: every squid loaded, in one table. Click one to examine it;
  tick two or more to compare them.
- **History**: the squid's life as a ribbon. Every event is a mark on it; a
  neuron it grew is a large node with what it was wired to hanging beneath.
  Slide the slider, or press *Play its life*, to step through every event: the
  brain below is redrawn as it was at that moment, and the card beside it says
  what happened and what it cost.
- **Strata**: the same life as layers, oldest at the bottom. Two ages (a life
  alone, and among other squid), their stages, and the periods each turning
  point began. Red marks are losses: a fight, a belief given up, a neuron, a
  life. Click any mark to go to that moment in History.
- **Why**: why each neuron it grew exists, and for every connection what has
  changed it and how often (born with it, inherited, learned from what an
  action led to, replayed in sleep, an encounter with another squid).
- **Family**: its parents and each synapse it inherited from them, what
  comes after it (a mate, an egg), and who lived in its tank before it.
- **Compare**: two or more squid side by side: their drives, the neurons
  each grew and when, and where their wiring differs most.
- **Session**: reads a `session.json` written by `tools/internet_session.py`:
  what happened between several squid over a multiplayer session.

The page shows what the game recorded and works nothing out for itself, so it
cannot disagree with the game about a squid's life. A save from before 3.5 has
no timeline; open that squid in the game and save it, or run:

```bash
python tools/add_timeline.py SAVE.zip
```

Connections are drawn at the strength they have now. When each one first
formed is recorded; how strong it was at that moment is not.

## SaveViewer.html

One save, in full: the squid, its life and the other squid it knows, what it
believes, its statistics, every neuron with why it grew, its memories, and the
raw files.

## SquidBreeder.html

Load two squid (saves or brain files) and breed them.

- **As the game does** (the default): a random half of each parent's inborn
  wiring laid over a newborn brain, with the game's mutation rate and size.
  Nothing either parent learned or grew is passed on.
- **Free blend**: an experiment the game does not perform. Marked as such.

After breeding as the game does, *Save hatchling* writes a save the game
opens: a newborn with the child's brain, its parents and every inherited
synapse on record, marked as bred here rather than by two squid meeting. Put
the file in the game's `saves` folder; it takes a free save slot and appears
in the slot chooser.

## The trainer

```bash
python headless/headless_trainer.py --serve
```

The headless trainer, working, in a browser. See `headless/README.md`.

## The Neuron Laboratory is something else

Inside the game, double-clicking a neuron opens the Neuron Laboratory: one
neuron of a living squid, as it is right now, what it means, what it would do
to the others, and controls to change it. These pages do none of that. They
read saves and change nothing.

## For maintainers

- `vendor/dosidicus_data.js` holds the facts about the game the pages need
  (a newborn's neurons and wiring, the mutation rate, which neurons are
  senses). It is written by `python tools/update_extras_data.py`; a test fails
  if it no longer matches the game.
- `vendor/lab.js` is shared by the Laboratory: reading a save and drawing a
  brain as it was at a moment.
- `vendor/jszip.min.js` and `vendor/chart.umd.min.js` are bundled with their
  licences so the pages work offline.
- `brain_2_keras.py` converts a brain file to a Keras model.
