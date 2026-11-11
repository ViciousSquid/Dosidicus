"""Where the laboratory tools are on this machine.

The browser tools (extras/Laboratory.html and the rest) are shipped beside
the game in every build and sit in the repository when it is run from
source. They are looked for beside the program, then in the folder the game
is working in - which on a Mac is its data folder, where the app's own copy
is linked.
"""
import os
import sys
from pathlib import Path
from typing import Optional

FOLDER = 'extras'
LABORATORY = 'Laboratory.html'


def extras_folder() -> Optional[Path]:
    """The folder holding the tools, or None if this copy has none."""
    places = [Path(__file__).resolve().parent.parent,          # beside src/
              Path(sys.executable).resolve().parent,            # beside a built game
              Path(os.path.abspath(sys.argv[0] or '.')).parent,
              Path.cwd()]
    for place in places:
        folder = place / FOLDER
        if (folder / LABORATORY).is_file():
            return folder
    return None


def laboratory_page() -> Optional[Path]:
    folder = extras_folder()
    return folder / LABORATORY if folder else None


__all__ = ['extras_folder', 'laboratory_page', 'FOLDER', 'LABORATORY']
