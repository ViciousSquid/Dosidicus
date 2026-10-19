"""Mobile file actions over the shared desktop brain interchange format."""
import json
from pathlib import Path
from .shared import HeadlessBrain  # establishes the shared source path
from src.brain_io import MAX_BRAIN_BYTES, read_brain_file
from src.brain_io import normalise_brain as _normalise


def normalise_brain(data):
    return _normalise(data, require_required=True)


def import_brain(path, personality=None, sim_time=None):
    from .brain import NeuralBrain
    payload = normalise_brain(read_brain_file(path))
    if personality is not None:
        payload['personality'] = getattr(personality, 'value', personality)
    if sim_time is not None:
        payload['sim_time'] = float(sim_time)
    return NeuralBrain.from_dict(payload)


def export_brain(brain, path):
    payload = normalise_brain(brain.to_dict())
    payload['metadata']['exported_by'] = 'dosidicus_android_3.1'
    Path(path).write_text(json.dumps(payload, indent=2, allow_nan=False), encoding='utf-8')
    return str(path)
