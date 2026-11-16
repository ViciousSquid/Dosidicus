"""Resolve bundled image assets regardless of dev-tree vs. packaged APK layout."""
import os

# dosidicus_mobile/ui/assets.py -> app root is two levels up (android/)
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _asset_dir():
    """Where the pictures are.

    In an APK, android/prepare_apk.py has staged them in assets/ beside the
    app. In a checkout there is no second copy: they are the desktop game's
    images/ folder, one level above android/ (see android/mobile_assets.txt).
    """
    staged = os.path.join(_APP_ROOT, "assets")
    if os.path.isfile(os.path.join(staged, "icon.png")):
        return staged
    shared = os.path.join(os.path.dirname(_APP_ROOT), "images")
    return shared if os.path.isdir(shared) else staged


ASSET_DIR = _asset_dir()


def asset(name: str) -> str:
    return os.path.join(ASSET_DIR, name)
