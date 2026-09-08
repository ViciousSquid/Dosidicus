# 2.4.5.1 | rev3_dec25
#  --------------------------------------------------------------
#  NEURON LABORATORY
#  --------------------------------------------------------------

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5 import QtCore
from PyQt5.QtGui import (
    QFont, QPixmap, QColor, QPainter, QBrush, QPen, QDoubleValidator
)
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
    QPushButton, QScrollArea, QSlider, QSpinBox, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QToolButton
)

import json, math, time, random, datetime as dt
from .localisation import loc  # Import localisation

# ------------------------------------------------------------------
#  Helper: coloured connection badge
# ------------------------------------------------------------------
def badge(text, color="#333", bg="#eee"):
    return f"""<span style="color:{color};background:{bg};
               padding:2px 6px;border-radius:4px;font-size:10pt;
               font-weight:600;">{text}</span>"""


# ------------------------------------------------------------------
#  Main Laboratory Dialog
# ------------------------------------------------------------------
class NeuronLaboratory(QDialog):
    def __init__(self, brain_widget, parent=None):
        super().__init__(parent)
        self.bw = brain_widget
        self.setWindowTitle(loc("lab_title", "🧠  Neuron Laboratory"))
        self.resize(900, 750)
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint)

        # ---- top toolbar ----
        bar = QHBoxLayout()
        self.live_check = QCheckBox(loc("lab_live_refresh", "Live refresh"))
        self.live_check.setChecked(True)
        self.live_check.toggled.connect(self._toggle_live)
        bar.addWidget(self.live_check)

        bar.addStretch()
        self.lock_check = QCheckBox(loc("lab_unlock_editing", "🔓  Unlock editing"))
        self.lock_check.toggled.connect(self._unlock_editing)
        bar.addWidget(self.lock_check)

        # ---- main notebook ----
        self.tabs = QTabWidget()
        
        # --- Apply Card-Based Styling ---
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #e1e5eb;
                border-radius: 12px;
                background-color: #f8f9fa;
            }
            QTabBar::tab {
                background: #f8f9fa;
                border: 1px solid #e1e5eb;
                padding: 10px 20px;
                margin-right: 5px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 14px;
                color: #2c3e50;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-bottom: none;
                font-weight: 600;
            }
            /* Style all QGroupBoxes to appear as modern cards */
            QGroupBox { 
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding-top: 20px; 
                margin-top: 10px; 
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                left: 10px;
                color: #1976d2; /* Use a primary color for card titles */
                font-weight: bold;
                font-size: 12pt;
            }
        """)
        # ------------------------------------------------------------------
        
        # Initialize forced values and timer for absolute override
        self.forced_neurons = {}  # Dictionary to store forced values: name -> value
        self._force_timer = QTimer(self)
        self._force_timer.timeout.connect(self._apply_forced_values)
        self._force_timer.start(100)  # Check 10 times per second for smooth override
        
        self._build_overview_tab()
        self._build_inspector_tab()
        self._build_edit_tab()

        # ---- footer ----
        self.status_lbl = QLabel(loc("lab_status_ready", "Ready"))
        self.status_lbl.setStyleSheet("color:#888;font-size:9pt;")

        lay = QVBoxLayout(self)
        lay.addLayout(bar)
        lay.addWidget(self.tabs)
        lay.addWidget(self.status_lbl)

        # ---- refresh timer ----
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(1000)  # 1 Hz

        self._refresh()  # first paint

        # ---- per-neuron manual lock table ----
        self.locked_neurons = {}   # name -> {locked: bool, slider, spin, button}

    # ================================================================
    #  Construction helpers
    # ================================================================
    def _build_overview_tab(self):
        self.ov_scroll = QScrollArea()
        self.ov_widget = QWidget()
        self.ov_grid = QGridLayout(self.ov_widget)
        self.ov_scroll.setWidget(self.ov_widget)
        self.ov_scroll.setWidgetResizable(True)
        self.tabs.addTab(self.ov_scroll, loc("lab_tab_overview", "📊  Live Overview"))

    def _build_inspector_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.pick_neuron = QComboBox()
        self.pick_neuron.currentTextChanged.connect(self._inspect_neuron)
        lay.addWidget(QLabel(loc("lab_pick_neuron", "Pick a neuron to inspect:")))
        self.pick_neuron.setStyleSheet("""
            QComboBox { font-size: 18px; min-height: 36px; padding: 4px; }
        """)
        lay.addWidget(self.pick_neuron)
        self.inspector_scroll = QScrollArea()
        self.inspector_cards = QWidget()
        self.inspector_lay = QVBoxLayout(self.inspector_cards)
        self.inspector_scroll.setWidget(self.inspector_cards)
        self.inspector_scroll.setWidgetResizable(True)
        lay.addWidget(self.inspector_scroll, 1)
        self.tabs.addTab(w, loc("lab_tab_inspector", "🔍  Deep Inspector"))

    def _build_edit_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        warn = QLabel(loc("lab_edit_locked_msg", "⚠️  Editing is locked – check 'Unlock editing' in the toolbar."))
        warn.setStyleSheet("color:#d9534f;font-weight:bold;")
        lay.addWidget(warn)
        self.edit_warn = warn
        self.edit_scroll = QScrollArea()
        self.edit_cards = QWidget()
        self.edit_lay = QVBoxLayout(self.edit_cards)
        self.edit_scroll.setWidget(self.edit_cards)
        self.edit_scroll.setWidgetResizable(True)
        lay.addWidget(self.edit_scroll, 1)
        self.tabs.addTab(w, loc("lab_tab_edit", "🔧  Edit Sandbox"))

    # ================================================================
    #  Live refresh
    # ================================================================
    def _refresh(self):
        if not self.live_check.isChecked():
            return
        current = self.pick_neuron.currentText()
        self.pick_neuron.clear()
        
        # Translate neuron names if needed, or use raw keys? 
        # Usually keys are used internally, but displayed names might be localized.
        # For this tool, we usually show keys, but let's stick to keys for consistency with other tools.
        self.pick_neuron.addItems(sorted(self.bw.neuron_positions.keys()))
        
        idx = self.pick_neuron.findText(current)
        if idx >= 0:
            self.pick_neuron.setCurrentIndex(idx)
        self._paint_overview()
        self._inspect_neuron(self.pick_neuron.currentText())
        self._paint_edit()

    def select_neuron_by_name(self, neuron_name: str):
        """
        Selects the specified neuron in the pick_neuron dropdown
        and refreshes the Inspector tab content.
        """
        if not hasattr(self, 'pick_neuron'):
            return
                
        # 1. Select the neuron in the dropdown
        idx = self.pick_neuron.findText(neuron_name)
        if idx >= 0:
            self.pick_neuron.blockSignals(True)
            self.pick_neuron.setCurrentIndex(idx)
            self.pick_neuron.blockSignals(False)
                
            # 2. Force the inspection of the newly selected neuron
            self._inspect_neuron(neuron_name)
                
            # 3. Switch to the "Deep Inspector" tab
            self.tabs.setCurrentIndex(1)
                
            # 4. Update the view to reflect the change
            self.update()

    # ================================================================
    #  Overview / Inspector / Edit
    # ================================================================
    def _paint_overview(self):
        while self.ov_grid.count():
            item = self.ov_grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        nd = getattr(self.bw, 'neurogenesis_data', {})
        cfg = getattr(self.bw, 'neurogenesis_config', {})
        monitor = getattr(self.bw, 'capability', None)
        engine = getattr(self.bw, 'enhanced_neurogenesis', None)

        # Card 1: what the brain currently cannot do, and how close each of
        # those problems is to earning a neuron.
        #
        # This card used to show progress bars toward novelty / stress / reward
        # thresholds. Those counters stopped deciding anything in v4.0 - growth
        # is driven by persistent capability deficits now - so the bars were
        # filling up toward numbers that no longer meant anything. What follows
        # is the diagnosis neurogenesis actually consults.
        card1 = QGroupBox(loc("lab_ov_deficits", "What the brain cannot do yet"))
        g1 = QGridLayout(card1)
        deficits = sorted(getattr(monitor, 'active', {}).values(),
                          key=lambda d: -d.severity) if monitor else []
        actionable = {d.key for d in monitor.actionable()} if monitor else set()
        if not deficits:
            g1.addWidget(QLabel(loc(
                "lab_ov_no_deficits",
                "Nothing. The network can represent, regulate and express "
                "everything it has met.")), 0, 0, 1, 2)
        for row, d in enumerate(deficits[:5]):
            if d.key in actionable:
                state = loc("lab_ov_ready", "ready to grow structure")
            elif not d.unresolved:
                state = loc("lab_ov_shrinking",
                            "ordinary learning is already shrinking it")
            else:
                state = loc("lab_ov_watching",
                            "watching - {obs} observation(s), {age:.0f}s",
                            obs=d.observations, age=d.age)
            label = QLabel(f"<b>[{d.kind.replace('_', ' ')}]</b> {d.summary}"
                           f"<br><i>severity {d.severity:.2f} &mdash; {state}</i>")
            label.setWordWrap(True)
            g1.addWidget(label, row, 0)
            g1.addWidget(self._progress_bar(min(100, d.severity * 100)), row, 1)
        self.ov_grid.addWidget(card1, 0, 0)

        # Card 2: what has been grown, and what it was grown for.
        card2 = QGroupBox(loc("lab_ov_newest", "Newest neurogenesis neurons"))
        v2 = QVBoxLayout(card2)
        grown = list(getattr(engine, 'growth_log', []) or [])[-5:]
        for row in reversed(grown):
            age = int(max(0.0, time.time() - row.get('at', 0)))
            lbl = QLabel(f"<b>{row.get('neuron', '?')}</b> &mdash; "
                         + loc("lab_ago", "{seconds}s ago", seconds=age)
                         + f"<br><i>{row.get('because', '')}</i>")
            lbl.setWordWrap(True)
            v2.addWidget(lbl)
        stood_down = list(getattr(engine, 'stood_down', []) or [])[-2:]
        for _at, key, why in reversed(stood_down):
            lbl = QLabel("<span style='color:#666;'>"
                         + loc("lab_ov_stood_down",
                               "Did not grow for {deficit}: {why}",
                               deficit=key, why=why)
                         + "</span>")
            lbl.setWordWrap(True)
            v2.addWidget(lbl)
        if not grown and not stood_down:
            v2.addWidget(QLabel(loc("lab_none_yet", "None yet")))
        self.ov_grid.addWidget(card2, 0, 1)
        
        # Card 3: Limits
        card3 = QGroupBox(loc("lab_ov_limits", "Limits & pruning"))
        v3 = QVBoxLayout(card3)
        current = len(self.bw.neuron_positions) - len(self.bw.excluded_neurons)
        max_n = cfg.get('max_neurons', 32)
        v3.addWidget(self._progress_widget(loc("neurons", "Neurons"), current, max_n))
        pruning_text = loc("lab_pruning_enabled", "Pruning enabled:")
        v3.addWidget(QLabel(f"{pruning_text} <b>{self.bw.pruning_enabled}</b>"))
        if engine is not None:
            remaining = engine.get_global_cooldown_remaining()
            v3.addWidget(QLabel(
                loc("lab_ov_cooldown", "Growth cooldown: {left:.0f}s left",
                    left=remaining)))
        self.ov_grid.addWidget(card3, 1, 0)
        
        # Card 4: Quick Actions
        card4 = QGroupBox(loc("lab_ov_actions", "Quick actions"))
        h = QHBoxLayout(card4)
        btn = QPushButton(loc("lab_force_hebbian", "Force Hebbian cycle"))
        btn.clicked.connect(self.bw.perform_hebbian_learning)
        h.addWidget(btn)
        if monitor is not None:
            rediagnose = QPushButton(loc("lab_rediagnose", "Re-run diagnosis"))
            rediagnose.clicked.connect(monitor.evaluate)
            h.addWidget(rediagnose)
        self.ov_grid.addWidget(card4, 1, 1)
        self.ov_grid.setRowStretch(2, 1)

    def _inspect_neuron(self, name):
        """Explain one neuron, entirely from the brain's own record of itself.

        Six questions, in the order somebody actually asks them:

            What is this?             identity, role, and what it is doing now
            Why does it exist?        the birth record, or an honest answer
            What does it stand for?   measured, from the capability monitor
            What do its connections mean?
            What has it actually done to the squid?
            What has changed here, and why?

        Nothing on this page is computed by the Laboratory. Every line comes
        from the ledger the organism writes as it learns, the capability
        monitor neurogenesis consults, or the live weights the network
        propagates through - so the Laboratory cannot tell you a story the
        squid would not tell you itself.

        The page it replaces showed a raw weight table, a hypothetical impact
        table and a static "did you know" tip. All three described the CATEGORY
        a neuron fell into rather than the neuron: a table of numbers is not an
        explanation, a simulated impact is not something that happened, and a
        tip keyed on a neuron's name says the same thing about every neuron
        that happens to share it.
        """
        if not name:
            return
        while self.inspector_lay.count():
            item = self.inspector_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        for builder in (self._card_identity, self._card_origin,
                        self._card_meaning, self._card_connections,
                        self._card_influence, self._card_history,
                        self._card_tip):
            try:
                card = builder(name)
            except Exception as exc:      # a broken card must not blank the page
                card = self._card(loc("lab_card_error", "Could not read this"),
                                  f"{type(exc).__name__}: {exc}")
            if card is not None:
                self.inspector_lay.addWidget(card)
        self.inspector_lay.addStretch(1)

    # ---------------------------------------------------------------
    #  Inspector cards
    # ---------------------------------------------------------------
    def _card(self, title, html):
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        label = QLabel(html)
        label.setWordWrap(True)
        label.setTextFormat(QtCore.Qt.RichText)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(label)
        return box

    def _functional(self, name):
        engine = getattr(self.bw, 'enhanced_neurogenesis', None)
        return (getattr(engine, 'functional_neurons', {}) or {}).get(name)

    def _role(self, name):
        """What kind of thing this neuron is, and who writes it each tick."""
        from .brain_constants import (CORE_STAT_NEURONS, PURE_INPUT_NEURONS,
                                      is_network_driven)
        if name in (getattr(self.bw, 'externally_driven', set()) or set()):
            action = (self.bw.action_for_neuron(name)
                      if hasattr(self.bw, 'action_for_neuron') else "")
            writer = loc("lab_role_action_writer",
                         "written each tick by what the squid is doing, exactly "
                         "as a sense organ is written by the world")
            if action:
                writer += loc("lab_role_action_which",
                              " - it is on whenever the squid is doing "
                              "<b>{action}</b>",
                              action=action.replace('_', ' '))
            return ('action',
                    loc("lab_role_action",
                        "An action the squid can notice itself performing"),
                    writer)
        if name in PURE_INPUT_NEURONS:
            return ('sensor', loc("lab_role_sensor", "A sense organ"),
                    loc("lab_role_sensor_writer",
                        "written each tick by the world; nothing the network "
                        "does can change it, which is why no synapse is allowed "
                        "to point at it"))
        if name in CORE_STAT_NEURONS:
            return ('drive',
                    loc("lab_role_drive",
                        "A core drive - part of the squid's body, not its network"),
                    loc("lab_role_drive_writer",
                        "written by the squid model; the network reaches it by "
                        "modulation, a small nudge each tick, never by "
                        "overwriting it"))
        if self._functional(name) is not None:
            return ('grown',
                    loc("lab_role_grown", "A neuron the squid grew for itself"),
                    loc("lab_role_grown_writer",
                        "computed by the network every tick from the synapses "
                        "that point at it"))
        if is_network_driven(name):
            return ('designed',
                    loc("lab_role_designed", "A neuron added in the Designer"),
                    loc("lab_role_designed_writer",
                        "computed by the network every tick from the synapses "
                        "that point at it"))
        return ('other', loc("lab_role_other", "A neuron"), "")

    @staticmethod
    def _reading(value):
        """A number is not a reading. This is what the number means."""
        if value >= 85:
            return loc("lab_reading_max", "as high as it goes")
        if value >= 65:
            return loc("lab_reading_high", "well above its resting level")
        if value >= 55:
            return loc("lab_reading_up", "a little above resting")
        if value > 45:
            return loc("lab_reading_neutral", "at rest, contributing nothing")
        if value > 35:
            return loc("lab_reading_down", "a little below resting")
        if value > 15:
            return loc("lab_reading_low", "well below its resting level")
        return loc("lab_reading_min", "as low as it goes")

    def _card_identity(self, name):
        kind, role, writer = self._role(name)
        value = self.bw.state.get(name, 50)
        if isinstance(value, bool):
            value = 100.0 if value else 0.0
        value = float(value)

        lines = [f"<b>{role}</b> &mdash; {writer}." if writer
                 else f"<b>{role}.</b>"]
        lines.append(loc("lab_identity_now",
                         "Right now it reads <b>{value:.0f}</b> - {reading}.",
                         value=value, reading=self._reading(value)))

        fn = self._functional(name)
        if fn is not None:
            lines.append(loc("lab_identity_spec",
                             "It is a <b>{spec}</b> neuron, and it has been "
                             "meaningfully active {count} time(s) since it was "
                             "born.",
                             spec=str(fn.specialization).replace('_', ' '),
                             count=fn.activation_count))
            if getattr(fn, 'strength_multiplier', 1.0) > 1.0:
                lines.append(loc("lab_identity_strength",
                                 "It has been deepened to <b>{mult:.1f}x</b> "
                                 "strength, because the brain met the same kind "
                                 "of problem again and had no room to grow "
                                 "another neuron for it.",
                                 mult=fn.strength_multiplier))

        monitor = getattr(self.bw, 'capability', None)
        if monitor is not None and hasattr(monitor, 'deficits_naming'):
            open_deficits = monitor.deficits_naming(name)
            if open_deficits:
                worst = max(open_deficits, key=lambda d: d.severity)
                lines.append(loc("lab_identity_deficit",
                                 "<span style='color:#b7791f;'>It is part of a "
                                 "problem the brain has not solved:</span> "
                                 "{summary}.", summary=worst.summary))
        return self._card(loc("lab_card_identity", "What is this?"),
                          "<br><br>".join(lines))

    def _card_origin(self, name):
        ledger = getattr(self.bw, 'ledger', None)
        if ledger is None:
            return None
        html = ledger.explain_neuron(name).replace("\n", "<br>")
        origin = ledger.origins.get(name)
        if origin is not None and origin.evidence:
            rows = "".join(
                f"<li><b>{str(k).replace('_', ' ')}</b>: "
                f"{self._readable_evidence(v)}</li>"
                for k, v in list(origin.evidence.items())[:8]
                if len(str(v)) < 160)
            if rows:
                html += ("<br><br><i>"
                         + loc("lab_origin_evidence",
                               "The measurements behind that diagnosis:")
                         + f"</i><ul style='margin-left:-20px;'>{rows}</ul>")
        return self._card(loc("lab_origin_title", "Why does this neuron exist?"),
                          html)

    @staticmethod
    def _readable_evidence(value):
        """A measurement, without its Python punctuation."""
        if isinstance(value, dict):
            return ", ".join(f"{str(k).replace('_', ' ')} {v}"
                             for k, v in value.items())
        if isinstance(value, (list, tuple, set)):
            return ", ".join(str(v).replace('_', ' ') for v in value)
        if isinstance(value, float):
            return f"{value:g}"
        return str(value).replace('_', ' ')

    def _card_meaning(self, name):
        """What this neuron has turned out to stand for, measured."""
        monitor = getattr(self.bw, 'capability', None)
        if monitor is None or not hasattr(monitor, 'what_does_it_represent'):
            return None
        readings = monitor.what_does_it_represent(name)
        if not readings:
            return self._card(
                loc("lab_meaning_title", "What does it stand for?"),
                loc("lab_meaning_none",
                    "Nothing yet, as far as the squid's own statistics can "
                    "tell. This neuron does not behave measurably differently "
                    "in any situation the squid keeps meeting, so it is not "
                    "standing for any of them. It may be too young, or it may "
                    "simply be carrying signal from one place to another."))

        lines = [loc("lab_meaning_lead",
                     "Measured from how this neuron actually behaves, not from "
                     "what it was grown for. The number is Cohen's <i>d</i>: "
                     "how far apart its activation is when the situation holds "
                     "and when it does not. It is the same statistic "
                     "neurogenesis uses to decide whether the brain can tell a "
                     "situation apart at all.")]
        for row in readings:
            what = str(row['name']).replace('|', ' and ').replace('_', ' ')
            if row['kind'] == 'action':
                subject = loc("lab_meaning_action",
                              "while the squid is doing <b>{what}</b>", what=what)
            else:
                subject = loc("lab_meaning_situation",
                              "when <b>{what}</b>", what=what)
            if row['direction'] > 0:
                moves = loc("lab_meaning_up", "rises to {inside:.0f}",
                            inside=row['inside_mean'])
            else:
                moves = loc("lab_meaning_down", "falls to {inside:.0f}",
                            inside=row['inside_mean'])
            if row['separation'] >= 1.2:
                strength = loc("lab_meaning_unmistakable", "unmistakable")
            elif row['separation'] >= 0.8:
                strength = loc("lab_meaning_clear", "clear")
            else:
                strength = loc("lab_meaning_slight", "slight")
            lines.append(
                f"&bull; {subject}, it {moves} "
                + loc("lab_meaning_otherwise", "(otherwise {outside:.0f})",
                      outside=row['outside_mean'])
                + f" &mdash; <b>{strength}</b>, d = {row['separation']:.2f}, "
                + loc("lab_meaning_seen", "seen {n} time(s)",
                      n=row['occurrences']))
        return self._card(loc("lab_meaning_title", "What does it stand for?"),
                          "<br><br>".join(lines))

    def _connection_sentence(self, name, edge, weight):
        """What one synapse implies, in a sentence, with why it is that value."""
        from .neural_provenance import humanise, MECHANISMS
        ledger = getattr(self.bw, 'ledger', None)
        label = ledger.label if ledger is not None else humanise
        src, dst = edge
        magnitude = abs(float(weight))
        # Three decimals for anything a two-decimal reading would print as
        # "+0.00", which is not a weight, it is a rounding artefact.
        shown = f"{weight:+.3f}" if magnitude < 0.05 else f"{weight:+.2f}"
        if magnitude >= 0.7:
            strength = loc("lab_conn_decisive", "decisively")
        elif magnitude >= 0.45:
            strength = loc("lab_conn_strongly", "strongly")
        elif magnitude >= 0.2:
            strength = loc("lab_conn_moderately", "moderately")
        else:
            strength = loc("lab_conn_faintly", "faintly")
        direction = (loc("lab_conn_up", "up") if weight > 0
                     else loc("lab_conn_down", "down"))

        if src == name:
            sentence = loc(
                "lab_conn_out",
                "When <b>{me}</b> is above its resting level it pushes "
                "<b>{other}</b> {direction}, {strength} (weight {w}); "
                "below resting level it does the opposite.",
                me=label(name), other=label(dst), direction=direction,
                strength=strength, w=shown)
        else:
            sentence = loc(
                "lab_conn_in",
                "<b>{other}</b> being above its resting level drives this "
                "neuron {direction}, {strength} (weight {w}).",
                other=label(src), direction=direction, strength=strength,
                w=shown)

        why = ""
        if ledger is not None:
            totals = ledger.edge_totals(edge)
            if totals:
                mechanism, amount = max(totals.items(),
                                        key=lambda kv: abs(kv[1]))
                why = loc("lab_conn_why",
                          "Most of that value ({amount:+.2f}) came from {reason}.",
                          amount=amount,
                          reason=MECHANISMS.get(mechanism, mechanism))
        return sentence, why

    def _card_connections(self, name):
        weights = getattr(self.bw, 'weights', {}) or {}
        outgoing = sorted(((e, w) for e, w in weights.items() if e[0] == name),
                          key=lambda row: -abs(row[1]))
        incoming = sorted(((e, w) for e, w in weights.items() if e[1] == name),
                          key=lambda row: -abs(row[1]))

        if not outgoing and not incoming:
            return self._card(
                loc("lab_conn_title", "What do its connections mean?"),
                loc("lab_conn_none",
                    "It has no synapses at all. Nothing can drive it and it can "
                    "drive nothing, so whatever it computes stays where it is. "
                    "The capability monitor counts that as a deficit, and the "
                    "brain will grow a connector to bridge it back in."))

        blocks = []
        for heading, rows in ((loc("lab_conn_drives", "What it drives"), outgoing),
                              (loc("lab_conn_driven", "What drives it"), incoming)):
            if not rows:
                continue
            items = []
            for edge, weight in rows[:8]:
                sentence, why = self._connection_sentence(name, edge, weight)
                tag = self._influence_badge(weight, incoming=(edge[1] == name))
                items.append("<li>" + sentence + " " + tag
                             + (f"<br><span style='color:#666;'>{why}</span>"
                                if why else "") + "</li>")
            if len(rows) > 8:
                items.append("<li><i>"
                             + loc("lab_conn_more", "...and {n} more",
                                   n=len(rows) - 8) + "</i></li>")
            blocks.append(f"<b>{heading}</b><ul style='margin-left:-20px;'>"
                          + "".join(items) + "</ul>")

        if name in (getattr(self.bw, 'externally_driven', set()) or set()):
            blocks.append("<br><i>" + loc(
                "lab_conn_external",
                "Nothing drives this neuron through a synapse, and nothing may: "
                "the world writes it every tick, so a synapse pointing at it "
                "would be overwritten before anything could read what it put "
                "there.") + "</i>")
        return self._card(loc("lab_conn_title",
                              "What do its connections mean?"), "".join(blocks))

    def _card_influence(self, name):
        """What this neuron has actually done to the squid, not what it could."""
        from .brain_constants import CORE_STAT_NEURONS
        ledger = getattr(self.bw, 'ledger', None)
        weights = getattr(self.bw, 'weights', {}) or {}
        lines = []

        if ledger is not None:
            influence = getattr(ledger, '_influence', {}) or {}
            mine = [(edge, rec) for edge, rec in influence.items()
                    if edge[0] == name]
            mine.sort(key=lambda kv: -abs(kv[1].get('total', 0.0)))
            for edge, record in mine[:6]:
                lines.append(loc(
                    "lab_influence_row",
                    "It has pushed <b>{other}</b> by {total:+.2f} points in "
                    "total, over {ticks} tick(s) in which it was doing anything "
                    "at all.",
                    other=ledger.label(edge[1]),
                    total=record.get('total', 0.0),
                    ticks=record.get('ticks', 0)))

        drives = [e for e in weights if e[0] == name and e[1] in CORE_STAT_NEURONS]
        if not lines:
            if drives:
                lines.append(loc(
                    "lab_influence_pending",
                    "It has synapses onto the squid's physiology but has not "
                    "yet been active enough to move any of it. Modulation is "
                    "deliberately gentle: a saturated source through a maximal "
                    "synapse contributes about 0.15 points a tick."))
            else:
                lines.append(loc(
                    "lab_influence_indirect",
                    "It does not touch the squid's physiology directly. "
                    "Whatever it contributes reaches behaviour through the "
                    "neurons it drives."))

        causal = getattr(self.bw, 'causal_learning', None)
        action = (self.bw.action_for_neuron(name)
                  if hasattr(self.bw, 'action_for_neuron') else "")
        if action and causal is not None:
            for stat, entry in (causal.contingencies.get(action, {}) or {}).items():
                baseline = causal.baseline_drift(stat, action)
                effect = entry.effect(baseline)
                if abs(effect) < 1.0:
                    continue
                lines.append(loc(
                    "lab_influence_contingency",
                    "The squid believes {action} sends {stat} {direction} by "
                    "about {effect:.0f} points ({conf:.0%} confident, after "
                    "{n} observation(s)).",
                    action=action.replace('_', ' '),
                    stat=str(stat).replace('_', ' '),
                    direction=("up" if effect > 0 else "down"),
                    effect=abs(effect), conf=entry.confidence(baseline),
                    n=entry.n))
        # ...and what it is doing right now, which is a projection rather
        # than a record, and is labelled as one.
        projection = self._compute_impacts(name)
        if projection:
            rows = "".join(
                f"<li>{ledger.label(partner) if ledger else partner}: "
                f"<b>{delta:+.2f}</b></li>"
                for partner, delta in sorted(projection.items(),
                                             key=lambda kv: -abs(kv[1]))[:6])
            lines.append("<i>" + loc(
                "lab_influence_now",
                "At its current activation, and if nothing else changed, this "
                "is what it would contribute to each of its targets on the next "
                "tick:") + f"</i><ul style='margin-left:-20px;'>{rows}</ul>")
        return self._card(
            loc("lab_influence_title", "What has it actually done?"),
            "<br><br>".join(lines))

    def _card_tip(self, name):
        """The one card that is allowed to teach rather than report."""
        tip = self._educational_tip(name)
        if not tip:
            return None
        return self._card(loc("lab_did_you_know", "Did you know?"), tip)

    def _card_history(self, name):
        ledger = getattr(self.bw, 'ledger', None)
        if ledger is None:
            return None
        events = []
        for edge in list(getattr(self.bw, 'weights', {}).keys()):
            if name not in edge:
                continue
            events.extend(ledger.weight_history(edge, limit=6))
        events.sort(key=lambda e: e.timestamp)
        if events:
            rows = "".join(f"<li>{e.describe()}</li>" for e in events[-12:])
            html = f"<ul style='margin-left:-20px;'>{rows}</ul>"
        else:
            html = loc("lab_history_none",
                       "Nothing has changed any of this neuron's synapses yet.")
        return self._card(loc("lab_history_title",
                              "What has changed here, and why"), html)

    # ================================================================
    #  EDIT tab
    # ================================================================
    def _paint_edit(self):
        while self.edit_lay.count():
            item = self.edit_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        if not self.lock_check.isChecked():
            return

        card = QGroupBox(loc("lab_edit_header", "Neuron values (drag to change)  –  click 🔒 to lock"))
        grid = QGridLayout(card)

        for row, name in enumerate(sorted(self.bw.neuron_positions.keys())):
            val = self.forced_neurons.get(name, self.bw.state.get(name, 50))
            if isinstance(val, bool):
                continue

            # Preserve existing lock state
            was_locked = self.locked_neurons.get(name, {}).get("locked", False)

            # label
            grid.addWidget(QLabel(name), row, 0)

            # slider
            slider = QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(int(val))
            slider.valueChanged.connect(lambda v, n=name: self._set_neuron(n, v))
            grid.addWidget(slider, row, 1)

            # spin-box
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setValue(int(val))
            spin.valueChanged.connect(lambda v, n=name: self._set_neuron(n, v))
            grid.addWidget(spin, row, 2)

            # pad-lock button
            btn = QToolButton()
            btn.setCheckable(True)
            btn.setChecked(was_locked)
            btn.setText("🔒" if was_locked else "🔓")
            btn.setFixedSize(24, 24)
            btn.setStyleSheet("QToolButton:checked { color: red; }")
            btn.toggled.connect(lambda checked, n=name, b=btn: self._toggle_lock(n, b))
            grid.addWidget(btn, row, 3)

            # store references
            self.locked_neurons[name] = {
                "locked": was_locked,
                "slider": slider,
                "spin": spin,
                "button": btn
            }

        self.edit_lay.addWidget(card)
        self.edit_lay.addStretch(1)

    # -----------  lock / set slots  ---------------------------------
    def update_debug_info(self):
        self._refresh()

    def _toggle_lock(self, name, button):
        is_locked = button.isChecked()
        self.locked_neurons[name]["locked"] = is_locked
        button.setText("🔒" if is_locked else "🔓")
        
        if is_locked:
            current_value = self.bw.state.get(name, 50)
            self.forced_neurons[name] = int(current_value)
            self.status_lbl.setText(loc("lab_status_locked", "🔒 {name} locked at {value}", name=name, value=current_value))
        else:
            if name in self.forced_neurons:
                del self.forced_neurons[name]
            self.status_lbl.setText(loc("lab_status_unlocked", "🔓 {name} unlocked", name=name))

    def _set_neuron(self, name, value):
        self.forced_neurons[name] = value
        self.bw.state[name] = value
        self.bw.update()

    def _apply_forced_values(self):
        if not self.isVisible():
            return
            
        for name, value in self.forced_neurons.items():
            if name in self.bw.state:
                self.bw.state[name] = value
                
                # NEW: Sync to squid if it's a core statistic neuron
                if hasattr(self.bw, 'tamagotchi_logic') and hasattr(self.bw.tamagotchi_logic, 'squid'):
                    squid = self.bw.tamagotchi_logic.squid
                    if name in ['hunger', 'happiness', 'cleanliness', 'sleepiness', 
                            'health', 'satisfaction', 'curiosity', 'anxiety']:
                        setattr(squid, name, value)
                
                if name in self.locked_neurons and self.locked_neurons[name]["locked"]:
                    slider = self.locked_neurons[name]["slider"]
                    spin = self.locked_neurons[name]["spin"]
                    
                    int_value = int(value)
                    if slider.value() != int_value:
                        slider.blockSignals(True)
                        slider.setValue(int_value)
                        slider.blockSignals(False)
                    
                    if spin.value() != int_value:
                        spin.blockSignals(True)
                        spin.setValue(int_value)
                    spin.blockSignals(False)

    # ================================================================
    #  Slots
    # ================================================================
    def _toggle_live(self, on):
        self.timer.setInterval(1000 if on else 10000)

    def _unlock_editing(self, on):
        if on:
            title = loc("lab_unlock_title", "Unlock editing?")
            msg = loc("lab_unlock_msg", "You can now change neuron values and force creation events. Use responsibly!")
            ans = QMessageBox.question(self, title, msg)
            if ans != QMessageBox.Yes:
                self.lock_check.setChecked(False)
                return
        self.edit_warn.setVisible(not on)
        self._paint_edit()

    def _force_neurogenesis(self, typ):
        """Grow a neuron of this type now, for inspection.

        This used to write a made-up `{type}_exposure = 999` into the brain
        state and hope a threshold somewhere noticed. Nothing read that key
        after the trigger rewrite, so the button did nothing. It now calls the
        one creation path directly and says what it did.
        """
        engine = getattr(self.bw, 'enhanced_neurogenesis', None)
        if engine is None:
            print("No neurogenesis engine on this brain.")
            return
        name = engine.create_neuron(typ, brain_state=dict(self.bw.state),
                                    environment={})
        if name:
            print(f"🧬 Laboratory forced growth of {name} ({typ})")
        else:
            print(f"🧬 Laboratory could not grow a {typ} neuron "
                  f"(type cap or neuron limit reached)")
        self._refresh()

    # ================================================================
    #  Pretty helpers
    # ================================================================
    def _progress_bar(self, pct):
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(pct))
        bar.setTextVisible(True)
        bar.setStyleSheet("QProgressBar::chunk{background:#4CAF50;}")
        return bar

    def _progress_widget(self, title, cur, maxi):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(QLabel(f"{title}  {cur}/{maxi}"))
        bar = self._progress_bar((cur / maxi) * 100)
        bar.setMaximumHeight(12)
        h.addWidget(bar)
        return w

    def _influence_badge(self, w, incoming=False):
        mag = abs(w)
        if mag < 0.1:
            return badge(loc("lab_inf_tiny", "tiny"), "#666", "#fff")
        if mag < 0.3:
            return badge(loc("lab_inf_mild", "mild"), "#fff", "#555")
        if mag < 0.6:
            return badge(loc("lab_inf_mod", "moderate"), "#fff", "#000")
        return badge(loc("lab_inf_strong", "STRONG"), "#fff", "#d9534f")

    def _compute_impacts(self, name):
        """What this neuron would contribute to each target on the next tick.

        Uses propagation's own reading of how much a neuron is contributing, so
        the projection cannot disagree with what the network will actually do -
        including for a sense organ, whose quiet state is zero rather than the
        midpoint.
        """
        from .propagation import signal_of
        impacts = {}
        val = self.bw.state.get(name, 50)
        if isinstance(val, bool):
            val = 100.0 if val else 0.0
        signal = signal_of(name, float(val))
        if abs(signal) < 5:
            return impacts
        for (src, dst), w in self.bw.weights.items():
            if src == name and dst not in self.bw.excluded_neurons:
                impacts[dst] = signal * w * 0.5
        return impacts

    def _educational_tip(self, name):
        # 1. Try specific key first
        specific_key = f"lab_tip_{name}"
        text = loc(specific_key)
        
        # Check if translation was found (if loc returns key when missing)
        if text != specific_key:
            return text

        # 2. Core neurons
        core_keys = ["hunger", "happiness", "anxiety", "curiosity"]
        if name in core_keys:
            return loc(specific_key)
                
        if name in self.bw.original_neuron_positions:
            return loc("lab_tip_core", "Core neuron – fundamental to survival.")
                
        # If the ledger recorded why this neuron was grown, say THAT. It is
        # the neuron's own account of itself, and it is available before any of
        # the category guesses below - which is where this used to consult it,
        # so a grown neuron with a perfectly good birth record was told it had
        # a "purpose inferred from birth context".
        ledger = getattr(self.bw, 'ledger', None)
        origin = ledger.origins.get(name) if ledger is not None else None
        if origin is not None and origin.deficit_summary:
            return (f"It exists because {origin.deficit_summary}. "
                    f"It was wired to {origin.remedy or 'remedy that'}.")

        nd = getattr(self.bw, 'neurogenesis_data', {})
        det = nd.get('new_neurons_details', {}).get(name)

        if not det:
            return loc("lab_tip_neuro_default", "Neurogenesis neuron – purpose inferred from birth context.")

        # Special handling for connectors
        if det.get('trigger_type') == 'connector':
            return loc("lab_tip_connector", "Generated by the network to connect orphaned neurons. Has 3 connections.")
                
        return loc("lab_tip_neuro_fmt", 
                "Created by <b>{trigger}</b> – specialises in <b>{spec}</b>. Its job is to turn experiences into long-term behaviour.",
                trigger=det.get('trigger_type'),
                spec=det.get('specialisation','?'))


NeurogenesisDebugDialog = NeuronLaboratory  #  Old name alias – Backwards compatibility


# ------------------------------------------------------------------
#  Quick test when run standalone
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    # dummy brain-widget for test
    class DummyBW:
        neuron_positions = {"hunger": (100, 100), "happiness": (200, 100)}
        excluded_neurons = []
        original_neuron_positions = {"hunger": (100, 100), "happiness": (200, 100)}
        state = {"hunger": 60, "happiness": 40}
        pruning_enabled = True
        weights = {("hunger", "happiness"): 0.75}
        neurogenesis_data = {
            "novelty_counter": 2.3,
            "stress_counter": 0.4,
            "reward_counter": 1.1,
            "new_neurons_details": {
                "novelty_0": {"trigger_type": "novelty", "created_at": time.time() - 120,
                              "specialisation": "object_investigation", "trigger_value_at_creation": 3.2,
                              "associated_state_snapshot": {"curiosity": 80}}
            },
            "last_neuron_time": time.time() - 300
        }
        neurogenesis_config = {"novelty_threshold": 3, "stress_threshold": 0.7, "reward_threshold": 0.6,
                               "max_neurons": 32, "cooldown": 180}

        def perform_hebbian_learning(self):
            print("Hebbian cycle triggered")
            
        def update(self):
            # dummy update for slider/spinbox changes
            pass

    dlg = NeuronLaboratory(DummyBW())
    dlg.show()

    sys.exit(app.exec_())
