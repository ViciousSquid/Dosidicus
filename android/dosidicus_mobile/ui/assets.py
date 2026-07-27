"""Resolve bundled image assets regardless of dev-tree vs. packaged APK layout."""
import os

# dosidicus_mobile/ui/assets.py -> app root is two levels up (android/)
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSET_DIR = os.path.join(_APP_ROOT, "assets")


def asset(name: str) -> str:
    return os.path.join(ASSET_DIR, name)
