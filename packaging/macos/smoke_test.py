"""Launch the mounted DMG's app from an unrelated directory and a fresh data store."""

from pathlib import Path
import os
import subprocess
import sys
import tempfile


def main():
    bundle = Path(sys.argv[1]).resolve(strict=True)
    architecture = sys.argv[2]
    with tempfile.TemporaryDirectory(prefix="dosidicus-macos-smoke-") as temporary:
        root = Path(temporary)
        env = dict(os.environ, DOSIDICUS_SMOKE_DATA_DIR=str(root / "data"))
        result = subprocess.run([
            "arch", f"-{architecture}", str(bundle / "Contents/MacOS/Dosidicus"),
            "--smoke-test",
        ], cwd=root, env=env, capture_output=True, text=True, timeout=90)
        console = root / "data/logs/console.log"
        output = result.stdout + result.stderr
        if console.exists():
            output += console.read_text(errors="replace")
        print(output)
        if result.returncode or "DOSIDICUS_SMOKE_OK" not in output:
            raise SystemExit(f"Startup failed for {architecture}: {result.returncode}")
        for required in ("config.ini", "images/poop1.png", "saves", "_memory", "logs"):
            if not (root / "data" / required).exists():
                raise SystemExit(f"Runtime data missing: {required}")
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(bundle)], check=True)


if __name__ == "__main__":
    main()
