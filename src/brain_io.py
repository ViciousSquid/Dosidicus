"""Brain interchange shared by the game, Designer, trainer and Android.

The desktop save's brain_state.json is authoritative. JSON brain documents use
the existing Designer neurons/connections layout; legacy layouts remain readable.
This module has no UI dependencies.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import zipfile

from .brain_constants import REQUIRED_NEURONS, newborn_neurons, INNATE_ACTION_WIRING, action_competition_wiring
from .propagation import baseline_of

MAX_BRAIN_BYTES = 16 * 1024 * 1024


def _number(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Brain contains a non-finite number')
    return value


def brain_document(data):
    """Unwrap a desktop save bundle or custom-brain wrapper without stale data."""
    if not isinstance(data, dict):
        raise ValueError('Expected a brain object')
    if 'brain_state' in data:
        custom = data.get('custom_brain') or {}
        base = deepcopy(custom.get('brain_definition') or {})
        current = data['brain_state']
        if not isinstance(current, dict):
            raise ValueError('Invalid brain_state')
        # Do not let the original custom architecture shadow the live save.
        if any(k in current for k in ('neuron_positions', 'positions', 'neurons')):
            for key in ('neurons', 'positions', 'neuron_positions', 'connections', 'weights', 'weights_list', 'state'):
                base.pop(key, None)
        base.update(deepcopy(current))
        squid = (data.get('game_state') or {}).get('squid') or {}
        state = base.setdefault('state', deepcopy(base.get('neuron_states', {})))
        for name in REQUIRED_NEURONS:
            if name in squid:
                state[name] = squid[name]
        if 'neuron_states' in base:
            base['neuron_states'] = deepcopy(state)
        return base
    if data.get('is_custom_brain'):
        return brain_document(data.get('brain_definition'))
    if 'brain' in data and not any(k in data for k in ('neurons', 'positions', 'neuron_positions')):
        return brain_document(data['brain'])
    return deepcopy(data)


def normalise_brain(data, *, require_required=False):
    data = brain_document(data)
    payload = deepcopy(data)
    positions = data.get('neuron_positions') if 'weights_list' in data else None
    if positions is None:
        positions = data.get('neurons', data.get('positions', data.get('neuron_positions')))
    if isinstance(positions, list):
        positions = {n['name']: n for n in positions}
    if not positions and 'layers' in data:
        positions = {name: [100 + j * 90, 80 + i * 150]
                     for i, layer in enumerate(data['layers'])
                     for j, name in enumerate(layer.get('neurons', []))}
    if not isinstance(positions, dict) or not positions or len(positions) > 2048:
        raise ValueError('Brain must contain 1–2048 named neurons')
    neurons = {}
    for name, raw in positions.items():
        if not isinstance(name, str) or not name:
            raise ValueError('Invalid neuron name')
        original_neurons = data.get('neurons') or {}
        original = original_neurons.get(name, {}) if isinstance(original_neurons, dict) else {}
        attributes = deepcopy(raw if isinstance(raw, dict) else original if isinstance(original, dict) else {})
        pos = attributes.get('position', [attributes.get('x', 0), attributes.get('y', 0)]) if isinstance(raw, dict) else raw
        if not isinstance(pos, (list, tuple)) or len(pos) != 2:
            raise ValueError(f'Invalid position for {name}')
        neurons[name] = dict(attributes, position=[_number(v) for v in pos])
    missing = set(REQUIRED_NEURONS) - neurons.keys()
    if require_required and missing:
        raise ValueError('Brain is missing required neurons: ' + ', '.join(sorted(missing)))
    edges = data.get('weights_list', data.get('connections', data.get('weights', data.get('custom_connections', []))))
    if isinstance(edges, dict):
        entries = []
        for key, value in edges.items():
            if isinstance(key, tuple) and len(key) == 2:
                names = key
            elif isinstance(key, str):
                separator = '->' if '->' in key else ('|' if '|' in key else ',')
                names = [n.strip() for n in key.replace('(', '').replace(')', '').replace("'", '').split(separator)]
            else:
                raise ValueError('Invalid connection key')
            if len(names) != 2:
                raise ValueError('Invalid connection key: ' + str(key))
            entries.append([*names, value])
    elif isinstance(edges, list):
        entries = edges
    else:
        raise ValueError('Invalid connections')
    connections = []
    for edge in entries:
        if isinstance(edge, dict):
            a, b, weight = edge.get('source', edge.get('from')), edge.get('target', edge.get('to')), edge.get('weight', 0)
        elif isinstance(edge, (list, tuple)) and len(edge) == 3:
            a, b, weight = edge
        else:
            raise ValueError('Invalid connection')
        if a not in neurons or b not in neurons:
            raise ValueError(f'Connection references an unknown neuron: {a} -> {b}')
        connections.append(dict(source=a, target=b, weight=_number(weight)))
    # Only pre-3.1 Android saves need motor-bank migration.
    if 'engine_version' not in data and 'neurogenesis' in data and 'neuron_positions' in data:
        for name, pos in newborn_neurons().items():
            neurons.setdefault(name, dict(position=list(pos), is_custom=False))
        present = {(e['source'], e['target']) for e in connections}
        for a, b, weight in tuple(INNATE_ACTION_WIRING) + action_competition_wiring():
            if (a, b) not in present:
                connections.append(dict(source=a, target=b, weight=weight))
    state = data.get('state', {})
    if isinstance(state, dict) and 'neuron_states' in data:
        state = dict(state, **data['neuron_states'])
    if not isinstance(state, dict):
        raise ValueError('Invalid brain state')
    payload['state'] = {n: (100.0 if state.get(n, nd.get('activation', baseline_of(n))) is True
                              else _number(state.get(n, nd.get('activation', baseline_of(n)))))
                        for n, nd in neurons.items()}
    for name, neuron in neurons.items():
        neuron['activation'] = payload['state'][name]
    for key in ('positions', 'weights', 'weights_list', 'neuron_positions', 'neuron_states'):
        payload.pop(key, None)
    payload.update(neurons=neurons, connections=connections)
    payload.setdefault('neurogenesis_data', data.get('neurogenesis', {}))
    return payload


def read_brain_file(path):
    """Read a brain JSON or the live brain inside a desktop/mobile save ZIP."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            bundle = {}
            for name in ('brain_state', 'game_state', 'custom_brain'):
                member = name + '.json'
                if member not in archive.namelist():
                    continue
                if archive.getinfo(member).file_size > MAX_BRAIN_BYTES:
                    raise ValueError('Save member exceeds 16 MiB: ' + member)
                bundle[name] = json.loads(archive.read(member).decode('utf-8'))
            if not bundle.get('brain_state'):
                if not bundle.get('custom_brain'):
                    raise ValueError('Save contains no brain_state.json or custom brain')
                return brain_document(bundle['custom_brain'])
            return brain_document(bundle)
    if Path(path).stat().st_size > MAX_BRAIN_BYTES:
        raise ValueError('Brain file exceeds 16 MiB')
    return brain_document(json.loads(Path(path).read_text(encoding='utf-8')))


def desktop_brain_state(data):
    """Use the desktop save keys, preserving all cognitive and Designer data."""
    payload = normalise_brain(data)
    payload['weights_list'] = [[e['source'], e['target'], e['weight']] for e in payload['connections']]
    payload['neuron_positions'] = {n: nd['position'] for n, nd in payload['neurons'].items()}
    payload['neuron_states'] = dict(payload['state'])
    return payload
