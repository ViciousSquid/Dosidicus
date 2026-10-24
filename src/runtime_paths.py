"""Writable storage for the macOS app, including launches from a read-only DMG."""

import os
from pathlib import Path
import shutil
import sys


def is_macos_bundle():
    return sys.platform == "darwin" and getattr(sys, "frozen", False)


def runtime_data_dir():
    if is_macos_bundle():
        # Only the automated startup check uses an isolated, temporary directory.
        if "--smoke-test" in sys.argv and os.environ.get("DOSIDICUS_SMOKE_DATA_DIR"):
            return Path(os.environ["DOSIDICUS_SMOKE_DATA_DIR"]).resolve()
        return Path.home() / "Library" / "Application Support" / "Dosidicus"
    return Path.cwd()


def prepare_macos_runtime():
    if not is_macos_bundle():
        return
    resources = Path(sys._MEIPASS)
    destination = runtime_data_dir()
    destination.mkdir(parents=True, exist_ok=True)
    # Refresh shipped assets and built-in plugin code, keeping user settings,
    # saves, memories, added plugins and custom brains between launches.
    for directory in ("images", "plugins", "custom_brains", "example_squids", "src"):
        source = resources / directory
        for path in source.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            target = destination / path.relative_to(resources)
            target.parent.mkdir(parents=True, exist_ok=True)
            if directory in ("images", "src") or path.suffix == ".py" or not target.exists():
                shutil.copy2(path, target)
    config = destination / "config.ini"
    if not config.exists():
        shutil.copy2(resources / "config.ini", config)
    for directory in ("saves", "_memory", "logs", "exports"):
        (destination / directory).mkdir(exist_ok=True)
    os.chdir(destination)
    # Windowed PyInstaller apps have no console streams. Existing logging and
    # debug TeeStream code expect writable file objects.
    for stream in ("stdout", "stderr"):
        if getattr(sys, stream) is None:
            setattr(sys, stream, (destination / "logs" / "console.log").open(
                "a", encoding="utf-8", buffering=1
            ))
