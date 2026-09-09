# File: peer_ledger.py
"""What this squid remembers about other squid.

This is deliberately NOT a database. Every encounter is written to the squid's
own MemoryManager as an ordinary memory - category 'social', key
'peer:<uuid>' - and this class is a *view* over what is already there.

The reason is that MemoryManager already does the things a relationship store
would otherwise have to reimplement and then keep in sync:

  * long-term memory persists across sessions in _memory/LongTerm.json;
  * should_transfer_to_long_term() already decides what deserves to last, so
    this asks that question rather than inventing a second threshold;
  * re-writing the same (category, key) raises importance by 0.5 and
    re-promotes, so a second bad encounter with the same individual is
    automatically weightier than the first.

A second store would drift from that one, and then two answers to "what
happened with this squid" would exist. The only thing kept here is an
aggregate cache, which is derived and can always be rebuilt.
"""

import time
from typing import Any, Dict, List, Optional

from .identity import SquidIdentity, memory_key_for

MEMORY_CATEGORY = 'social'

#: Familiarity saturates: the difference between the first and second meeting
#: matters, the difference between the ninth and tenth does not.
_FAMILIARITY_SATURATION = 6.0

#: How much of a single encounter's valence a sensor should read. Encounter
#: valence is a signed drive delta; this maps it onto the 0-100 activation
#: scale every neuron in the project uses.
_VALENCE_FULL_SCALE = 40.0


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


class PeerSummary:
    """Everything this squid knows about one individual, at a glance."""

    __slots__ = ('uuid', 'name', 'encounters', 'good', 'bad', 'last_seen',
                 'last_outcome')

    def __init__(self, uuid: str, name: str = "Squid"):
        self.uuid = uuid
        self.name = name
        self.encounters = 0
        self.good = 0.0          # summed positive valence
        self.bad = 0.0           # summed negative valence, as a positive number
        self.last_seen = 0.0
        self.last_outcome = ""

    @property
    def familiarity(self) -> float:
        """0 for a stranger, rising toward 100 and saturating.

        A stranger reading exactly zero is the point: a sensor at rest means
        "nothing to report", and having never met this squid before is
        precisely nothing to report.
        """
        if self.encounters <= 0:
            return 0.0
        return _clamp(100.0 * min(1.0, self.encounters / _FAMILIARITY_SATURATION))

    @property
    def recalled_good(self) -> float:
        return _clamp(100.0 * min(1.0, self.good / _VALENCE_FULL_SCALE))

    @property
    def recalled_bad(self) -> float:
        return _clamp(100.0 * min(1.0, self.bad / _VALENCE_FULL_SCALE))

    def to_dict(self) -> Dict[str, Any]:
        return {
            'uuid': self.uuid, 'name': self.name,
            'encounters': self.encounters,
            'familiarity': round(self.familiarity, 1),
            'recalled_good': round(self.recalled_good, 1),
            'recalled_bad': round(self.recalled_bad, 1),
            'last_seen': self.last_seen,
            'last_outcome': self.last_outcome,
        }


class PeerLedger:
    """Reads and writes encounter history through the squid's own memory."""

    def __init__(self, memory_manager=None):
        self.memory_manager = memory_manager
        self._summaries: Dict[str, PeerSummary] = {}
        self._loaded = False

    # -- reading --------------------------------------------------------
    def summary(self, peer_uuid: str) -> PeerSummary:
        """What is remembered about this individual. Never None.

        A squid that has never met this one gets a summary reading zero
        everywhere, which is a real answer rather than a missing one.
        """
        self._ensure_loaded()
        key = str(peer_uuid)
        found = self._summaries.get(key)
        if found is None:
            found = PeerSummary(key)
            self._summaries[key] = found
        return found

    def familiarity(self, peer_uuid: str) -> float:
        return self.summary(peer_uuid).familiarity

    def recalled_good(self, peer_uuid: str) -> float:
        return self.summary(peer_uuid).recalled_good

    def recalled_bad(self, peer_uuid: str) -> float:
        return self.summary(peer_uuid).recalled_bad

    def known_peers(self) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        return [s.to_dict() for s in self._summaries.values() if s.encounters > 0]

    # -- writing --------------------------------------------------------
    def record(self, record) -> bool:
        """File one encounter as an ordinary memory, and update the cache.

        `record` is an EncounterRecord. Returns True if it reached memory.
        """
        summary = self.summary(record.peer.uuid)
        summary.name = record.peer.name or summary.name
        summary.encounters += 1
        if record.valence >= 0:
            summary.good += float(record.valence)
        else:
            summary.bad += abs(float(record.valence))
        summary.last_seen = record.ended_at or time.time()
        summary.last_outcome = record.outcome

        manager = self.memory_manager
        if manager is None or not hasattr(manager, 'add_short_term_memory'):
            return False
        manager.add_short_term_memory(
            category=MEMORY_CATEGORY,
            key=record.memory_key,
            value=record.to_memory_value(),
            importance=record.importance,
            related_neurons=list(record.related_neurons),
        )

        # Promote now if the existing rule says this one deserves to last.
        #
        # MemoryManager promotes a NEW memory only when review_and_transfer
        # runs, which is 30 seconds apart and only considers memories already
        # older than the five-minute short-term window. An encounter that
        # frightened the squid would therefore sit in short-term storage for
        # five minutes and be lost outright if the session ended first - so
        # "the squid remembers being robbed" would depend on how long the
        # player kept playing afterwards.
        #
        # The threshold is not re-decided here: should_transfer_to_long_term
        # is asked, so this stays the same rule the rest of memory uses.
        if hasattr(manager, 'should_transfer_to_long_term'):
            candidate = {'importance': record.importance, 'access_count': 1}
            if manager.should_transfer_to_long_term(candidate):
                manager.transfer_to_long_term_memory(MEMORY_CATEGORY,
                                                     record.memory_key)
        return True

    # -- cache ----------------------------------------------------------
    def refresh(self) -> None:
        """Rebuild the cache from memory. Safe to call at any time."""
        self._summaries = {}
        self._loaded = False
        self._ensure_loaded()

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True         # set first: a failed load must not re-loop
        manager = self.memory_manager
        if manager is None or not hasattr(manager, 'get_memories_by_key_prefix'):
            return
        try:
            memories = manager.get_memories_by_key_prefix(MEMORY_CATEGORY, 'peer:')
        except Exception as exc:
            print(f"[PeerLedger] could not read encounter memories: {exc}")
            return
        for memory in memories:
            self._absorb(memory)

    def _absorb(self, memory: Dict[str, Any]) -> None:
        key = memory.get('key') or ''
        if not key.startswith('peer:'):
            return
        peer_uuid = key[len('peer:'):]
        if not peer_uuid:
            return
        summary = self._summaries.get(peer_uuid)
        if summary is None:
            summary = PeerSummary(peer_uuid)
            self._summaries[peer_uuid] = summary

        value = memory.get('value')
        if not isinstance(value, dict):
            # A memory written before this format, or by hand. It still counts
            # as having met the squid; it just carries no valence.
            summary.encounters += 1
            return

        detail = value.get('detail') if isinstance(value.get('detail'), dict) else {}
        summary.name = value.get('peer_name') or summary.name
        summary.encounters += max(1, int(detail.get('encounters', 1) or 1))
        valence = value.get('valence', 0.0)
        try:
            valence = float(valence)
        except (TypeError, ValueError):
            valence = 0.0
        if valence >= 0:
            summary.good += valence
        else:
            summary.bad += abs(valence)
        summary.last_outcome = str(value.get('outcome') or summary.last_outcome)
        timestamp = memory.get('timestamp')
        if isinstance(timestamp, (int, float)):
            summary.last_seen = max(summary.last_seen, float(timestamp))


__all__ = ['PeerLedger', 'PeerSummary', 'MEMORY_CATEGORY', 'memory_key_for',
           'SquidIdentity']
