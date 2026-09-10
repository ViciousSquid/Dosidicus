"""
brain_knowledge_tab.py - what the squid knows, and why, in plain English.

This tab is a *view*. It computes nothing about the brain and keeps no copy of
it: every line it shows comes from the same provenance ledger the organism
itself writes to as it learns (src/neural_provenance.py), the same capability
monitor neurogenesis consults (src/capability.py), and the live weights the
network propagates through. If the tab says a synapse moved because two things
kept happening together, that is because the mechanism that moved it said so at
the time - not because the UI diffed a snapshot afterwards and guessed.

Four questions, four sub-tabs:

    What does it know?          every learned association and contingency
    Why did this weight change? the full provenance of one synapse
    Why does this neuron exist? the deficit a grown neuron was born to remedy
    What can't it do yet?       the deficits driving its next growth
"""

from PyQt5 import QtCore, QtGui, QtWidgets

from .brain_base_tab import BrainBaseTab
from .display_scaling import DisplayScaling
from .neural_provenance import humanise
from .localisation import loc


_KIND_COLOURS = {
    'association': ("#e3f2fd", "#1565c0"),
    'contingency': ("#e8f5e9", "#2e7d32"),
    'structure':   ("#fff3e0", "#e65100"),
}

_KIND_LABEL_KEYS = {
    'association': ("knowledge_kind_association", "association"),
    'contingency': ("knowledge_kind_contingency", "cause and effect"),
    'structure':   ("knowledge_kind_structure", "new structure"),
}


def _kind_style(kind):
    """Colours are fixed; the label is looked up each time so a language
    switch is picked up without rebuilding the tab."""
    bg, colour = _KIND_COLOURS.get(kind, ("#f5f5f5", "#424242"))
    key, default = _KIND_LABEL_KEYS.get(kind, (None, None))
    label = loc(key, default) if key else kind
    return bg, colour, label


def _confidence_bar(confidence: float, colour: str) -> str:
    filled = int(round(max(0.0, min(1.0, confidence)) * 20))
    return (f"<span style='font-family:monospace; color:{colour};'>"
            f"{'█' * filled}{'░' * (20 - filled)}</span>")


class KnowledgeTab(BrainBaseTab):
    """Reads the brain's own record of what it learned and why."""

    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None,
                 config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)

        self._topic = ""
        self._last_refresh = 0.0

        self._build_ui()

        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(2500)
        self.refresh()

    # ------------------------------------------------------------------
    # Access to the authoritative objects. Never cached, never copied.
    # ------------------------------------------------------------------
    @property
    def ledger(self):
        return getattr(self.brain_widget, 'ledger', None)

    @property
    def capability(self):
        return getattr(self.brain_widget, 'capability', None)

    @property
    def causal(self):
        return getattr(self.brain_widget, 'causal_learning', None)

    # ==================================================================
    # UI
    # ==================================================================
    def _build_ui(self):
        self.tabs = QtWidgets.QTabWidget()
        font = QtGui.QFont()
        font.setPointSize(DisplayScaling.font_size(10))
        self.tabs.setFont(font)
        self.layout.addWidget(self.tabs)

        self.tabs.addTab(self._build_knowledge_page(),
                         loc("knowledge_subtab_knows", "What it knows"))
        self.tabs.addTab(self._build_weight_page(),
                         loc("knowledge_subtab_weight", "Why this weight?"))
        self.tabs.addTab(self._build_neuron_page(),
                         loc("knowledge_subtab_neuron", "Why this neuron?"))
        self.tabs.addTab(self._build_capability_page(),
                         loc("knowledge_subtab_capability", "What it can't do yet"))

        self.summary_label = QtWidgets.QLabel("")
        # The summary text grows with the brain ("N recorded synaptic changes
        # across M synapses . ..."), and an unwrapped QLabel reports that whole
        # string as its minimum width. That minimum propagates all the way up
        # to the Brain Tool window, which Qt then refuses to open any narrower
        # - so the window silently ignored its own configured width and opened
        # ~1150px wide. Wrapping the label, and pinning an explicit minimum,
        # keeps this line from dictating the size of the window that shows it.
        self.summary_label.setWordWrap(True)
        self.summary_label.setMinimumWidth(DisplayScaling.scale(120))
        self.summary_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                                         QtWidgets.QSizePolicy.Preferred)
        self.summary_label.setStyleSheet(
            f"color:#546e7a; font-size:{DisplayScaling.font_size(10)}pt; padding:4px;")
        self.layout.addWidget(self.summary_label)

    # -- page 1: knowledge ---------------------------------------------
    def _build_knowledge_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel(
            loc("knowledge_ask_prefix", "What does the squid know about")))
        self.topic_edit = QtWidgets.QLineEdit()
        self.topic_edit.setPlaceholderText(loc(
            "knowledge_topic_placeholder", "anything… try 'food', 'anxiety', 'plant'"))
        self.topic_edit.textChanged.connect(self._on_topic_changed)
        controls.addWidget(self.topic_edit, 1)
        controls.addWidget(QtWidgets.QLabel(loc("knowledge_ask_suffix", "?")))

        refresh_btn = QtWidgets.QPushButton(loc("knowledge_btn_refresh", "Refresh"))
        refresh_btn.clicked.connect(self.refresh)
        controls.addWidget(refresh_btn)

        export_btn = QtWidgets.QPushButton(loc("knowledge_btn_export", "Export…"))
        export_btn.setToolTip(loc("knowledge_tip_export",
                                  "Save everything the squid knows, in plain English"))
        export_btn.clicked.connect(self._export_knowledge)
        controls.addWidget(export_btn)
        layout.addLayout(controls)

        self.knowledge_view = QtWidgets.QTextBrowser()
        self.knowledge_view.setOpenExternalLinks(False)
        layout.addWidget(self.knowledge_view, 1)
        return page

    # -- page 2: weight provenance -------------------------------------
    def _build_weight_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel(loc("knowledge_lbl_synapse", "Synapse:")))
        self.edge_combo = QtWidgets.QComboBox()
        self.edge_combo.setMinimumWidth(DisplayScaling.scale(320))
        self.edge_combo.currentIndexChanged.connect(self._show_weight_explanation)
        controls.addWidget(self.edge_combo, 1)
        layout.addLayout(controls)

        self.weight_view = QtWidgets.QTextBrowser()
        layout.addWidget(self.weight_view, 1)

        self.weight_table = QtWidgets.QTableWidget(0, 6)
        self.weight_table.setHorizontalHeaderLabels([
            loc("knowledge_col_when", "When"),
            loc("knowledge_col_from", "From"),
            loc("knowledge_col_to", "To"),
            loc("knowledge_col_change", "Change"),
            loc("knowledge_col_mechanism", "Mechanism"),
            loc("knowledge_col_evidence", "Evidence"),
        ])
        self.weight_table.horizontalHeader().setStretchLastSection(True)
        self.weight_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.weight_table, 1)
        return page

    # -- page 3: neuron provenance -------------------------------------
    def _build_neuron_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel(loc("knowledge_lbl_neuron", "Neuron:")))
        self.neuron_combo = QtWidgets.QComboBox()
        self.neuron_combo.currentIndexChanged.connect(self._show_neuron_explanation)
        controls.addWidget(self.neuron_combo, 1)
        layout.addLayout(controls)

        self.neuron_view = QtWidgets.QTextBrowser()
        layout.addWidget(self.neuron_view, 1)
        return page

    # -- page 4: capability --------------------------------------------
    def _build_capability_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)

        blurb = QtWidgets.QLabel(loc(
            "knowledge_capability_blurb",
            "A neuron is grown when the network has a persistent functional "
            "deficiency it cannot fix with the structure it already has - not "
            "because a particular event happened. This is that diagnosis, live."))
        blurb.setWordWrap(True)
        blurb.setStyleSheet(f"color:#37474f; font-size:{DisplayScaling.font_size(10)}pt;")
        layout.addWidget(blurb)

        self.capability_view = QtWidgets.QTextBrowser()
        layout.addWidget(self.capability_view, 1)
        return page

    # ==================================================================
    # Refresh
    # ==================================================================
    def _on_topic_changed(self, text):
        self._topic = text.strip()
        self._refresh_knowledge()

    def update_from_brain_state(self, state):
        # The tab is driven by its own timer; the brain-state broadcast only
        # needs to keep the pickers in step with a network that just grew.
        self._sync_pickers()

    def refresh(self):
        if self.brain_widget is None:
            return
        self._sync_pickers()
        self._refresh_knowledge()
        self._show_weight_explanation()
        self._show_neuron_explanation()
        self._refresh_capability()
        self._refresh_summary()

    def _refresh_summary(self):
        ledger = self.ledger
        if ledger is None:
            self.summary_label.setText(
                loc("knowledge_no_provenance", "This brain keeps no provenance."))
            return
        s = ledger.summary()
        causal = self.causal
        contingencies = 0
        if causal is not None:
            try:
                contingencies = len(causal.known_contingencies())
            except Exception:
                contingencies = 0
        self.summary_label.setText(loc(
            "knowledge_summary",
            "{changes} recorded synaptic changes across "
            "{synapses} synapses · {grown} neurons grown, "
            "{pruned} pruned · {episodes} experiences remembered · "
            "{contingencies} things it has worked out about its own actions",
            changes=s['weight_changes'], synapses=s['tracked_synapses'],
            grown=s['neurons_grown'], pruned=s['neurons_pruned'],
            episodes=s['episodes'], contingencies=contingencies))

    def _sync_pickers(self):
        weights = getattr(self.brain_widget, 'weights', {}) or {}
        ledger = self.ledger

        edges = sorted(weights.keys(), key=lambda e: (-abs(weights[e]), e))
        current = self.edge_combo.currentData()
        if len(edges) != self.edge_combo.count() or current not in edges:
            self.edge_combo.blockSignals(True)
            self.edge_combo.clear()
            for edge in edges:
                label = (f"{ledger.label(edge[0]) if ledger else humanise(edge[0])}"
                         f"  →  "
                         f"{ledger.label(edge[1]) if ledger else humanise(edge[1])}"
                         f"   ({weights[edge]:+.3f})")
                self.edge_combo.addItem(label, edge)
            if current in edges:
                self.edge_combo.setCurrentIndex(edges.index(current))
            self.edge_combo.blockSignals(False)

        names = sorted(getattr(self.brain_widget, 'neuron_positions', {}) or {})
        if names != [self.neuron_combo.itemData(i)
                     for i in range(self.neuron_combo.count())]:
            selected = self.neuron_combo.currentData()
            self.neuron_combo.blockSignals(True)
            self.neuron_combo.clear()
            for name in names:
                self.neuron_combo.addItem(
                    ledger.label(name) if ledger else humanise(name), name)
            if selected in names:
                self.neuron_combo.setCurrentIndex(names.index(selected))
            self.neuron_combo.blockSignals(False)

    # ------------------------------------------------------------------
    def _refresh_knowledge(self):
        ledger = self.ledger
        if ledger is None:
            self.knowledge_view.setHtml(
                "<p>%s</p>" % loc("knowledge_no_provenance",
                                  "This brain keeps no provenance."))
            return
        try:
            items = ledger.knowledge(self._topic or None)
        except Exception as exc:
            self.knowledge_view.setHtml("<p>%s</p>" % loc(
                "knowledge_ledger_error", "Could not read the ledger: {error}", error=exc))
            return

        if not items:
            if self._topic:
                self.knowledge_view.setHtml(
                    "<p style='padding:20px;'>%s</p>" % loc(
                        "knowledge_empty_topic",
                        "The squid has not learned anything about <b>{topic}</b> "
                        "yet. Everything it knows comes from experience, so give "
                        "it some.", topic=self._topic))
            else:
                self.knowledge_view.setHtml(
                    "<p style='padding:20px;'>%s</p>" % loc(
                        "knowledge_empty",
                        "The squid has not learned anything yet. Its synapses are "
                        "still the ones it was born with."))
            return

        self.knowledge_view.setHtml(self._render_items(items))

    def _render_items(self, items) -> str:
        parts = ["<body style='font-family:sans-serif;'>"]
        for item in items:
            bg, colour, kind_label = _kind_style(item.kind)
            rows = []
            if item.experience:
                rows.append((loc("knowledge_row_experience",
                                 "What experience caused it"), item.experience))
            if item.action:
                rows.append((loc("knowledge_row_action",
                                 "Which action was involved"), humanise(item.action)))
            if item.consequence:
                rows.append((loc("knowledge_row_consequence",
                                 "What consequence followed"), item.consequence))
            if item.reason:
                rows.append((loc("knowledge_row_reason",
                                 "Why the connection changed"), item.reason))
            if item.behaviour:
                rows.append((loc("knowledge_row_behaviour",
                                 "How it affected behaviour"), item.behaviour))

            detail = "".join(
                f"<tr><td style='color:{colour}; padding:2px 10px 2px 0; "
                f"white-space:nowrap; vertical-align:top;'><b>{label}</b></td>"
                f"<td style='padding:2px 0;'>{value}</td></tr>"
                for label, value in rows)

            parts.append(
                f"<div style='background:{bg}; border-left:5px solid {colour}; "
                f"margin:8px 2px; padding:10px 14px; border-radius:6px;'>"
                f"<div style='font-size:11pt; color:#1b1b1b;'><b>{item.statement}</b>"
                f"<span style='float:right; color:{colour}; font-size:9pt;'>"
                f"{kind_label}</span></div>"
                f"<table style='margin-top:6px; font-size:9.5pt; color:#333;'>{detail}</table>"
                f"<div style='margin-top:6px; font-size:9pt; color:{colour};'>"
                + loc("knowledge_confidence", "confidence {confidence}",
                      confidence=f"{item.confidence:.0%}")
                + f" {_confidence_bar(item.confidence, colour)} &nbsp;·&nbsp; "
                + loc("knowledge_strength", "strength {strength}",
                      strength=f"{item.strength:+.2f}")
                + "</div>"
                f"</div>")
        parts.append("</body>")
        return "".join(parts)

    # ------------------------------------------------------------------
    def _show_weight_explanation(self, *_args):
        ledger = self.ledger
        edge = self.edge_combo.currentData()
        if ledger is None or not edge:
            self.weight_view.setPlainText("")
            self.weight_table.setRowCount(0)
            return

        try:
            text = ledger.explain_weight(tuple(edge))
        except Exception as exc:
            text = loc("knowledge_weight_error",
                       "Could not explain this synapse: {error}", error=exc)
        self.weight_view.setPlainText(text)

        events = ledger.weight_history(tuple(edge), limit=40)
        self.weight_table.setRowCount(len(events))
        for row, event in enumerate(reversed(events)):
            evidence = []
            r = event.detail.get('correlation')
            if isinstance(r, (int, float)):
                evidence.append(f"r={r:+.2f}")
            n = event.detail.get('samples')
            if n:
                evidence.append(f"n={n}")
            if event.detail.get('note'):
                evidence.append(str(event.detail['note']))
            ep = ledger.get_episode(event.episode_id)
            if ep is not None:
                evidence.append(loc("knowledge_evidence_after", "after it {action}",
                                    action=humanise(ep.action)))

            cells = [
                QtCore.QDateTime.fromSecsSinceEpoch(
                    int(event.timestamp)).toString("HH:mm:ss"),
                ledger.label(event.edge[0]),
                ledger.label(event.edge[1]),
                f"{event.old_weight:+.3f} → {event.new_weight:+.3f} ({event.delta:+.3f})",
                event.mechanism,
                "; ".join(evidence),
            ]
            for col, value in enumerate(cells):
                self.weight_table.setItem(row, col,
                                          QtWidgets.QTableWidgetItem(str(value)))
        self.weight_table.resizeColumnsToContents()

    # ------------------------------------------------------------------
    def _show_neuron_explanation(self, *_args):
        ledger = self.ledger
        name = self.neuron_combo.currentData()
        if ledger is None or not name:
            self.neuron_view.setPlainText("")
            return
        try:
            self.neuron_view.setPlainText(ledger.explain_neuron(name))
        except Exception as exc:
            self.neuron_view.setPlainText(loc(
                "knowledge_neuron_error", "Could not explain this neuron: {error}", error=exc))

    # ------------------------------------------------------------------
    def _refresh_capability(self):
        monitor = self.capability
        engine = getattr(self.brain_widget, 'enhanced_neurogenesis', None)
        if monitor is None:
            self.capability_view.setHtml(
                "<p>%s</p>" % loc("knowledge_no_monitor",
                                  "This brain has no capability monitor."))
            return

        parts = ["<body style='font-family:sans-serif;'>"]
        try:
            deficits = sorted(monitor.active.values(), key=lambda d: -d.severity)
            actionable = {d.key for d in monitor.actionable()}
        except Exception as exc:
            self.capability_view.setHtml("<p>%s</p>" % loc(
                "knowledge_monitor_error", "Could not read the monitor: {error}", error=exc))
            return

        if not deficits:
            parts.append(
                "<p style='padding:14px; background:#e8f5e9; border-radius:6px;'>%s</p>"
                % loc("knowledge_no_deficits",
                      "The network can currently represent, regulate and express "
                      "everything it has met. Nothing to grow."))
        for deficit in deficits:
            ready = deficit.key in actionable
            colour = "#c62828" if ready else "#ef6c00"
            bg = "#ffebee" if ready else "#fff8e1"
            if ready:
                status = "<b>%s</b>" % loc("knowledge_status_ready",
                                           "ready to grow structure")
            else:
                status = loc("knowledge_status_watching",
                             "watching — seen {observations} time(s) over {age}s",
                             observations=deficit.observations,
                             age=f"{deficit.age:.0f}")
                if not deficit.unresolved:
                    status += loc("knowledge_status_shrinking",
                                  "; ordinary learning is already shrinking it")
            parts.append(
                f"<div style='background:{bg}; border-left:5px solid {colour}; "
                f"margin:8px 2px; padding:10px 14px; border-radius:6px;'>"
                f"<div style='color:{colour};'><b>{deficit.kind}</b> — "
                + loc("knowledge_severity", "severity {severity}",
                      severity=f"{deficit.severity:.2f}") + "</div>"
                f"<div style='margin-top:4px; color:#222;'>{deficit.summary}</div>"
                f"<div style='margin-top:4px; color:#555; font-size:9.5pt;'>"
                + loc("knowledge_remedy", "A new neuron would: {remedy}",
                      remedy=deficit.remedy
                      or loc("knowledge_remedy_default", "remedy it")) + "</div>"
                f"<div style='margin-top:4px; color:{colour}; font-size:9pt;'>"
                f"{status}</div></div>")

        if engine is not None and hasattr(engine, 'growth_report'):
            try:
                report = engine.growth_report()
            except Exception:
                report = {}
            cooldown = report.get('cooldown_remaining', 0)
            if cooldown:
                parts.append("<p style='color:#607d8b;'>%s</p>" % loc(
                    "knowledge_cooldown", "Growth cooldown: {seconds}s remaining.",
                    seconds=f"{cooldown:.0f}"))
            stood_down = report.get('stood_down') or []
            if stood_down:
                parts.append("<h4 style='margin-bottom:2px;'>%s</h4><ul>" % loc(
                    "knowledge_stood_down", "Considered and stood down"))
                for row in stood_down:
                    parts.append(f"<li>{row['deficit']} — {row['because']}</li>")
                parts.append("</ul>")
            grown = report.get('grown') or []
            if grown:
                parts.append("<h4 style='margin-bottom:2px;'>%s</h4><ul>" % loc(
                    "knowledge_grown", "Structure grown so far"))
                for row in list(grown)[-8:]:
                    parts.append(f"<li><b>{row['neuron']}</b> ({row['deficit']}) — "
                                 f"{row['because']}</li>")
                parts.append("</ul>")

        parts.append("</body>")
        self.capability_view.setHtml("".join(parts))

    # ------------------------------------------------------------------
    def _export_knowledge(self):
        ledger = self.ledger
        if ledger is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, loc("knowledge_export_title", "Export what the squid knows"),
            "squid_knowledge.txt",
            loc("knowledge_export_filter", "Text files (*.txt)"))
        if not path:
            return
        try:
            items = ledger.knowledge(self._topic or None, limit=500)
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(loc("knowledge_export_head",
                                 "What this squid knows") + "\n")
                handle.write("=" * 60 + "\n\n")
                for item in items:
                    handle.write(item.describe())
                    handle.write("\n\n")
                handle.write("\n" + loc("knowledge_export_deficits",
                                        "What it cannot do yet") + "\n")
                handle.write("=" * 60 + "\n\n")
                monitor = self.capability
                if monitor is not None:
                    handle.write(monitor.describe())
                handle.write("\n")
            QtWidgets.QMessageBox.information(
                self, loc("knowledge_export_done_title", "Exported"),
                loc("knowledge_export_done", "Wrote {count} item(s) to {path}",
                    count=len(items), path=path))
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self, loc("knowledge_export_fail_title", "Export failed"), str(exc))
