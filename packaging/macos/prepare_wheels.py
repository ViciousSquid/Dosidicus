"""Fuse matching upstream Intel/ARM wheels before PyInstaller universal2 analysis."""

from pathlib import Path
import shutil
import subprocess
import sys

from delocate.fuse import fuse_wheels

PAIRED = ("PyQt5==5.15.11", "PyQt5-Qt5==5.15.16", "numpy==2.2.6")
SIP = "PyQt5-sip==12.17.0"


def download(requirement, platform, destination):
    subprocess.run([
        sys.executable, "-m", "pip", "download", "--no-deps", "--only-binary=:all:",
        "--python-version", "311", "--implementation", "cp",
        "--abi", "cp311", "--abi", "abi3", "--abi", "none",
        "--platform", platform, "--dest", str(destination), requirement,
    ], check=True)


def main():
    root = Path("work/macos/wheels").resolve()
    if root.exists():
        shutil.rmtree(root)
    universal = root / "universal"
    universal.mkdir(parents=True)
    for index, requirement in enumerate(PAIRED):
        wheels = []
        for arch in ("x86_64", "arm64"):
            folder = root / str(index) / arch
            folder.mkdir(parents=True)
            download(requirement, f"macosx_11_0_{arch}", folder)
            wheel, = folder.glob("*.whl")
            wheels.append(wheel)
        fuse_wheels(wheels[0], wheels[1], universal)
    download(SIP, "macosx_11_0_universal2", universal)
    subprocess.run([
        sys.executable, "-m", "pip", "install", "--no-index", "--no-deps",
        "--force-reinstall", *map(str, sorted(universal.glob("*.whl"))),
    ], check=True)
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)


if __name__ == "__main__":
    main()
