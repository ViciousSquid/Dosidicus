# Neural rock throwing

The review of `e872044` is developed on **UNSTABLE only**. CANARY and main are
unchanged. The unrelated open tasks in the evolution handoff remain separate.

`src/throwing.py` is shared by desktop and Android, without Qt or Kivy imports.
The existing action-neuron competition decides whether to throw or drop, with
no random throw probability or directional coin flip. Velocity follows the
stronger activation of `act_play` and the squid's grown `aggression` neuron.
A custom motor binding instead uses the neuron that actually fired. Aim follows
the nearest squid in the current view cone, compensating for gravity and the
flight's drag (without the drag a full-power throw at 600 px falls 80 px
short), or the squid's gaze when no squid is visible. Aim, activation, source neuron, speed
and angle are recorded for the thrower. Personality does not choose a throw.

A projectile has its own lifetime, independent of carrying. Repeated throw
requests cannot relaunch it, carry cleanup cannot stop its flight, and a drop
clears the parent and possession flags. Flying rocks cannot be picked up;
settled rocks respect their pickup cooldown. Headstones cannot be picked up.
Only one physics connection is installed on each desktop timer.

Collision checks sweep the entire movement segment, choose the first body
struck, account for desktop item size, and run before floor cleanup. Movement
is clipped at the first physical tank boundary, so a landing cannot falsely
hit something beyond that point. One rock can strike once. Android uses the
same flight and swept-contact functions, subdividing slow render frames
without changing the one-second cognitive cadence.

## Remote bodies, local brains

Encounter protocol **4** adds identified rock impacts and reports of a visitor's
completed throw. Older peers must update together. Each throw has a unique ID;
repeat hooks and repeat or re-enveloped UDP consequences do not repeat damage,
startle, statistics or encounter counts. Distinct physical throws still count.

The struck squid receives only the impact, speed and the identity involved.
Neither aim nor the thrower's neural reasons are sent to the recipient. A hit
costs two health points and triggers the ordinary startle/sensory path; the
recipient's own network processes that experience. No event labels the rock as
an attack or infers whether it was deliberate. Hits given carry no judgement
about their value. Taken/given counts are remembered against the actual peer.
Separate rock encounters retain separate memory keys, so a later impact cannot
be lost by reinforcing an older, unchanged memory. Counts survive save/load.
A projectile retains its source identity after departure; the resident core
applies its impact once even if multiplayer has since been disabled. Lethal
mobile damage remains fatal after save/load.

A desktop visitor's next play intent can throw the rock it took, using the
activation and aggression supplied by its own home brain. The host supplies
physical geometry and executes the intent; it constructs no visitor brain.
The resident can feel that visitor's rock through the same hit hook.

Live Android Nearby visits now use the shared remote-mind protocol through
`engine/peer_visit.py`. Identity, perception, intents and consequences cross
the connection. The visitor keeps its brain, learning and encounter memory on
its own device; link loss restores its home body without undoing consequences.
Live ink is an edge-triggered parallel motor event, and fight animations own
the visitor body until resolution. Fight results are applied and remembered
at home with unique, replay-safe IDs. Local preview visitors remain a separate
offline demonstration. Live connections
no longer implicitly send a copied brain; the existing ZIP export/import flow
remains available for deliberately sharing a copy. Mobile health is persisted
in both its state and the interoperable save archive. APK staging includes the
shared throwing and Qt-free remote-mind modules.

## Validation

With PyQt5, NumPy and pytest installed, run the complete suites:

```sh
QT_QPA_PLATFORM=offscreen python -m pytest tests android/tests -q -p no:cacheprovider
```

The reviewed tree passed **720 tests**: 665 desktop and 55 Android, plus 577
subtests. Three existing `Thread.setName` deprecation warnings remain.
Regressions include neural competition and exact-threshold ties, custom motor
provenance, view filtering, swept/tangent/stationary collisions, floor clipping,
carry/drop state, replayed hits and throw reports, and persistence across
multiple rock encounters. APK staging is tested in a subprocess that forbids
Qt and Kivy imports, including the mobile peer adapter.

For two real desktop processes over the LAN transport, with disposable saves:

```sh
QT_QPA_PLATFORM=offscreen python tools/test_rock_multiplayer.py /tmp/rock-pair
```

Use a new output directory. The harness explicitly consents for the disposable
squids and controls their neural activations to exercise both throw directions.
It checks discovery and admission, real projectile impacts, duplicate UDP
consequences, the recipient's neural startle sensor, and a save archive retaining
98 health and exactly one hit taken/given in long-term encounter memory. Logs
and results are retained in the output directory; both processes are stopped.
This is a controlled regression, not a claim about spontaneous aggression.

Two mobile simulations additionally exercise the live remote-mind round trip,
including a visitor throwing back and link loss, without a host-side copied
brain. Google Nearby radio/permissions and on-device rendering require Android
hardware and have not been tested here. No signed APK was built or published.
