"""
cup_game_ui.py - the cup-and-food game, played in the tank.

Three cups on the tank floor, a piece of food, and a squid. Bait a cup, shuffle
them, and see whether the squid picks the right one. It is a shell game and it
is meant to be fun.

It is also the experiment in `src/cup_experiment.py`, with a player in the loop
instead of a script, and it runs on the same objects: the same `CupExperiment`
keeps the trial log, the same `CupLayout` randomises the cups, and the same
scoring produces the numbers. `headless/cup_experiment_runner.py` is the version
you can seed and repeat; this is the version you can watch.

WHAT THE SQUID GETS
-------------------
Nothing new. The food is an ordinary food item in `TamagotchiLogic.food_items`,
so the VisionWorker sees it exactly as it sees any other food and `can_see_food`
means what it always meant. Hiding it under a cup takes it out of that list and
out of the scene: there is then nothing for the vision cone to find and nothing
for a movement drive to home in on, so the sensor falls to 0 through the
ordinary path. Revealing it puts the same item back, and the squid eats it with
`Squid.eat` - the call a hand-fed squid gets, with the consequences a hand-fed
squid gets.

The ghost marker that shows the player where the food is lives in the scene as a
decoration with no category, so `extract_scene_objects` skips it and the squid
cannot see it. It is drawn for the person watching and for nobody else.

The squid is never told it is playing. It swims where its own network sends it;
this module watches its ordinary position and calls the first cup it reaches its
selection.
"""

import os
import time

from PyQt5 import QtCore, QtGui, QtWidgets

from .cup_experiment import (
    CUP_IDENTITIES, CupExperiment, CupLayout, Phase, chance_rate,
    persistence_values, score_block,
)

CUP_WIDTH = 96
CUP_HEIGHT = 110
#: How far the squid must be from every cup before the choice window opens.
#: Without it the squid "chooses" the cup it is already standing on after
#: watching the food go under it, which scores well above chance while knowing
#: nothing. See the runner's TrialSettings for the full argument.
START_CLEARANCE = 330.0


# ---------------------------------------------------------------------------
# Scene items
# ---------------------------------------------------------------------------
class CupItem(QtWidgets.QGraphicsItem):
    """One cup. Drawn rather than loaded, so it needs no new art.

    Deliberately has NO `category` attribute: `extract_scene_objects` keys off
    that, so a cup is not among the objects the vision worker is given and
    cannot become something the squid sees. A cup is scenery for the player.
    """

    def __init__(self, identity: str):
        super().__init__()
        self.identity = identity
        self.lifted = True
        self.setZValue(20)

    def boundingRect(self):
        return QtCore.QRectF(0, -18, CUP_WIDTH, CUP_HEIGHT + 18)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        top = -18 if self.lifted else 0
        body = QtCore.QRectF(6, top + 14, CUP_WIDTH - 12, CUP_HEIGHT - 14)

        gradient = QtGui.QLinearGradient(body.topLeft(), body.topRight())
        gradient.setColorAt(0.0, QtGui.QColor(196, 108, 62))
        gradient.setColorAt(0.5, QtGui.QColor(238, 156, 96))
        gradient.setColorAt(1.0, QtGui.QColor(176, 92, 52))
        painter.setBrush(QtGui.QBrush(gradient))
        painter.setPen(QtGui.QPen(QtGui.QColor(110, 56, 30), 3))

        path = QtGui.QPainterPath()
        path.moveTo(body.left(), body.bottom())
        path.lineTo(body.left() + 10, body.top())
        path.lineTo(body.right() - 10, body.top())
        path.lineTo(body.right(), body.bottom())
        path.closeSubpath()
        painter.drawPath(path)

        painter.setBrush(QtGui.QBrush(QtGui.QColor(228, 142, 84)))
        painter.drawEllipse(QtCore.QRectF(body.left() + 6, body.top() - 7,
                                          body.width() - 12, 14))

        painter.setPen(QtGui.QPen(QtGui.QColor(255, 246, 230), 2))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(16)
        painter.setFont(font)
        painter.drawText(body, QtCore.Qt.AlignCenter, self.identity)

    def set_lifted(self, lifted: bool):
        if lifted != self.lifted:
            self.lifted = bool(lifted)
            self.update()


class GhostItem(QtWidgets.QGraphicsItem):
    """The experimenter's marker: where the food really is.

    EXPERIMENTER-ONLY. Like CupItem it carries no `category`, so it is invisible
    to `extract_scene_objects` and therefore to the squid. It exists so that the
    person watching can see the ground truth the squid does not have, which is
    the whole point of showing it: what you know and what the squid knows are
    two different things and the interface should never blur them.
    """

    def __init__(self):
        super().__init__()
        self.setZValue(15)
        self.visible_to_player = True

    def boundingRect(self):
        return QtCore.QRectF(0, 0, CUP_WIDTH, CUP_HEIGHT)

    def paint(self, painter, option, widget=None):
        if not self.visible_to_player:
            return
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor(90, 220, 130, 220), 3,
                                  QtCore.Qt.DashLine))
        painter.setBrush(QtGui.QBrush(QtGui.QColor(90, 220, 130, 60)))
        painter.drawEllipse(QtCore.QRectF(18, CUP_HEIGHT - 58, CUP_WIDTH - 36, 40))
        painter.setPen(QtGui.QPen(QtGui.QColor(30, 90, 50), 1))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(QtCore.QRectF(0, CUP_HEIGHT - 20, CUP_WIDTH, 18),
                         QtCore.Qt.AlignCenter, "you know")


# ---------------------------------------------------------------------------
# Running the game
# ---------------------------------------------------------------------------
class CupGameController(QtCore.QObject):
    """Drives one trial at a time against the live tank.

    Phase timings are in seconds of wall clock, because that is what the player
    is watching. The headless runner counts simulation ticks instead; both drive
    the same `CupExperiment` through the same phases in the same order.
    """

    trial_finished = QtCore.pyqtSignal(object)   # TrialRecord
    phase_changed = QtCore.pyqtSignal(str)

    #: Seconds per phase. BAIT and CHOICE are limits rather than durations:
    #: BAIT ends once the squid has actually seen the food, CHOICE when it
    #: reaches a cup.
    BAIT_LIMIT = 25.0
    BAIT_DWELL = 3.0
    SHUFFLE = 4.0
    HIDDEN = 5.0
    CLEARANCE_LIMIT = 25.0
    CHOICE_LIMIT = 45.0
    OUTCOME = 4.0

    def __init__(self, tamagotchi_logic, parent=None):
        super().__init__(parent)
        self.logic = tamagotchi_logic
        self.ui = tamagotchi_logic.user_interface
        self.scene = self.ui.scene

        self.layout = CupLayout(self._slot_positions(), CUP_IDENTITIES)
        self.experiment = CupExperiment(self._brain(), self.layout)
        self.cups = {name: CupItem(name) for name in CUP_IDENTITIES}
        self.ghost = GhostItem()
        for item in list(self.cups.values()) + [self.ghost]:
            self.scene.addItem(item)
        self._place_cups()

        self.block = "train"
        self.auto = False
        self.food_item = None
        self._seen_bait = False
        self._phase_started = 0.0
        self._deadline = 0.0

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(120)

    # -- the tank --------------------------------------------------------
    def _brain(self):
        window = getattr(self.logic, 'brain_window', None)
        return getattr(window, 'brain_widget', None)

    def _floor_y(self):
        return self.ui.window_height - 120 - CUP_HEIGHT

    def _slot_positions(self):
        margin = 150.0
        span = self.ui.window_width - 2 * margin - CUP_WIDTH
        y = self.ui.window_height - 120 - CUP_HEIGHT
        return [(margin + span * i / 2.0, y) for i in range(3)]

    def _place_cups(self):
        for name, slot in self.layout.slot_of_identity.items():
            x, y = self.layout.position_of_slot(slot)
            self.cups[name].setPos(x, y)

    def _squid_centre(self):
        squid = self.logic.squid
        return (squid.squid_x + squid.squid_width / 2.0,
                squid.squid_y + squid.squid_height / 2.0)

    def _brain_state(self):
        brain = self._brain()
        return dict(getattr(brain, 'state', {}) or {})

    # -- the food --------------------------------------------------------
    def _make_food(self, x, y):
        """An ordinary food item, made the way `spawn_food` makes one."""
        pixmap = QtGui.QPixmap(os.path.join("images", "cheese.png"))
        item = QtWidgets.QGraphicsPixmapItem(pixmap)
        item.is_sushi = False
        item.setPos(x, y)
        return item

    def _show_food_at(self, slot):
        """Put the food in the world, where the squid can see it."""
        x, y = self.layout.position_of_slot(slot)
        fx = x + (CUP_WIDTH - self.logic.food_width) / 2.0
        fy = self.ui.window_height - 120 - self.logic.food_height
        if self.food_item is None:
            self.food_item = self._make_food(fx, fy)
        else:
            self.food_item.setPos(fx, fy)
        if self.food_item not in self.logic.food_items:
            self.scene.addItem(self.food_item)
            self.logic.food_items.append(self.food_item)
        self._mark_dirty()

    def _hide_food(self):
        """Take the food out of the world's visible objects.

        This is what "under a cup" means to everything downstream: it is not
        among the objects handed to the vision worker, so `can_see_food` reads 0
        for the ordinary reason, and it is not in `food_items`, so the decision
        engine's `_nearest_food` cannot home in on it either. The item itself is
        kept, and the same one comes back at the reveal.
        """
        if self.food_item is not None:
            if self.food_item in self.logic.food_items:
                self.logic.food_items.remove(self.food_item)
            if self.food_item.scene() is self.scene:
                self.scene.removeItem(self.food_item)
        self._mark_dirty()

    def _discard_food(self):
        self._hide_food()
        self.food_item = None

    def _mark_dirty(self):
        squid = getattr(self.logic, 'squid', None)
        if squid is not None and hasattr(squid, 'mark_scene_objects_dirty'):
            squid.mark_scene_objects_dirty()

    # -- phases ----------------------------------------------------------
    def start_trial(self, block=None):
        if self.experiment.current is not None:
            return
        self.block = block or self.block
        record = self.experiment.begin_trial(self.block)
        self._seen_bait = False
        for cup in self.cups.values():
            cup.set_lifted(True)
        self._show_food_at(record.truth_baited_slot)
        self._update_ghost(record.truth_baited_slot)
        self._enter(Phase.BAIT, self.BAIT_LIMIT)

    def _enter(self, phase, seconds):
        self.experiment.enter_phase(phase)
        self._phase_started = time.time()
        self._deadline = time.time() + float(seconds)
        self.phase_changed.emit(phase.value)

    def _elapsed(self):
        return time.time() - self._phase_started

    def _expired(self):
        return time.time() >= self._deadline

    def _update_ghost(self, slot):
        if slot is None or slot < 0:
            self.ghost.setVisible(False)
            return
        x, y = self.layout.position_of_slot(slot)
        self.ghost.setPos(x, y)
        self.ghost.setVisible(True)

    def _clear_of_cups(self):
        return self.layout.slot_nearest(*self._squid_centre(),
                                        radius=START_CLEARANCE) < 0

    def _tick(self):
        record = self.experiment.current
        if record is None:
            if self.auto:
                self.start_trial()
            return

        phase = self.experiment.phase
        state = self._brain_state()
        self.experiment.observe(self._squid_centre(),
                                getattr(self.logic.squid, 'status', ''), state)

        if phase is Phase.BAIT:
            if float(state.get('can_see_food', 0.0)) >= 100.0:
                self._seen_bait = True
            if (self._seen_bait and self._elapsed() >= self.BAIT_DWELL) \
                    or self._expired():
                self.shuffle()

        elif phase is Phase.SHUFFLE:
            if self._expired():
                self._hide()

        elif phase is Phase.HIDDEN:
            if self._expired() and (self._clear_of_cups()
                                    or self._elapsed() >= self.CLEARANCE_LIMIT):
                record.started_clear = self._clear_of_cups()
                self._enter(Phase.CHOICE, self.CHOICE_LIMIT)

        elif phase is Phase.CHOICE:
            # `observe` above already commits a choice when the squid arrives.
            if self.experiment.phase is Phase.REVEAL:
                self._reveal()
            elif self._expired():
                self.experiment.give_up()
                self._reveal()

        elif phase is Phase.OUTCOME:
            if self._expired():
                self._settle()

    def shuffle(self):
        """Step 3. The bait travels with its own cup, still in view."""
        record = self.experiment.current
        if record is None or self.experiment.phase is not Phase.BAIT:
            return
        self.experiment.shuffle()
        self._place_cups()
        self._show_food_at(record.truth_baited_slot)
        self._update_ghost(record.truth_baited_slot)
        self._enter(Phase.SHUFFLE, self.SHUFFLE)

    def _hide(self):
        """Step 4. The cups come down and the food goes out of the world."""
        record = self.experiment.current
        for cup in self.cups.values():
            cup.set_lifted(False)
        self._hide_food()
        self.experiment.hide()
        self._update_ghost(record.truth_baited_slot)
        self._enter(Phase.HIDDEN, self.HIDDEN)

    def _reveal(self):
        """Steps 6-7. Lift the chosen cup; if the food is there, it eats."""
        record = self.experiment.current
        if record.chosen_slot >= 0:
            self.cups[self.layout.identity_at(record.chosen_slot)].set_lifted(True)
        if record.correct:
            # Back into the world at the cup it picked. From here the ordinary
            # pipeline takes over: `move_cheese` notices the collision and calls
            # `Squid.eat`, with the stat changes, the reflex and the memory that
            # every other meal gets. Nothing about the reward is special here.
            self._show_food_at(record.chosen_slot)
        self._enter(Phase.OUTCOME, self.OUTCOME)

    def _settle(self):
        record = self.experiment.current
        ate = record.correct and (self.food_item not in self.logic.food_items)
        self._discard_food()
        for cup in self.cups.values():
            cup.set_lifted(True)
        self.ghost.setVisible(False)
        finished = self.experiment.resolve(ate=bool(ate))
        self.trial_finished.emit(finished)

    # -- controls --------------------------------------------------------
    def set_frozen(self, frozen: bool):
        self.experiment.set_learning_frozen(bool(frozen))

    def set_ghost_visible(self, visible: bool):
        self.ghost.visible_to_player = bool(visible)
        self.ghost.update()

    def shutdown(self):
        self.timer.stop()
        self._discard_food()
        for item in list(self.cups.values()) + [self.ghost]:
            if item.scene() is self.scene:
                self.scene.removeItem(item)
        self.experiment.set_learning_frozen(False)


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------
class CupGameWindow(QtWidgets.QDialog):
    """Controls, trial history, and everything the run produced.

    The layout has one organising idea: WHAT YOU KNOW and WHAT THE SQUID KNOWS
    are separate panels and never mix. The history table marks the ground-truth
    columns; the perception panel shows only readings off the squid's own
    sensors and neurons.
    """

    def __init__(self, tamagotchi_logic, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🥤 Cup & Food — a shell game, and a measurement")
        self.resize(1040, 720)
        self.setWindowFlag(QtCore.Qt.WindowMinMaxButtonsHint)

        self.controller = CupGameController(tamagotchi_logic, self)
        self.controller.trial_finished.connect(self._on_trial_finished)
        self.controller.phase_changed.connect(self._on_phase_changed)

        self._build()

        self.refresh = QtCore.QTimer(self)
        self.refresh.timeout.connect(self._refresh_live)
        self.refresh.start(400)

    # -- construction ----------------------------------------------------
    def _build(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.addLayout(self._build_toolbar())

        self.phase_label = QtWidgets.QLabel("Press “Run a trial” to begin.")
        self.phase_label.setStyleSheet(
            "font-size: 15px; font-weight: 600; padding: 6px;"
            "background: #eef3f8; border-radius: 6px;")
        outer.addWidget(self.phase_label)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter.addWidget(self._build_history())
        splitter.addWidget(self._build_tabs())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        outer.addWidget(splitter, 1)

        self.score_label = QtWidgets.QLabel()
        self.score_label.setWordWrap(True)
        self.score_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        outer.addWidget(self.score_label)
        self._refresh_scores()

    def _build_toolbar(self):
        bar = QtWidgets.QHBoxLayout()

        self.run_button = QtWidgets.QPushButton("Run a trial")
        self.run_button.clicked.connect(lambda: self.controller.start_trial())
        bar.addWidget(self.run_button)

        self.auto_check = QtWidgets.QCheckBox("Keep going")
        self.auto_check.toggled.connect(self._set_auto)
        bar.addWidget(self.auto_check)

        bar.addSpacing(16)
        bar.addWidget(QtWidgets.QLabel("Block:"))
        self.block_box = QtWidgets.QComboBox()
        self.block_box.addItems(["train", "eval"])
        self.block_box.currentTextChanged.connect(self._set_block)
        self.block_box.setToolTip(
            "train: the squid learns from the trials.\n"
            "eval: plasticity is frozen, so what you measure is what it "
            "already knew rather than what it is picking up while you watch.")
        bar.addWidget(self.block_box)

        self.frozen_label = QtWidgets.QLabel()
        bar.addWidget(self.frozen_label)

        bar.addStretch()
        self.ghost_check = QtWidgets.QCheckBox("Show me where the food is")
        self.ghost_check.setChecked(True)
        self.ghost_check.setToolTip(
            "The ghost marker is yours, not the squid's. It is drawn in the "
            "tank but it carries no category, so the vision worker is never "
            "given it and nothing the squid perceives contains it.")
        self.ghost_check.toggled.connect(self.controller.set_ghost_visible)
        bar.addWidget(self.ghost_check)
        return bar

    def _build_history(self):
        self.history = QtWidgets.QTableWidget(0, 8)
        self.history.setHorizontalHeaderLabels([
            "#", "Block", "YOU KNOW: cup", "YOU KNOW: slot",
            "Squid went to", "Result", "Outcome", "Started clear",
        ])
        self.history.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch)
        self.history.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.history.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.history.itemSelectionChanged.connect(self._show_selected_trial)
        return self.history

    def _build_tabs(self):
        self.tabs = QtWidgets.QTabWidget()
        self.perception = self._text_tab(
            "What the squid perceived",
            "Readings off its own sensors and neurons. Nothing here knows "
            "which cup was baited.")
        self.weights_view = self._text_tab(
            "Weight changes",
            "Every synapse that moved during the selected trial, from the "
            "brain's own weight table.")
        self.plasticity_view = self._text_tab(
            "Plasticity events",
            "The provenance ledger's account of why each of those changed.")
        self.episodes_view = self._text_tab(
            "Experience records",
            "Episodes the causal ledger closed during the trial: what the "
            "squid was doing, and what happened next.")
        self.knowledge_view = self._text_tab(
            "What it knows",
            "Generated by the existing knowledge system, not by this "
            "experiment.")
        return self.tabs

    def _text_tab(self, title, blurb):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        caption = QtWidgets.QLabel(blurb)
        caption.setWordWrap(True)
        caption.setStyleSheet("color: #55606a; font-size: 11px;")
        layout.addWidget(caption)
        view = QtWidgets.QTextEdit()
        view.setReadOnly(True)
        view.setStyleSheet("font-family: monospace; font-size: 12px;")
        layout.addWidget(view)
        self.tabs.addTab(page, title)
        return view

    # -- reacting --------------------------------------------------------
    def _set_auto(self, on):
        self.controller.auto = bool(on)

    def _set_block(self, name):
        self.controller.block = name
        # An evaluation block is frozen. That is what makes it an evaluation:
        # nothing measured in it can be something the squid picked up while
        # being measured.
        self.controller.set_frozen(name == "eval")
        self._refresh_live()

    def _on_phase_changed(self, phase):
        captions = {
            'bait': "Baiting a cup — the squid can see the food.",
            'shuffle': "Shuffling — the food travels with its cup, still in view.",
            'hidden': "Hidden — the cups are down and the squid must get clear "
                      "of them before it may choose.",
            'choice': "Choosing — whichever cup it reaches first is its answer.",
            'reveal': "Lifting the cup…",
            'outcome': "…and the consequences, whatever they are.",
        }
        self.phase_label.setText(captions.get(phase, phase))

    def _on_trial_finished(self, record):
        row = self.history.rowCount()
        self.history.insertRow(row)
        went = ("—" if record.chosen_slot < 0
                else f"slot {record.chosen_slot} (cup {record.chosen_identity})")
        result = ("no choice" if not record.committed
                  else ("correct ✓" if record.correct else "wrong ✗"))
        outcome = ", ".join(f"{k} {v:+.1f}"
                            for k, v in sorted(record.outcome_deltas.items())) or "—"
        values = [str(record.index), record.block,
                  record.truth_baited_identity, str(record.truth_baited_slot),
                  went, result, outcome,
                  "yes" if record.started_clear else "no"]
        for column, value in enumerate(values):
            item = QtWidgets.QTableWidgetItem(value)
            if column in (2, 3):
                item.setBackground(QtGui.QColor(232, 244, 234))
            if column == 5 and record.committed:
                item.setForeground(QtGui.QColor(
                    30, 130, 60) if record.correct else QtGui.QColor(170, 50, 50))
            self.history.setItem(row, column, item)
        self.history.scrollToBottom()
        self.history.selectRow(row)
        self._refresh_scores()

    def _show_selected_trial(self):
        rows = self.history.selectionModel().selectedRows()
        if not rows:
            return
        index = rows[0].row()
        trials = self.controller.experiment.trials
        if index >= len(trials):
            return
        record = trials[index]

        lines = [f"trial {record.index}  ({record.block})", ""]
        for phase in (Phase.BAIT, Phase.SHUFFLE, Phase.HIDDEN, Phase.CHOICE):
            sample = record.perceived(phase)
            if sample is None:
                continue
            lines.append(
                f"{phase.value:<9} can_see_food {sample.can_see_food:6.1f}   "
                f"act_eat {sample.act_eat:6.1f}   hunger {sample.hunger:5.1f}   "
                f"status {sample.status}")
        visible = record.act_eat_while_visible()
        hidden = record.act_eat_while_hidden()
        lines += ["", "peak act_eat with the food in sight: "
                  + ("n/a" if visible is None else f"{visible:.1f}"),
                  "peak act_eat with the food hidden:   "
                  + ("n/a" if hidden is None else f"{hidden:.1f}")]
        lines += ["", "(the baited cup appears nowhere above — it never "
                  "reached the squid)"]
        self.perception.setPlainText("\n".join(lines))

        self.weights_view.setPlainText(
            "\n".join(f"{edge:<40} {delta:+.4f}"
                      for edge, delta in sorted(record.weight_deltas.items()))
            or "no synapse moved during this trial")
        self.plasticity_view.setPlainText(
            "\n".join(record.plasticity_events) or "no plasticity events")
        self.episodes_view.setPlainText(
            "\n".join(record.episodes) or "no episodes closed during this trial")
        self.knowledge_view.setPlainText(
            "\n".join(record.knowledge) or "nothing yet")

    def _refresh_live(self):
        frozen = self.controller.experiment.learning_frozen
        self.frozen_label.setText("🧊 plasticity frozen" if frozen
                                  else "🌱 learning")
        self.frozen_label.setStyleSheet(
            "color: #2a6fb0; font-weight: 600;" if frozen
            else "color: #2e8b57; font-weight: 600;")

    def _refresh_scores(self):
        experiment = self.controller.experiment
        if not experiment.trials:
            self.score_label.setText(
                f"No trials yet. Chance is {chance_rate():.1%} — a squid that "
                "learned nothing should land there.")
            return
        lines = []
        for name in dict.fromkeys(r.block for r in experiment.trials):
            block = experiment.block(name)
            lines.append(score_block(block, name).describe())
            drive = persistence_values(block)
            if drive:
                lines.append(
                    f"    food-seeking drive surviving occlusion: "
                    f"{sum(drive) / len(drive):.0%}")
        self.score_label.setText("\n".join(lines))

    def closeEvent(self, event):
        self.refresh.stop()
        self.controller.shutdown()
        super().closeEvent(event)
