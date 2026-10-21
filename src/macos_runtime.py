"""Prepare a writable working directory for a frozen macOS Dosidicus app.

The GUI historically resolves images, plugins, config.ini, saves and logs from
the current directory. Finder does not guarantee the bundle's runtime directory
as cwd, and a signed .app must not be used as a writable data directory.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys


_READ_ONLY_DIRECTORIES = ("images", "plugins", "src", "translations", "example_squids")
_READ_ONLY_FILES = ("version", "README.md", "LICENSE")


def prepare_macos_runtime(*, executable=None, data_dir=None):
    """Switch frozen .app launches to Application Support with bundled assets.

    Returns the data directory, or None when not running from a .app bundle.
    Optional paths permit platform-independent unit tests.
    """
    if sys.platform != "darwin" and executable is None:
        return None

    binary = Path(executable or sys.executable).resolve()
    resources = binary.parent
    if resources.name != "MacOS" or resources.parent.name != "Contents":
        return None

    override = os.environ.get("DOSIDICUS_DATA_DIR")
    workdir = Path(data_dir or override or
                   (Path.home() / "Library" / "Application Support" / "Dosidicus"))
    workdir.mkdir(parents=True, exist_ok=True)

    # Relative asset lookups continue to work, even when the bundle is
    # installed in /Applications (normally not writable by standard users).
    # Refresh our links if the .app was moved or replaced by an update.
    for name in (*_READ_ONLY_DIRECTORIES, *_READ_ONLY_FILES):
        source = resources / name
        if not source.exists():
            continue
        destination = workdir / name
        if destination.is_symlink() and destination.resolve() != source.resolve():
            destination.unlink()
        if not destination.exists() and not destination.is_symlink():
            destination.symlink_to(source, target_is_directory=source.is_dir())

    # Preserve mutable user files between upgrades and never edit signed
    # resources in Contents/MacOS.
    config_source = resources / "config.ini"
    config_target = workdir / "config.ini"
    if config_source.is_file() and not config_target.exists():
        shutil.copy2(config_source, config_target)

    brains_source = resources / "custom_brains"
    brains_target = workdir / "custom_brains"
    if brains_source.is_dir() and not brains_target.exists():
        shutil.copytree(brains_source, brains_target)

    os.chdir(workdir)
    return workdir
