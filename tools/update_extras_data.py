#!/usr/bin/env python3
"""Write what the browser tools in extras/ need to know about the game.

The Save Viewer and Squid Breeder are single HTML pages: they cannot import
the game. What they have to agree with it about - which neurons a squid is
born with and how they are wired, how inheritance mutates, which neurons are
drives, senses, actions or grown for other squid - is written here, from the
game's own modules, into extras/vendor/dosidicus_data.js.

    python tools/update_extras_data.py            write the file
    python tools/update_extras_data.py --check    exit 1 if it is out of date

tests/test_extras_tools.py runs the check, so the tools cannot quietly fall
behind the game again.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TARGET = ROOT / 'extras' / 'vendor' / 'dosidicus_data.js'


def game_data():
    from src import brain_constants as constants
    from src import fighting, inheritance, lifecycle
    from src.portable_brain import HeadlessBrain, TrainingConfig
    newborn = HeadlessBrain(TrainingConfig())
    version = re.search(r'^dosidicus:\s*(\S+)', (ROOT / 'version').read_text(), flags=re.M)
    return {
        'game_version': version.group(1) if version else '',
        # A squid as it hatches: its neurons, where they sit, how they are wired.
        'newborn_neurons': {name: [round(float(x), 2), round(float(y), 2)]
                            for name, (x, y) in newborn.positions.items()},
        'newborn_connections': sorted([src, dst, round(float(weight), 4)]
                                      for (src, dst), weight in newborn.weights.items()),
        # src/inheritance.py
        'mutation_rate': inheritance.MUTATION_RATE,
        'mutation_size': inheritance.MUTATION_SIZE,
        'max_genes': inheritance.MAX_GENES,
        # What kind of neuron a name is.
        'core_neurons': sorted(constants.CORE_STAT_NEURONS),
        'action_neurons': sorted(constants.ACTION_NEURONS),
        'binary_neurons': sorted(constants.BINARY_NEURONS),
        # What the world sets and the network only reads.
        'input_sensors': sorted(set(constants.DEFAULT_INPUT_SENSORS) | set(constants.SOCIAL_SENSORS)),
        'social_senses': sorted(constants.SOCIAL_SENSORS),
        'social_neurons': sorted(constants.SOCIAL_NEURONS),
        'aggression_neuron': constants.AGGRESSION_NEURON,
        # src/fighting.py, src/lifecycle.py
        'aggression_threshold': fighting.AGGRESSION_THRESHOLD,
        'lifecycle_stages': list(lifecycle.STAGES),
        'death_causes': list(lifecycle.CAUSES),
    }


def rendered():
    body = json.dumps(game_data(), indent=1, sort_keys=True)
    return ('// Written by tools/update_extras_data.py from the game\'s own modules.\n'
            '// Do not edit: run that tool. tests/test_extras_tools.py fails if this\n'
            '// file no longer matches the game.\n'
            f'window.DOSIDICUS = {body};\n')


if __name__ == '__main__':
    text = rendered()
    if '--check' in sys.argv[1:]:
        if not TARGET.exists() or TARGET.read_text() != text:
            print(f'{TARGET.relative_to(ROOT)} is out of date: run tools/update_extras_data.py')
            sys.exit(1)
        print('up to date')
    else:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(text)
        print(f'wrote {TARGET.relative_to(ROOT)}')
