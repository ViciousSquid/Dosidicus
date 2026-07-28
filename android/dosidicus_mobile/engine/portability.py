"""Export / import a squid as a .zip, matching the desktop layout.

The archive contains the same files the desktop app produces so squids can be
shared through the Squid-Exchange ecosystem:

    game_state.json    - the authoritative mobile save (full fidelity)
    brain_state.json   - desktop-shaped brain (weights_list, neuron_positions...)
    statistics.json    - lifetime stats (identical field names to desktop)
    ShortTerm.json     - short-term memories
    LongTerm.json      - long-term memories
    custom_brain.json  - null (no custom brain designer on mobile yet)
    achievements.json  - {}
    uuid.txt           - "SquidSignature\\t<uuid>"

Import reads game_state.json when it's a mobile save (perfect round-trip), and
falls back to a best-effort reconstruction from a desktop archive (squid stats,
brain weights/positions and memories).
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime

from .simulation import Simulation
from .squid import Squid
from .personality import Personality
from .memory import MemoryManager


# --------------------------------------------------------------------- export
def _brain_state_desktop(brain):
    """Desktop-shaped brain_state.json from our NeuralBrain."""
    seen, weights_list = set(), []
    for (a, b), w in brain.weights.items():
        key = tuple(sorted((a, b)))
        if key in seen:
            continue
        seen.add(key)
        weights_list.append([a, b, w])
    return {
        "weights_list": weights_list,
        "neuron_positions": {n: list(p) for n, p in brain.neuron_positions.items()},
        "neuron_states": {n: brain.state.get(n, 0.0) for n in brain.neuron_names},
        "neurogenesis_data": {"new_neurons": list(brain.neurogenesis.get("new_neurons", []))},
    }


def _memories_desktop(mem_list):
    out = []
    for m in mem_list:
        out.append({
            "timestamp": m.get("wall", 0) or 0,
            "category": m.get("category"),
            "key": m.get("key"),
            "value": m.get("value"),
            "importance": m.get("importance", 1.0),
            "related_neurons": m.get("related_neurons", []),
            "access_count": m.get("access_count", 1),
        })
    return out


def export_squid(sim: Simulation, path: str):
    """Write ``sim`` to a shareable .zip at ``path``."""
    squid = sim.squid
    files = {
        "game_state.json": sim.to_dict(),
        "brain_state.json": _brain_state_desktop(squid.brain),
        "statistics.json": sim.stats.to_dict(),
        "ShortTerm.json": _memories_desktop(squid.memory.short_term),
        "LongTerm.json": _memories_desktop(squid.memory.long_term),
        "custom_brain.json": None,
        "achievements.json": {},
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, json.dumps(data, indent=2))
        z.writestr("uuid.txt", f"SquidSignature\t{squid.uuid}")
    return path


# --------------------------------------------------------------------- import
def _read_json(z, name, default=None):
    try:
        return json.loads(z.read(name).decode("utf-8"))
    except (KeyError, ValueError):
        return default


def import_squid(path: str, tank_size=(900, 500)) -> Simulation:
    """Load a squid .zip. Mobile archives round-trip exactly; desktop archives
    are reconstructed best-effort."""
    with zipfile.ZipFile(path, "r") as z:
        game_state = _read_json(z, "game_state.json")

        # Mobile save? (our to_dict has version + tank_size). Use it directly.
        if isinstance(game_state, dict) and "version" in game_state and "tank_size" in game_state:
            sim = Simulation.from_dict(game_state)
            sim.tank_size = tank_size
            sim.squid.tank_size = tank_size
            return sim

        # Otherwise reconstruct from a desktop archive.
        return _import_desktop(z, game_state, tank_size)


def _import_desktop(z, game_state, tank_size):
    sq = (game_state or {}).get("squid", {}) if isinstance(game_state, dict) else {}
    personality = Personality.from_value(sq.get("personality", "adventurous"))
    squid = Squid(personality, tank_size=tank_size)

    stat_map = {"hunger": "hunger", "happiness": "happiness", "cleanliness": "cleanliness",
                "sleepiness": "sleepiness", "satisfaction": "satisfaction",
                "anxiety": "anxiety", "curiosity": "curiosity"}
    for src, dst in stat_map.items():
        if isinstance(sq.get(src), (int, float)):
            setattr(squid, dst, float(sq[src]))
    if sq.get("uuid"):
        squid.uuid = sq["uuid"]
    squid.is_sick = bool(sq.get("is_sick", False))

    # Brain: import neuron positions + weights from brain_state.json.
    bs = _read_json(z, "brain_state.json", {}) or {}
    positions = bs.get("neuron_positions") or {}
    for name, pos in positions.items():
        squid.brain.neuron_positions[name] = tuple(pos)
        squid.brain.state.setdefault(name, 50.0)
    for grown in bs.get("neurogenesis_data", {}).get("new_neurons", []):
        if grown not in squid.brain.neurogenesis["new_neurons"]:
            squid.brain.neurogenesis["new_neurons"].append(grown)
    squid.brain.weights = {}
    for entry in bs.get("weights_list", []):
        try:
            a, b, w = entry[0], entry[1], float(entry[2])
        except (ValueError, IndexError, TypeError):
            continue
        if a in squid.brain.neuron_positions and b in squid.brain.neuron_positions:
            squid.brain.set_weight(a, b, w)

    # Memories.
    def _load_mem(name, target):
        for m in (_read_json(z, name, []) or []):
            target.append({
                "timestamp": 0.0, "wall": m.get("timestamp", 0) or 0,
                "category": m.get("category"), "key": m.get("key"),
                "value": m.get("value"), "raw_value": None,
                "importance": m.get("importance", 1.0),
                "related_neurons": m.get("related_neurons", []),
                "access_count": m.get("access_count", 1),
            })
    squid.memory = MemoryManager()
    _load_mem("ShortTerm.json", squid.memory.short_term)
    _load_mem("LongTerm.json", squid.memory.long_term)

    sim = Simulation(tank_size=tank_size, squid=squid)
    # Desktop decorations embed base64 pixmaps and don't map to our bundled
    # assets, so they're skipped; everything else is reconstructed.
    from .statistics import Statistics
    sim.stats = Statistics.from_dict(_read_json(z, "statistics.json", {}))
    return sim
