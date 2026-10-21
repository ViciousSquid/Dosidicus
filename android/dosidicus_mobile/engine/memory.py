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


from . import shared
from src.memory_manager import MemoryManager as DesktopMemoryManager


class MemoryManager(DesktopMemoryManager):
    """In-memory, simulation-clock adapter over desktop memory management."""
    def __init__(self):
        self._now = 0.0
        super().__init__(persistent=False, clock=lambda: self._now)

    @property
    def short_term(self):
        return self.short_term_memory

    @short_term.setter
    def short_term(self, value):
        self.short_term_memory = value

    @property
    def long_term(self):
        return self.long_term_memory

    @long_term.setter
    def long_term(self, value):
        self.long_term_memory = value

    def add_short_term(self, category, key, value, raw_value=None,
                       importance=1.0, related_neurons=None, now=0.0):
        self._now = now
        self.add_short_term_memory(category, key, value, importance, related_neurons)
        for memory in self.short_term + self.long_term:
            if memory.get('category') == category and memory.get('key') == key:
                memory.update(raw_value=raw_value, wall=time.time())

    def add_long_term(self, category, key, value, raw_value=None, now=0.0):
        self._now = now
        self.add_long_term_memory(category, key, value)
        for memory in self.long_term:
            if memory.get('category') == category and memory.get('key') == key:
                memory.update(raw_value=raw_value, wall=time.time())

    def should_transfer(self, memory):
        return self.should_transfer_to_long_term(memory)

    def transfer(self, category, key, now=0.0):
        self._now = now
        source = next((dict(m) for m in self.short_term if m.get('category') == category and m.get('key') == key), None)
        self.transfer_to_long_term_memory(category, key)
        if source:
            for memory in self.long_term:
                if memory.get('category') == category and memory.get('key') == key:
                    memory.update(source)

    def review_and_transfer(self, now):
        self._now = now
        self.review_and_transfer_memories()

    def periodic(self, now):
        self._now = now
        self.periodic_memory_management()

    def consolidate_sleep(self, now):
        """Sleep consolidation: rehearse and promote the day's more meaningful
        short-term memories into long-term storage. Sleep lowers the promotion
        bar (an event only needs to be moderately important or to have been
        revisited), mirroring how the desktop's sleep replay cements memories.

        Returns the number of memories promoted.
        """
        promoted = 0
        for m in list(self.short_term):
            if (self.should_transfer(m)
                    or m.get("importance", 1) >= 4
                    or m.get("access_count", 0) >= 2):
                self.transfer(m["category"], m["key"], now)
                promoted += 1
        return promoted

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
