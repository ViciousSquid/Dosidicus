"""Locate the shared engine in a checkout or in the staged APK sources."""
import sys
from pathlib import Path

# Development uses the actual desktop sources. APK staging puts that same src
# package beside main.py; never maintain a second copy in the mobile package.
_checkout = Path(__file__).resolve().parents[3]
if (_checkout / "src" / "portable_brain.py").is_file():
    sys.path.insert(0, str(_checkout))

from src.portable_brain import HeadlessBrain, TrainingConfig  # noqa: E402,F401
