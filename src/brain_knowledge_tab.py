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


_KIND_STYLE = {
    'association': ("#e3f2fd", "#1565c0", "association"),
    'contingency': ("#e8f5e9", "#2e7d32", "cause and effect"),
    'structure':   ("#fff3e0", "#e65100", "new structure"),
}


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

        self.tabs.addTab(self._build_knowledge_page(), "What it knows")
        self.tabs.addTab(self._build_weight_page(), "Why this weight?")
        self.tabs.addTab(self._build_neuron_page(), "Why this neuron?")
        self.tabs.addTab(self._build_capability_page(), "What it can't do yet")

        self.summary_label = QtWidgets.QLabel("")
        self.summary_label.setStyleSheet(
            f"color:#546e7a; font-size:{DisplayScaling.font_size(10)}pt; padding:4px;")
        self.layout.addWidget(self.summary_label)

    # -- page 1: knowledge ---------------------------------------------
    def _build_knowledge_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel("What does the squid know about"))
        self.topic_edit = QtWidgets.QLineEdit()
        self.topic_edit.setPlaceholderText("anything… try 'food', 'anxiety', 'plant'")
        self.topic_edit.textChanged.connect(self._on_topic_changed)
        controls.addWidget(self.topic_edit, 1)
        controls.addWidget(QtWidgets.QLabel("?"))

        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        controls.addWidget(refresh_btn)

        export_btn = QtWidgets.QPushButton("Export…")
        export_btn.setToolTip("Save everything the squid knows, in plain English")
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
        controls.addWidget(QtWidgets.QLabel("Synapse:"))
        self.edge_combo = QtWidgets.QComboBox()
        self.edge_combo.setMinimumWidth(DisplayScaling.scale(320))
        self.edge_combo.currentIndexChanged.connect(self._show_weight_explanation)
        controls.addWidget(self.edge_combo, 1)
        layout.addLayout(controls)

        self.weight_view = QtWidgets.QTextBrowser()
        layout.addWidget(self.weight_view, 1)

        self.weight_table = QtWidgets.QTableWidget(0, 6)
        self.weight_table.setHorizontalHeaderLabels(
            ["When", "From", "To", "Change", "Mechanism", "Evidence"])
        self.weight_table.horizontalHeader().setStretchLastSection(True)
        self.weight_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.weight_table, 1)
        return page

    # -- page 3: neuron provenance -------------------------------------
    def _build_neuron_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel("Neuron:"))
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

        blurb = QtWidgets.QLabel(
            "A neuron is grown when the network has a persistent functional "
            "deficiency it cannot fix with the structure it already has - not "
            "because a particular event happened. This is that diagnosis, live.")
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
            self.summary_label.setText("This brain keeps no provenance.")
            return
        s = ledger.summary()
        causal = self.causal
        contingencies = 0
        if causal is not None:
            try:
                contingencies = len(causal.known_contingencies())
            except Exception:
                contingencies = 0
        self.summary_label.setText(
            f"{s['weight_changes']} recorded synaptic changes across "
            f"{s['tracked_synapses']} synapses · {s['neurons_grown']} neurons grown, "
            f"{s['neurons_pruned']} pruned · {s['episodes']} experiences remembered · "
            f"{contingencies} things it has worked out about its own actions")

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
            self.knowledge_view.setHtml("<p>This brain keeps no provenance.</p>")
            return
        try:
            items = ledger.knowledge(self._topic or None)
        except Exception as exc:
            self.knowledge_view.setHtml(f"<p>Could not read the ledger: {exc}</p>")
            return

        if not items:
            if self._topic:
                self.knowledge_view.setHtml(
                    f"<p style='padding:20px;'>The squid has not learned anything "
                    f"about <b>{self._topic}</b> yet. Everything it knows comes "
                    f"from experience, so give it some.</p>")
            else:
                self.knowledge_view.setHtml(
                    "<p style='padding:20px;'>The squid has not learned anything "
                    "yet. Its synapses are still the ones it was born with.</p>")
            return

        self.knowledge_view.setHtml(self._render_items(items))

    def _render_items(self, items) -> str:
        parts = ["<body style='font-family:sans-serif;'>"]
        for item in items:
            bg, colour, kind_label = _KIND_STYLE.get(
                item.kind, ("#f5f5f5", "#424242", item.kind))
            rows = []
            if item.experience:
                rows.append(("What experience caused it", item.experience))
            if item.action:
                rows.append(("Which action was involved", humanise(item.action)))
            if item.consequence:
                rows.append(("What consequence followed", item.consequence))
            if item.reason:
                rows.append(("Why the connection changed", item.reason))
            if item.behaviour:
                rows.append(("How it affected behaviour", item.behaviour))

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
                f"confidence {item.confidence:.0%} {_confidence_bar(item.confidence, colour)} "
                f"&nbsp;·&nbsp; strength {item.strength:+.2f}</div>"
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
            text = f"Could not explain this synapse: {exc}"
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
                evidence.append(f"after it {humanise(ep.action)}")

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
            self.neuron_view.setPlainText(f"Could not explain this neuron: {exc}")

    # ------------------------------------------------------------------
    def _refresh_capability(self):
        monitor = self.capability
        engine = getattr(self.brain_widget, 'enhanced_neurogenesis', None)
        if monitor is None:
            self.capability_view.setHtml("<p>This brain has no capability monitor.</p>")
            return

        parts = ["<body style='font-family:sans-serif;'>"]
        try:
            deficits = sorted(monitor.active.values(), key=lambda d: -d.severity)
            actionable = {d.key for d in monitor.actionable()}
        except Exception as exc:
            self.capability_view.setHtml(f"<p>Could not read the monitor: {exc}</p>")
            return

        if not deficits:
            parts.append(
                "<p style='padding:14px; background:#e8f5e9; border-radius:6px;'>"
                "The network can currently represent, regulate and express "
                "everything it has met. Nothing to grow.</p>")
        for deficit in deficits:
            ready = deficit.key in actionable
            colour = "#c62828" if ready else "#ef6c00"
            bg = "#ffebee" if ready else "#fff8e1"
            status = ("<b>ready to grow structure</b>" if ready else
                      f"watching — seen {deficit.observations} time(s) over "
                      f"{deficit.age:.0f}s"
                      + ("" if deficit.unresolved else
                         "; ordinary learning is already shrinking it"))
            parts.append(
                f"<div style='background:{bg}; border-left:5px solid {colour}; "
                f"margin:8px 2px; padding:10px 14px; border-radius:6px;'>"
                f"<div style='color:{colour};'><b>{deficit.kind}</b> — severity "
                f"{deficit.severity:.2f}</div>"
                f"<div style='margin-top:4px; color:#222;'>{deficit.summary}</div>"
                f"<div style='margin-top:4px; color:#555; font-size:9.5pt;'>"
                f"A new neuron would: {deficit.remedy or 'remedy it'}</div>"
                f"<div style='margin-top:4px; color:{colour}; font-size:9pt;'>"
                f"{status}</div></div>")

        if engine is not None and hasattr(engine, 'growth_report'):
            try:
                report = engine.growth_report()
            except Exception:
                report = {}
            cooldown = report.get('cooldown_remaining', 0)
            if cooldown:
                parts.append(f"<p style='color:#607d8b;'>Growth cooldown: "
                             f"{cooldown:.0f}s remaining.</p>")
            stood_down = report.get('stood_down') or []
            if stood_down:
                parts.append("<h4 style='margin-bottom:2px;'>Considered and stood down</h4><ul>")
                for row in stood_down:
                    parts.append(f"<li>{row['deficit']} — {row['because']}</li>")
                parts.append("</ul>")
            grown = report.get('grown') or []
            if grown:
                parts.append("<h4 style='margin-bottom:2px;'>Structure grown so far</h4><ul>")
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
            self, "Export what the squid knows", "squid_knowledge.txt",
            "Text files (*.txt)")
        if not path:
            return
        try:
            items = ledger.knowledge(self._topic or None, limit=500)
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write("What this squid knows\n")
                handle.write("=" * 60 + "\n\n")
                for item in items:
                    handle.write(item.describe())
                    handle.write("\n\n")
                handle.write("\nWhat it cannot do yet\n")
                handle.write("=" * 60 + "\n\n")
                monitor = self.capability
                if monitor is not None:
                    handle.write(monitor.describe())
                handle.write("\n")
            QtWidgets.QMessageBox.information(
                self, "Exported", f"Wrote {len(items)} item(s) to {path}")
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Export failed", str(exc))
