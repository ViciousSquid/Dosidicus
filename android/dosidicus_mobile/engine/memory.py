"""Dual short/long-term memory, ported from ``src/memory_manager.py``.

Faithful to the desktop behaviour (importance boosting on repeat, promotion to
long-term memory, decay of stale short-term memories) but driven by the
simulation clock instead of wall-clock time and held in memory (the Simulation
persists it as part of the save rather than to separate JSON files).

A memory item::

    {timestamp, wall, category, key, value (text), raw_value (dict|None),
     importance, access_count, related_neurons}

``raw_value`` is a dict of stat deltas (e.g. {"hunger": -45, "satisfaction": 25})
so the UI can colour a memory positive/negative and the decision engine can
weigh it, exactly like the desktop.
"""

from __future__ import annotations

import time
from datetime import datetime


class MemoryManager:
    def __init__(self):
        self.short_term = []
        self.long_term = []
        self.short_term_limit = 50
        self.short_term_duration = 300.0   # sim seconds (5 simulated minutes)
        self._last_cleanup = 0.0

    # ------------------------------------------------------------- write
    def add_short_term(self, category, key, value, raw_value=None,
                       importance=1.0, related_neurons=None, now=0.0):
        for m in self.short_term:
            if m.get("key") == key and m.get("category") == category:
                m["importance"] = m.get("importance", 1.0) + 0.5
                m["timestamp"] = now
                m["wall"] = time.time()
                m["access_count"] = m.get("access_count", 0) + 1
                if m["importance"] >= 3.0:
                    self.transfer(category, key, now)
                return
        self.short_term.append({
            "timestamp": now, "wall": time.time(),
            "category": category, "key": key, "value": value,
            "raw_value": raw_value, "importance": importance,
            "related_neurons": related_neurons or [], "access_count": 1,
        })
        if len(self.short_term) > self.short_term_limit:
            self.short_term.pop(0)

    def add_long_term(self, category, key, value, raw_value=None, now=0.0):
        for m in self.long_term:
            if m.get("key") == key and m.get("category") == category:
                m["timestamp"] = now
                return
        self.long_term.append({
            "timestamp": now, "wall": time.time(), "category": category,
            "key": key, "value": value, "raw_value": raw_value,
        })

    # ------------------------------------------------------------- promote / decay
    def should_transfer(self, m):
        return (m.get("importance", 1) >= 7 or
                m.get("access_count", 0) >= 3 or
                (m.get("importance", 1) >= 5 and m.get("access_count", 0) >= 2))

    def transfer(self, category, key, now=0.0):
        for m in list(self.short_term):
            if m.get("category") == category and m.get("key") == key:
                self.add_long_term(category, key, m["value"], m.get("raw_value"), now)
                self.short_term.remove(m)
                return

    def review_and_transfer(self, now):
        for m in list(self.short_term):
            if (now - m.get("timestamp", 0)) > self.short_term_duration:
                if self.should_transfer(m):
                    self.transfer(m["category"], m["key"], now)
                else:
                    self.short_term.remove(m)
        if len(self.short_term) > self.short_term_limit:
            self.short_term.sort(
                key=lambda x: (x.get("importance", 1), x.get("access_count", 0)),
                reverse=True)
            self.short_term = self.short_term[:self.short_term_limit]

    def periodic(self, now):
        if now - self._last_cleanup > 30.0:
            self._last_cleanup = now
            self.review_and_transfer(now)

    # ------------------------------------------------------------- read
    def get_active_memories_data(self, now, count=None):
        active = []
        for m in self.short_term:
            ts = m.get("timestamp", 0)
            if (now - ts) <= self.short_term_duration:
                wall = m.get("wall", 0)
                time_str = (datetime.fromtimestamp(wall).strftime("%H:%M:%S")
                            if wall else "--:--:--")
                active.append({
                    "category": m.get("category"),
                    "key": m.get("key"),
                    "formatted_value": m.get("value"),
                    "raw_value": m.get("raw_value"),
                    "time_str": time_str,
                    "importance": m.get("importance", 1),
                    "access_count": m.get("access_count", 0),
                })
        active.sort(key=lambda x: (x["importance"], x["access_count"]), reverse=True)
        return active[:count] if count else active

    def get_long_term_data(self):
        out = []
        for m in self.long_term:
            wall = m.get("wall", 0)
            out.append({
                "category": m.get("category"), "key": m.get("key"),
                "formatted_value": m.get("value"), "raw_value": m.get("raw_value"),
                "time_str": (datetime.fromtimestamp(wall).strftime("%H:%M:%S")
                             if wall else "--:--:--"),
            })
        return out

    # ------------------------------------------------------------- persistence
    def to_dict(self):
        return {"short_term": self.short_term, "long_term": self.long_term}

    @classmethod
    def from_dict(cls, data):
        mm = cls()
        if data:
            mm.short_term = data.get("short_term", [])
            mm.long_term = data.get("long_term", [])
        return mm
