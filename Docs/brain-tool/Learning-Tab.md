<img src="https://github.com/user-attachments/assets/0c76149e-0975-4942-a10c-ca686f1d6f76" width="700">

#### `Hebbian learning` is a principle grounded in the functioning of biological neural networks


<p> The <strong>Learning Tab</strong> is your window into understanding how your squid learns. It focuses on the Hebbian learning principle: "neurons that fire together, wire together." 

This tab shows every synaptic change as it happens, **read from the brain's own
provenance ledger** — the record the mechanism that made the change wrote at the
time. It is not a diff of a cached copy of the weights, which is what it used to
be and why it could never tell you *why* anything changed.

Each card carries:

* the two neurons and the new weight, with the direction of the change;
* an **LTP / LTD badge** and the spike-timing delta, when spike timing actually
  contributed to that change;
* one line saying **why**: which mechanism fired (co-activation, spike timing,
  an action's outcome, sleep replay, an innate reflex, a new neuron being wired
  in), together with the measured correlation and how many observations backed
  it.

For example: if hunger and satisfaction have been rising and falling together
across the window, their connection strengthens on the next commit, and the card
says so along with the correlation it measured.

Co-activation is accumulated **every tick** and committed on a cycle (20 s by
default), so a one-second event such as seeing food is not invisible to
learning. The countdown shows when the next commit is due.

Over time useful connections keep strengthening and strong pathways develop.
This is how the squid learns favourable behaviours — and the
[Knowledge tab](Knowledge-Tab.md) turns the same record into plain English.


----------------------------

#### Further Reading:
External links

* https://medium.com/@reutdayan1/hebbian-learning-biologically-plausible-alternative-to-backpropagation-6ee0a24deb00
* https://informatics.ed.ac.uk/sites/default/files/2024-03/Qiuye%20Zhang%20Lovelace%20Colloquium%20Poster.pdf
* https://en.wikipedia.org/wiki/Hebbian_theory
* https://www.youtube.com/watch?v=TvTQQO5yTa4


