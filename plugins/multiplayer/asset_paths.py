# File: asset_paths.py
"""Turning a name from the network into a local file, safely.

A carried item arrives as a filename because the two tanks are two copies of
the same game and are expected to have the same artwork. The name is still
remote input, and it was previously used to build candidate paths of which the
last was the value verbatim - so `../../something.png` resolved outside the
game's own directories. Only an image was ever loaded from it, which bounds
the damage, but it is not a property to carry into anything routable.

Two rules, applied in one place so both call sites get them:

  1. only the basename is ever used, so nothing can traverse upward;
  2. the resolved path must sit inside one of the allowed asset roots, checked
     after resolution so a symlink cannot step outside either.
"""

import os
from typing import List, Optional, Sequence

#: Where game artwork lives. Relative to the game's working directory, which
#: is how the rest of the project addresses its images.
ASSET_ROOTS: Sequence[str] = (
    os.path.join("images", "decoration"),
    os.path.join("images", "items"),
    os.path.join("images", "food"),
    os.path.join("images", "rocks"),
    "images",
)

ALLOWED_SUFFIXES = ('.png', '.jpg', '.jpeg', '.gif', '.webp')


def safe_asset_name(remote_name) -> Optional[str]:
    """The bare filename from a remote value, or None if it is not usable.

    Rejects anything that is not a plain image filename: no directories, no
    traversal, no absolute paths, no unexpected suffix.
    """
    if not isinstance(remote_name, str):
        return None
    candidate = remote_name.strip().replace('\\', '/')
    if not candidate:
        return None
    # Take the last path segment and nothing else. This alone defeats
    # traversal; the checks below defeat the rest.
    base = os.path.basename(candidate)
    if not base or base in ('.', '..'):
        return None
    if base.startswith('.'):
        return None
    if os.path.isabs(base) or os.sep in base or (os.altsep and os.altsep in base):
        return None
    if not base.lower().endswith(ALLOWED_SUFFIXES):
        return None
    return base


def _roots(extra_roots: Optional[Sequence[str]] = None) -> List[str]:
    roots = list(ASSET_ROOTS)
    if extra_roots:
        roots = list(extra_roots) + roots
    return roots


def is_inside_assets(path: str, extra_roots: Optional[Sequence[str]] = None) -> bool:
    """True if `path` really sits inside an allowed asset root.

    Checked on the RESOLVED path, so a symlink pointing out of the tree fails
    here even though its name looked ordinary.
    """
    try:
        resolved = os.path.realpath(path)
    except (OSError, ValueError):
        return False
    for root in _roots(extra_roots):
        try:
            root_real = os.path.realpath(root)
        except (OSError, ValueError):
            continue
        if os.path.commonpath([resolved, root_real]) == root_real:
            return True
    return False


def resolve_local_asset(remote_name,
                        extra_roots: Optional[Sequence[str]] = None,
                        must_exist: bool = True) -> Optional[str]:
    """Find the local file a remote item name refers to, or None.

    Never returns a path outside the asset roots, whatever the remote sent.
    """
    base = safe_asset_name(remote_name)
    if base is None:
        return None
    for root in _roots(extra_roots):
        candidate = os.path.join(root, base)
        if must_exist and not os.path.isfile(candidate):
            continue
        if not is_inside_assets(candidate, extra_roots):
            continue
        return candidate
    return None


__all__ = ['safe_asset_name', 'resolve_local_asset', 'is_inside_assets',
           'ASSET_ROOTS', 'ALLOWED_SUFFIXES']
