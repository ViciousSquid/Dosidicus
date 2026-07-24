# src/brain_decisions_tab.py
#
# Graphical "Decisions" tab.
#
# Instead of a wall of text, this tab visualises *what* the squid decided and
# *how* that decision was reached:
#
#   • Winner banner  – the chosen action + the behaviour it produced.
#   • Confidence gauge – how clear-cut the winner was over the runner-up.
#   • Candidate bars – every action the engine scored, drawn as ranked bars
#     with a "ghost" marker showing the base (pre-modifier) score, so the
#     effect of memory / urgency / personality is visible at a glance.
#   • Scoring pipeline – for the winning action, the multiplicative chain
#     Base ×Memory ×(Personality & chance) → Final.
#   • Drive meters – the internal needs feeding the scores, plus which objects
#     the squid can currently perceive.
#   • Recent decisions – a colour-coded timeline of the last several choices.
#
# Data is read from the live DecisionEngine trace
# (squid._decision_engine.get_decision_data()) and falls back to
# TamagotchiLogic.get_decision_data() so it keeps working with older saves.

import math
from collections import deque

from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .display_scaling import DisplayScaling
from .localisation import Localisation


# --------------------------------------------------------------------------- #
# Palette / action metadata
# --------------------------------------------------------------------------- #

PAGE_BG      = QtGui.QColor("#f4f6f9")
CARD_BG      = QtGui.QColor("#ffffff")
CARD_BORDER  = QtGui.QColor("#e3e8ef")
TEXT_MAIN    = QtGui.QColor("#2b3440")
TEXT_MUTED   = QtGui.QColor("#7a8794")
TRACK_BG     = QtGui.QColor("#eef1f5")
GHOST_COLOR  = QtGui.QColor("#c3ccd6")
GOOD_COLOR   = QtGui.QColor("#22b06b")
BAD_COLOR    = QtGui.QColor("#e5533c")
NEUTRAL_MULT = QtGui.QColor("#9aa6b2")

# action_key -> (emoji, base RGB colour)
ACTION_META = {
    "exploring":         ("🧭", (59, 130, 246)),
    "eating":            ("🍽️", (245, 130, 32)),
    "approaching_plant": ("🌿", (34, 177, 96)),
    "approaching_rock":  ("🪨", (120, 144, 156)),
    "playing":           ("🎾", (155, 89, 232)),
    "throwing":          ("🎯", (233, 84, 158)),
    "throwing_rock":     ("🎯", (233, 84, 158)),
    "sleeping":          ("😴", (99, 102, 241)),
    "fleeing":           ("💨", (239, 68, 68)),
    "avoiding_threat":   ("🛡️", (239, 68, 68)),
    "organizing":        ("🧹", (20, 184, 166)),
}

# Drives shown as meters:  key -> (label, RGB)
DRIVE_META = [
    ("hunger",       ("Hunger",       (245, 130, 32))),
    ("sleepiness",   ("Sleepiness",   (99, 102, 241))),
    ("anxiety",      ("Anxiety",      (229, 83, 60))),
    ("curiosity",    ("Curiosity",    (59, 130, 246))),
    ("satisfaction", ("Satisfaction", (34, 177, 96))),
    ("happiness",    ("Happiness",    (250, 190, 40))),
    ("cleanliness",  ("Cleanliness",  (20, 184, 166))),
]


def _action_color(name):
    key = str(name).lower().replace(" ", "_")
    if key in ACTION_META:
        r, g, b = ACTION_META[key][1]
        return QtGui.QColor(r, g, b)
    # Stable pseudo-random hue for any unknown / outcome string
    h = (abs(hash(key)) % 360) / 360.0
    col = QtGui.QColor()
    col.setHsvF(h, 0.55, 0.85)
    return col


def _action_emoji(name):
    key = str(name).lower().replace(" ", "_")
    if key in ACTION_META:
        return ACTION_META[key][0]
    # Map common outcome strings back to a sensible glyph
    s = str(name).lower()
    for token, emoji in (("food", "🍽️"), ("eat", "🍽️"), ("plant", "🌿"),
                         ("sleep", "😴"), ("flee", "💨"), ("startl", "❗"),
                         ("rock", "🪨"), ("poop", "💩"), ("toy", "🎾"),
                         ("explor", "🧭"), ("wander", "🧭")):
        if token in s:
            return emoji
    return "🐙"


def _pretty(name):
    return str(name).replace("_", " ").strip().capitalize()


def _lerp(a, b, t):
    return a + (b - a) * t


def _lerp_color(c1, c2, t):
    return QtGui.QColor(
        int(_lerp(c1.red(), c2.red(), t)),
        int(_lerp(c1.green(), c2.green(), t)),
        int(_lerp(c1.blue(), c2.blue(), t)),
    )


def _confidence_color(conf):
    """Red (torn) → amber → green (decisive)."""
    conf = max(0.0, min(1.0, conf))
    if conf < 0.5:
        return _lerp_color(QtGui.QColor("#e5533c"), QtGui.QColor("#f0ad4e"), conf / 0.5)
    return _lerp_color(QtGui.QColor("#f0ad4e"), QtGui.QColor("#22b06b"), (conf - 0.5) / 0.5)


def _confidence_label(conf):
    if conf < 0.12:
        return "Torn"
    if conf < 0.32:
        return "Leaning"
    if conf < 0.6:
        return "Fairly sure"
    if conf < 0.85:
        return "Confident"
    return "Decisive"


def _card(painter, rect, radius=None):
    """Draw the standard rounded card background+border into rect."""
    if radius is None:
        radius = DisplayScaling.scale(10)
    painter.setPen(QtGui.QPen(CARD_BORDER, 1))
    painter.setBrush(CARD_BG)
    painter.drawRoundedRect(rect, radius, radius)


# --------------------------------------------------------------------------- #
# Confidence gauge
# --------------------------------------------------------------------------- #

class ConfidenceGauge(QtWidgets.QWidget):
    """A semicircular arc gauge for decision confidence (0..1)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target = 0.0
        self._value = 0.0
        self.setMinimumHeight(DisplayScaling.scale(150))
        self.setMinimumWidth(DisplayScaling.scale(200))
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_value(self, conf):
        self._target = max(0.0, min(1.0, float(conf)))
        if not self._timer.isActive():
            self._timer.start(16)

    def _tick(self):
        self._value = _lerp(self._value, self._target, 0.2)
        if abs(self._value - self._target) < 0.004:
            self._value = self._target
            self._timer.stop()
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        w, h = self.width(), self.height()
        margin = DisplayScaling.scale(18)
        thickness = DisplayScaling.scale(16)
        diameter = min(w - 2 * margin, (h - 2 * margin) * 2)
        arc_rect = QtCore.QRectF(
            (w - diameter) / 2.0,
            h - margin - diameter / 2.0 - DisplayScaling.scale(6),
            diameter, diameter
        )

        start_angle = 200 * 16      # sweeps 200° down to -20°
        span = -220 * 16

        # Background arc
        pen = QtGui.QPen(TRACK_BG, thickness, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(arc_rect, start_angle, span)

        # Value arc
        col = _confidence_color(self._value)
        pen = QtGui.QPen(col, thickness, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(arc_rect, start_angle, int(span * self._value))

        # Percentage
        center = arc_rect.center()
        p.setPen(TEXT_MAIN)
        f = self.font()
        f.setBold(True)
        f.setPixelSize(DisplayScaling.font_size(30))
        p.setFont(f)
        pct_rect = QtCore.QRectF(arc_rect.left(), center.y() - DisplayScaling.scale(30),
                                 arc_rect.width(), DisplayScaling.scale(40))
        p.drawText(pct_rect, QtCore.Qt.AlignCenter, f"{int(round(self._value * 100))}%")

        # Label
        p.setPen(col)
        f2 = self.font()
        f2.setBold(True)
        f2.setPixelSize(DisplayScaling.font_size(15))
        p.setFont(f2)
        lbl_rect = QtCore.QRectF(arc_rect.left(), center.y() + DisplayScaling.scale(2),
                                 arc_rect.width(), DisplayScaling.scale(24))
        p.drawText(lbl_rect, QtCore.Qt.AlignCenter, _confidence_label(self._value))
        p.end()


# --------------------------------------------------------------------------- #
# Candidate action bars
# --------------------------------------------------------------------------- #

class ActionRanksWidget(QtWidgets.QWidget):
    """Ranked horizontal bars for every scored action.

    Each row shows the final (adjusted) score as a filled bar and the base
    (pre-modifier) score as a faint 'ghost' tick, so the influence of memory /
    urgency / personality is directly visible. The winning action is ringed.
    """

    ROW_H = 46
    ROW_GAP = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []          # list of dicts: name, base, final, cur, winner
        self._winner = None
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_data(self, base_weights, adjusted_weights, winner):
        adjusted_weights = adjusted_weights or {}
        base_weights = base_weights or {}
        # Union of actions, sorted by final score descending
        names = list(adjusted_weights.keys()) or list(base_weights.keys())
        names = sorted(set(names), key=lambda n: adjusted_weights.get(n, base_weights.get(n, 0)), reverse=True)

        prev = {r["name"]: r["cur"] for r in self._rows}
        rows = []
        for n in names:
            rows.append({
                "name": n,
                "base": float(base_weights.get(n, adjusted_weights.get(n, 0.0)) or 0.0),
                "final": float(adjusted_weights.get(n, 0.0) or 0.0),
                "cur": prev.get(n, 0.0),
                "winner": (n == winner),
            })
        self._rows = rows
        self._winner = winner
        self.setMinimumHeight(self._content_height())
        if not self._timer.isActive():
            self._timer.start(16)

    def _content_height(self):
        n = max(1, len(self._rows))
        return DisplayScaling.scale(self.ROW_H * n + self.ROW_GAP * (n - 1) + 8)

    def sizeHint(self):
        return QtCore.QSize(DisplayScaling.scale(400), self._content_height())

    def _tick(self):
        done = True
        for r in self._rows:
            r["cur"] = _lerp(r["cur"], r["final"], 0.2)
            if abs(r["cur"] - r["final"]) > 0.5:
                done = False
        if done:
            for r in self._rows:
                r["cur"] = r["final"]
            self._timer.stop()
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        if not self._rows:
            p.setPen(TEXT_MUTED)
            f = self.font(); f.setPixelSize(DisplayScaling.font_size(14)); p.setFont(f)
            p.drawText(self.rect(), QtCore.Qt.AlignCenter, "Awaiting the first decision…")
            p.end()
            return

        row_h = DisplayScaling.scale(self.ROW_H)
        gap = DisplayScaling.scale(self.ROW_GAP)
        label_w = DisplayScaling.scale(150)
        score_w = DisplayScaling.scale(64)
        left = DisplayScaling.scale(4)
        bar_x = left + label_w + DisplayScaling.scale(8)
        bar_w = max(DisplayScaling.scale(40), self.width() - bar_x - score_w - DisplayScaling.scale(8))

        max_final = max((r["final"] for r in self._rows), default=1.0) or 1.0

        y = DisplayScaling.scale(4)
        swatch = DisplayScaling.scale(12)
        for r in self._rows:
            col = _action_color(r["name"])
            cy = y + row_h / 2.0

            # Winner highlight background
            if r["winner"]:
                hl = QtGui.QColor(col); hl.setAlpha(28)
                p.setPen(QtCore.Qt.NoPen); p.setBrush(hl)
                p.drawRoundedRect(QtCore.QRectF(left - DisplayScaling.scale(2), y,
                                                self.width() - left, row_h),
                                  DisplayScaling.scale(8), DisplayScaling.scale(8))

            # Colour swatch + label
            p.setPen(QtCore.Qt.NoPen); p.setBrush(col)
            p.drawEllipse(QtCore.QRectF(left, cy - swatch / 2.0, swatch, swatch))

            p.setPen(TEXT_MAIN)
            f = self.font()
            f.setBold(r["winner"])
            f.setPixelSize(DisplayScaling.font_size(14))
            p.setFont(f)
            lbl_rect = QtCore.QRectF(left + swatch + DisplayScaling.scale(8), y,
                                     label_w - swatch, row_h)
            p.drawText(lbl_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
                       _pretty(r["name"]))

            # Bar track
            bar_h = DisplayScaling.scale(18)
            track = QtCore.QRectF(bar_x, cy - bar_h / 2.0, bar_w, bar_h)
            p.setPen(QtCore.Qt.NoPen); p.setBrush(TRACK_BG)
            p.drawRoundedRect(track, bar_h / 2.0, bar_h / 2.0)

            # Filled bar (animated)
            frac = max(0.0, min(1.0, r["cur"] / max_final))
            fill_w = bar_w * frac
            if fill_w > 1:
                grad = QtGui.QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
                grad.setColorAt(0.0, col.lighter(112))
                grad.setColorAt(1.0, col)
                p.setBrush(QtGui.QBrush(grad))
                fill = QtCore.QRectF(bar_x, cy - bar_h / 2.0, max(bar_h, fill_w), bar_h)
                p.drawRoundedRect(fill, bar_h / 2.0, bar_h / 2.0)

            # Ghost marker for base score
            if max_final > 0 and r["base"] > 0:
                gx = bar_x + bar_w * max(0.0, min(1.0, r["base"] / max_final))
                p.setPen(QtGui.QPen(GHOST_COLOR, DisplayScaling.scale(2)))
                p.drawLine(QtCore.QPointF(gx, cy - bar_h / 2.0 - DisplayScaling.scale(3)),
                           QtCore.QPointF(gx, cy + bar_h / 2.0 + DisplayScaling.scale(3)))

            # Winner ring / check
            if r["winner"]:
                p.setPen(QtGui.QPen(col, DisplayScaling.scale(2)))
                p.setBrush(QtCore.Qt.NoBrush)
                p.drawRoundedRect(track.adjusted(-DisplayScaling.scale(2), -DisplayScaling.scale(3),
                                                 DisplayScaling.scale(2), DisplayScaling.scale(3)),
                                  bar_h / 2.0 + 2, bar_h / 2.0 + 2)

            # Score value
            p.setPen(TEXT_MUTED if not r["winner"] else col)
            f2 = self.font()
            f2.setBold(r["winner"])
            f2.setPixelSize(DisplayScaling.font_size(13))
            p.setFont(f2)
            sc_rect = QtCore.QRectF(bar_x + bar_w + DisplayScaling.scale(6), y, score_w, row_h)
            p.drawText(sc_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight,
                       f"{r['final']:.1f}")

            y += row_h + gap
        p.end()


# --------------------------------------------------------------------------- #
# Winner scoring pipeline
# --------------------------------------------------------------------------- #

class PipelineWidget(QtWidgets.QWidget):
    """Shows Base ×Memory ×(Personality & chance) → Final for the winner."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stages = []   # list of (kind, label, value)  kind in {'value','mult'}
        self._title = ""
        self.setMinimumHeight(DisplayScaling.scale(96))

    def set_data(self, action, base, final, memory_mult):
        self._stages = []
        self._title = ""
        if action is None:
            self.update()
            return
        self._title = _pretty(action)
        base = float(base or 0.0)
        final = float(final or 0.0)
        memory_mult = float(memory_mult if memory_mult else 1.0)

        stages = [("value", "Base drive", base)]
        if abs(memory_mult - 1.0) > 0.02:
            stages.append(("mult", "Memory", memory_mult))
        # Everything else (personality + random jitter) folded into a residual
        residual = 1.0
        if base > 0:
            residual = final / (base * memory_mult) if (base * memory_mult) else 1.0
        if abs(residual - 1.0) > 0.02:
            stages.append(("mult", "Personality & chance", residual))
        stages.append(("value", "Final score", final))
        self._stages = stages
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        if not self._stages:
            p.setPen(TEXT_MUTED)
            f = self.font(); f.setPixelSize(DisplayScaling.font_size(13)); p.setFont(f)
            p.drawText(self.rect(), QtCore.Qt.AlignCenter, "No scored winner to break down.")
            p.end()
            return

        pad = DisplayScaling.scale(6)
        gap = DisplayScaling.scale(6)
        n = len(self._stages)
        total_w = self.width() - 2 * pad
        box_w = (total_w - gap * (n - 1)) / n
        box_h = DisplayScaling.scale(64)
        y = (self.height() - box_h) / 2.0
        x = pad

        for i, (kind, label, value) in enumerate(self._stages):
            rect = QtCore.QRectF(x, y, box_w, box_h)
            if kind == "value":
                p.setPen(QtGui.QPen(CARD_BORDER, 1))
                p.setBrush(QtGui.QColor("#f7f9fc"))
                p.drawRoundedRect(rect, DisplayScaling.scale(8), DisplayScaling.scale(8))
                p.setPen(TEXT_MUTED)
                f = self.font(); f.setPixelSize(DisplayScaling.font_size(11)); p.setFont(f)
                p.drawText(QtCore.QRectF(rect.left(), rect.top() + DisplayScaling.scale(8),
                                         rect.width(), DisplayScaling.scale(16)),
                           QtCore.Qt.AlignCenter, label)
                p.setPen(TEXT_MAIN)
                f.setBold(True); f.setPixelSize(DisplayScaling.font_size(20)); p.setFont(f)
                p.drawText(QtCore.QRectF(rect.left(), rect.top() + DisplayScaling.scale(24),
                                         rect.width(), DisplayScaling.scale(32)),
                           QtCore.Qt.AlignCenter, f"{value:.1f}")
            else:  # multiplier chip
                if value > 1.02:
                    c = GOOD_COLOR
                elif value < 0.98:
                    c = BAD_COLOR
                else:
                    c = NEUTRAL_MULT
                chip = QtGui.QColor(c); chip.setAlpha(30)
                p.setPen(QtGui.QPen(c, DisplayScaling.scale(1.5)))
                p.setBrush(chip)
                p.drawRoundedRect(rect, DisplayScaling.scale(8), DisplayScaling.scale(8))
                p.setPen(TEXT_MUTED)
                f = self.font(); f.setPixelSize(DisplayScaling.font_size(11)); p.setFont(f)
                p.drawText(QtCore.QRectF(rect.left(), rect.top() + DisplayScaling.scale(8),
                                         rect.width(), DisplayScaling.scale(16)),
                           QtCore.Qt.AlignCenter, label)
                p.setPen(c)
                f.setBold(True); f.setPixelSize(DisplayScaling.font_size(18)); p.setFont(f)
                p.drawText(QtCore.QRectF(rect.left(), rect.top() + DisplayScaling.scale(24),
                                         rect.width(), DisplayScaling.scale(32)),
                           QtCore.Qt.AlignCenter, f"×{value:.2f}")

            # Operator between boxes
            if i < n - 1:
                op = "×" if self._stages[i + 1][0] == "mult" else "="
                # '=' only makes sense before the final value box
                if self._stages[i + 1][0] == "value":
                    op = "="
                p.setPen(TEXT_MUTED)
                f = self.font(); f.setBold(True); f.setPixelSize(DisplayScaling.font_size(16)); p.setFont(f)
                op_rect = QtCore.QRectF(x + box_w, y, gap, box_h)
                p.drawText(op_rect, QtCore.Qt.AlignCenter, op)
            x += box_w + gap
        p.end()


# --------------------------------------------------------------------------- #
# Drive meters + perception chips
# --------------------------------------------------------------------------- #

class DriveMetersWidget(QtWidgets.QWidget):
    """Horizontal 0-100 meters for the internal needs, plus perception chips."""

    ROW_H = 26

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values = {}      # key -> target 0..100
        self._cur = {}         # key -> animated
        self._perception = {}  # label -> bool
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_data(self, drive_values, perception):
        self._values = {k: float(v) for k, v in (drive_values or {}).items()}
        self._perception = perception or {}
        for k in self._values:
            self._cur.setdefault(k, 0.0)
        self.setMinimumHeight(self._content_height())
        if not self._timer.isActive():
            self._timer.start(16)
        self.update()

    def _content_height(self):
        rows = len(DRIVE_META)
        return DisplayScaling.scale(self.ROW_H * rows + 74)

    def sizeHint(self):
        return QtCore.QSize(DisplayScaling.scale(300), self._content_height())

    def _tick(self):
        done = True
        for k, tgt in self._values.items():
            cur = self._cur.get(k, 0.0)
            cur = _lerp(cur, tgt, 0.2)
            if abs(cur - tgt) > 0.3:
                done = False
            self._cur[k] = cur
        if done:
            for k, tgt in self._values.items():
                self._cur[k] = tgt
            self._timer.stop()
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        row_h = DisplayScaling.scale(self.ROW_H)
        label_w = DisplayScaling.scale(96)
        val_w = DisplayScaling.scale(38)
        left = DisplayScaling.scale(2)
        bar_x = left + label_w
        bar_w = max(DisplayScaling.scale(40), self.width() - bar_x - val_w - DisplayScaling.scale(4))
        bar_h = DisplayScaling.scale(12)

        f = self.font(); f.setPixelSize(DisplayScaling.font_size(12)); p.setFont(f)
        y = DisplayScaling.scale(2)
        for key, (label, rgb) in DRIVE_META:
            if key not in self._values:
                continue
            col = QtGui.QColor(*rgb)
            cy = y + row_h / 2.0
            p.setPen(TEXT_MAIN)
            p.drawText(QtCore.QRectF(left, y, label_w - DisplayScaling.scale(6), row_h),
                       QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, label)

            track = QtCore.QRectF(bar_x, cy - bar_h / 2.0, bar_w, bar_h)
            p.setPen(QtCore.Qt.NoPen); p.setBrush(TRACK_BG)
            p.drawRoundedRect(track, bar_h / 2.0, bar_h / 2.0)

            val = max(0.0, min(100.0, self._cur.get(key, 0.0)))
            fw = bar_w * (val / 100.0)
            if fw > 1:
                p.setBrush(col)
                p.drawRoundedRect(QtCore.QRectF(bar_x, cy - bar_h / 2.0, max(bar_h, fw), bar_h),
                                  bar_h / 2.0, bar_h / 2.0)

            p.setPen(TEXT_MUTED)
            p.drawText(QtCore.QRectF(bar_x + bar_w + DisplayScaling.scale(4), y, val_w, row_h),
                       QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight,
                       f"{int(round(self._values.get(key, 0.0)))}")
            y += row_h

        # Perception chips
        y += DisplayScaling.scale(8)
        p.setPen(TEXT_MUTED)
        fh = self.font(); fh.setPixelSize(DisplayScaling.font_size(11)); fh.setBold(True); p.setFont(fh)
        p.drawText(QtCore.QRectF(left, y, self.width(), DisplayScaling.scale(16)),
                   QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, "CAN SEE")
        y += DisplayScaling.scale(20)

        chip_x = left
        chip_h = DisplayScaling.scale(22)
        fc = self.font(); fc.setBold(False); fc.setPixelSize(DisplayScaling.font_size(12)); p.setFont(fc)
        for label, on in self._perception.items():
            text = f"{label}"
            tw = QtGui.QFontMetrics(fc).width(text) + DisplayScaling.scale(22)
            rect = QtCore.QRectF(chip_x, y, tw, chip_h)
            if on:
                base = _action_color(label if label.lower() != "food" else "eating")
                fillc = QtGui.QColor(base); fillc.setAlpha(38)
                p.setPen(QtGui.QPen(base, 1)); p.setBrush(fillc)
                txt_col = base.darker(120)
            else:
                p.setPen(QtGui.QPen(CARD_BORDER, 1)); p.setBrush(QtGui.QColor("#f2f4f7"))
                txt_col = TEXT_MUTED
            p.drawRoundedRect(rect, chip_h / 2.0, chip_h / 2.0)
            # dot
            dot = DisplayScaling.scale(8)
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(_action_color(label if label.lower() != "food" else "eating") if on else GHOST_COLOR)
            p.drawEllipse(QtCore.QRectF(rect.left() + DisplayScaling.scale(7),
                                        rect.center().y() - dot / 2.0, dot, dot))
            p.setPen(txt_col)
            p.drawText(QtCore.QRectF(rect.left() + DisplayScaling.scale(18), rect.top(),
                                     rect.width() - DisplayScaling.scale(18), rect.height()),
                       QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, text)
            chip_x += tw + DisplayScaling.scale(8)
        p.end()


# --------------------------------------------------------------------------- #
# Recent decisions timeline
# --------------------------------------------------------------------------- #

class DecisionHistoryWidget(QtWidgets.QWidget):
    """Colour-coded blocks for the last N decisions, height = confidence."""

    MAX = 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = deque(maxlen=self.MAX)   # (action, confidence)
        self.setMinimumHeight(DisplayScaling.scale(74))

    def push(self, action, confidence):
        self._items.append((action, max(0.0, min(1.0, float(confidence)))))
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        if not self._items:
            p.setPen(TEXT_MUTED)
            f = self.font(); f.setPixelSize(DisplayScaling.font_size(12)); p.setFont(f)
            p.drawText(self.rect(), QtCore.Qt.AlignCenter, "No decisions recorded yet.")
            p.end()
            return

        left = DisplayScaling.scale(4)
        right = DisplayScaling.scale(4)
        bottom = DisplayScaling.scale(20)
        top = DisplayScaling.scale(6)
        avail_w = self.width() - left - right
        n = len(self._items)
        gap = DisplayScaling.scale(4)
        block_w = max(DisplayScaling.scale(8), (avail_w - gap * (n - 1)) / n)
        max_h = self.height() - top - bottom

        x = left
        for i, (action, conf) in enumerate(self._items):
            col = _action_color(action)
            h = max(DisplayScaling.scale(6), max_h * (0.35 + 0.65 * conf))
            rect = QtCore.QRectF(x, top + (max_h - h), block_w, h)
            newest = (i == n - 1)
            fill = QtGui.QColor(col)
            if not newest:
                fill.setAlpha(150)
            p.setPen(QtGui.QPen(col.darker(115), DisplayScaling.scale(2)) if newest else QtCore.Qt.NoPen)
            p.setBrush(fill)
            p.drawRoundedRect(rect, DisplayScaling.scale(3), DisplayScaling.scale(3))
            x += block_w + gap

        # Caption: newest action name
        p.setPen(TEXT_MUTED)
        f = self.font(); f.setPixelSize(DisplayScaling.font_size(11)); p.setFont(f)
        latest = self._items[-1][0]
        p.drawText(QtCore.QRectF(left, self.height() - bottom, avail_w, bottom),
                   QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
                   f"latest → {_pretty(latest)}   (oldest … newest)")
        p.end()


# --------------------------------------------------------------------------- #
# Main tab
# --------------------------------------------------------------------------- #

class DecisionsTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        self.loc = Localisation.instance()
        self._last_sig = None
        self.initialize_ui()

    # -- helpers for consistent card sections ----------------------------- #

    def _section(self, title, subtitle=None):
        card = QtWidgets.QFrame()
        card.setObjectName("sectionCard")
        card.setStyleSheet(
            "#sectionCard { background-color: #ffffff; border: 1px solid #e3e8ef;"
            f" border-radius: {DisplayScaling.scale(10)}px; }}"
        )
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(DisplayScaling.scale(14), DisplayScaling.scale(12),
                               DisplayScaling.scale(14), DisplayScaling.scale(12))
        lay.setSpacing(DisplayScaling.scale(8))
        header = QtWidgets.QLabel(title)
        header.setStyleSheet(
            f"font-size: {DisplayScaling.font_size(15)}px; font-weight: bold; color: #2b3440;"
        )
        lay.addWidget(header)
        if subtitle:
            sub = QtWidgets.QLabel(subtitle)
            sub.setWordWrap(True)
            sub.setStyleSheet(f"font-size: {DisplayScaling.font_size(11)}px; color: #7a8794;")
            lay.addWidget(sub)
        return card, lay

    def initialize_ui(self):
        self.layout.setContentsMargins(DisplayScaling.scale(10), DisplayScaling.scale(10),
                                       DisplayScaling.scale(10), DisplayScaling.scale(10))
        self.layout.setSpacing(0)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #f4f6f9; }")
        self.layout.addWidget(scroll)

        container = QtWidgets.QWidget()
        container.setStyleSheet("background-color: #f4f6f9;")
        root = QtWidgets.QVBoxLayout(container)
        root.setContentsMargins(DisplayScaling.scale(6), DisplayScaling.scale(6),
                                DisplayScaling.scale(6), DisplayScaling.scale(6))
        root.setSpacing(DisplayScaling.scale(12))
        scroll.setWidget(container)

        # ---- Title row ----
        title_row = QtWidgets.QHBoxLayout()
        icon = QtWidgets.QLabel("🧠")
        icon.setStyleSheet(f"font-size: {DisplayScaling.font_size(26)}px;")
        title = QtWidgets.QLabel(self.loc.get("thought_process", "How the squid decides"))
        title.setStyleSheet(
            f"font-size: {DisplayScaling.font_size(22)}px; font-weight: bold; color: #2b3440;"
        )
        self.personality_badge = QtWidgets.QLabel("")
        self.personality_badge.setStyleSheet(
            f"font-size: {DisplayScaling.font_size(12)}px; font-weight: bold; color: #ffffff;"
            f" background-color: #6c7a89; border-radius: {DisplayScaling.scale(10)}px;"
            f" padding: {DisplayScaling.scale(4)}px {DisplayScaling.scale(10)}px;"
        )
        title_row.addWidget(icon)
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.personality_badge)
        root.addLayout(title_row)

        # ---- Winner banner + confidence ----
        top_row = QtWidgets.QHBoxLayout()
        top_row.setSpacing(DisplayScaling.scale(12))

        banner_card, banner_lay = self._section(self.loc.get("final_action", "Decision"))
        self.winner_emoji = QtWidgets.QLabel("🐙")
        self.winner_emoji.setAlignment(QtCore.Qt.AlignCenter)
        self.winner_emoji.setStyleSheet(f"font-size: {DisplayScaling.font_size(46)}px;")
        self.winner_action = QtWidgets.QLabel("…")
        self.winner_action.setStyleSheet(
            f"font-size: {DisplayScaling.font_size(26)}px; font-weight: bold; color: #2f6bff;"
        )
        self.winner_behaviour = QtWidgets.QLabel("Awaiting the first decision…")
        self.winner_behaviour.setWordWrap(True)
        self.winner_behaviour.setStyleSheet(
            f"font-size: {DisplayScaling.font_size(13)}px; color: #7a8794;"
        )
        emoji_row = QtWidgets.QHBoxLayout()
        emoji_row.addWidget(self.winner_emoji)
        text_col = QtWidgets.QVBoxLayout()
        text_col.setSpacing(DisplayScaling.scale(2))
        text_col.addWidget(self.winner_action)
        text_col.addWidget(self.winner_behaviour)
        emoji_row.addLayout(text_col, 1)
        banner_lay.addLayout(emoji_row)
        top_row.addWidget(banner_card, 3)

        gauge_card, gauge_lay = self._section(self.loc.get("confidence", "Confidence"))
        self.gauge = ConfidenceGauge()
        gauge_lay.addWidget(self.gauge)
        top_row.addWidget(gauge_card, 2)
        root.addLayout(top_row)

        # ---- Candidate action bars ----
        bars_card, bars_lay = self._section(
            "Candidate actions",
            "Every action the engine scored this tick. Bar = final score; the faint "
            "tick shows the base score before memory / urgency / personality."
        )
        self.action_bars = ActionRanksWidget()
        bars_lay.addWidget(self.action_bars)
        root.addWidget(bars_card)

        # ---- Winner pipeline ----
        pipe_card, pipe_lay = self._section(
            "How the winner was scored",
            "The winning action's score, from base drive to final."
        )
        self.pipeline = PipelineWidget()
        pipe_lay.addWidget(self.pipeline)
        root.addWidget(pipe_card)

        # ---- Drives + perception ----
        drive_card, drive_lay = self._section(
            "Current drives & perception",
            "The internal needs feeding the scores above, and what the squid can see."
        )
        self.drives = DriveMetersWidget()
        drive_lay.addWidget(self.drives)
        root.addWidget(drive_card)

        # ---- History ----
        hist_card, hist_lay = self._section(
            "Recent decisions",
            "One block per recent choice — colour = action, height = confidence."
        )
        self.history = DecisionHistoryWidget()
        hist_lay.addWidget(self.history)
        root.addWidget(hist_card)

        # ---- Squid's thoughts (live narration) ----
        thoughts_card, thoughts_lay = self._section(
            "Squid's thoughts",
            "Live narration emitted as the squid perceives and reacts."
        )
        self.thought_log_text = QtWidgets.QTextEdit()
        self.thought_log_text.setReadOnly(True)
        self.thought_log_text.setMaximumHeight(DisplayScaling.scale(130))
        self.thought_log_text.setStyleSheet(
            "QTextEdit { background-color: #f7f9fc; border: 1px solid #e3e8ef;"
            f" border-radius: {DisplayScaling.scale(8)}px; color: #3a4652;"
            f" font-size: {DisplayScaling.font_size(12)}px;"
            f" padding: {DisplayScaling.scale(6)}px; }}"
        )
        thoughts_lay.addWidget(self.thought_log_text)
        root.addWidget(thoughts_card)

        root.addStretch(1)

    def add_thought(self, thought):
        """Append a narration line to the thought log.

        SquidBrainWindow.add_thought() prefers self.thought_log_text directly,
        but this keeps a fallback entry point (and is safe to call any time).
        """
        if getattr(self, 'thought_log_text', None) is not None:
            self.thought_log_text.append(str(thought))
            sb = self.thought_log_text.verticalScrollBar()
            sb.setValue(sb.maximum())

    # -- data plumbing ---------------------------------------------------- #

    def _gather(self):
        """Return a normalized decision view-model, or None if unavailable."""
        logic = self.tamagotchi_logic
        if not logic:
            return None

        raw = None
        # 1. Prefer the live DecisionEngine trace (rich, reflects the real choice)
        squid = getattr(logic, 'squid', None)
        engine = getattr(squid, '_decision_engine', None) if squid else None
        if engine and hasattr(engine, 'get_decision_data'):
            try:
                d = engine.get_decision_data()
                if d:
                    raw = d
            except Exception:
                raw = None
        # 2. Fall back to the logic-side snapshot
        if raw is None and hasattr(logic, 'get_decision_data'):
            try:
                raw = logic.get_decision_data()
            except Exception:
                raw = None
        if not raw:
            return None

        base = raw.get('base_weights') or raw.get('weights') or {}
        adjusted = raw.get('adjusted_weights') or {}
        if not adjusted:
            adjusted = dict(base)
        brain_state = raw.get('brain_state') or {}
        inputs = raw.get('inputs') or {}
        memory_influences = raw.get('memory_influences') or {}

        # Winner = argmax of adjusted weights (the chosen *action*)
        winner = None
        if adjusted:
            winner = max(adjusted, key=lambda k: adjusted.get(k, 0))

        final_decision = raw.get('final_decision') or (winner or "…")
        confidence = float(raw.get('confidence', 0.0) or 0.0)

        # Drives: prefer brain_state, then inputs
        drives = {}
        for key, _ in DRIVE_META:
            for src in (brain_state, inputs):
                if key in src and isinstance(src.get(key), (int, float)):
                    drives[key] = float(src[key])
                    break

        # Perception chips
        def _seen(*conds):
            return any(bool(c) for c in conds)

        perception = {
            "Food": _seen(inputs.get('has_food_visible'),
                          (brain_state.get('can_see_food', 0) or 0) > 50,
                          (inputs.get('can_see_food', 0) or 0) > 50),
            "Plant": _seen(inputs.get('has_plant_visible'),
                           (brain_state.get('plant_proximity', 0) or 0) > 40,
                           (inputs.get('plant_proximity', 0) or 0) > 40),
            "Rock": _seen(inputs.get('has_rock_visible'), inputs.get('carrying_rock'),
                          getattr(squid, 'carrying_rock', False) if squid else False),
            "Poop": _seen(inputs.get('has_poop_visible'),
                          getattr(squid, 'carrying_poop', False) if squid else False),
        }

        personality = raw.get('personality') or raw.get('personality_influence')
        if hasattr(personality, 'value'):
            personality = personality.value

        return {
            'base': base,
            'adjusted': adjusted,
            'memory_influences': memory_influences,
            'winner': winner,
            'final_decision': final_decision,
            'confidence': confidence,
            'drives': drives,
            'perception': perception,
            'personality': personality,
        }

    def update_from_brain_state(self, state):
        vm = self._gather()
        if not vm:
            return

        # Signature to avoid redundant work / spurious history entries
        sig = (
            vm['final_decision'],
            round(vm['confidence'], 3),
            tuple(sorted((k, round(v, 2)) for k, v in vm['adjusted'].items())),
        )
        changed = (sig != self._last_sig)
        self._last_sig = sig

        # Banner
        win = vm['winner']
        self.winner_emoji.setText(_action_emoji(vm['final_decision'] if not win else win))
        self.winner_action.setText(_pretty(win) if win else _pretty(vm['final_decision']))
        col = _action_color(win or vm['final_decision'])
        self.winner_action.setStyleSheet(
            f"font-size: {DisplayScaling.font_size(26)}px; font-weight: bold;"
            f" color: {col.name()};"
        )
        behaviour = vm['final_decision']
        self.winner_behaviour.setText(f"Behaviour: “{behaviour}”")

        # Personality badge
        if vm['personality']:
            self.personality_badge.setText(str(vm['personality']).capitalize())
            self.personality_badge.show()
        else:
            self.personality_badge.hide()

        # Gauge + bars + drives
        self.gauge.set_value(vm['confidence'])
        self.action_bars.set_data(vm['base'], vm['adjusted'], win)
        self.drives.set_data(vm['drives'], vm['perception'])

        # Pipeline for the winner
        if win is not None:
            self.pipeline.set_data(
                win,
                vm['base'].get(win, 0.0),
                vm['adjusted'].get(win, 0.0),
                vm['memory_influences'].get(win, 1.0),
            )
        else:
            self.pipeline.set_data(None, 0, 0, 1.0)

        # History – only on an actual new decision
        if changed:
            self.history.push(win or vm['final_decision'], vm['confidence'])
