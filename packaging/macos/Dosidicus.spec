# Build using the universal2 framework Python; thin dependencies are rejected.
from pathlib import Path
import re
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).parents[1]
version_text = (root / "version").read_text()
version = re.search(r"dosidicus:\s*(\d+\.\d+\.\d+)", version_text).group(1)
data = [(str(root / name), name) for name in (
    "images", "plugins", "custom_brains", "example_squids", "translations"
)]
data += [(str(root / name), ".") for name in ("config.ini", "version", "LICENSE")]
data += [(str(path), "src") for pattern in ("*.ttf", "*.json")
         for path in (root / "src").glob(pattern)]
hidden = collect_submodules("src", filter=lambda name: name != "src.main")
hidden += collect_submodules("plugins") + collect_submodules("translations")
# Some designer modules are imported by their bare names after modifying sys.path.
hidden += [path.stem for path in (root / "src").glob("designer_*.py")]
hidden += ["brain_designer", "brain_designer_launcher", "brain_state_bridge"]

a = Analysis(
    [str(root / "main.py")], pathex=[str(root), str(root / "src")],
    binaries=[], datas=data, hiddenimports=hidden,
    runtime_hooks=[str(root / "packaging/macos/runtime_hook.py")],
    excludes=["PySide2", "PySide6", "PyQt6", "pytest", "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="Dosidicus",
    debug=False, strip=False, upx=False, console=False,
    target_arch="universal2", codesign_identity=None, entitlements_file=None,
)
collection = COLLECT(exe, a.binaries, a.datas, name="Dosidicus", strip=False, upx=False)
app = BUNDLE(
    collection, name="Dosidicus.app",
    icon=str(root / "work/macos/Dosidicus.icns"),
    bundle_identifier="org.dosidicus.Dosidicus", version=version,
    info_plist={
        "CFBundleDisplayName": "Dosidicus",
        "CFBundleShortVersionString": version,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSLocalNetworkUsageDescription": "Find other squids for multiplayer on your local network.",
    },
)
