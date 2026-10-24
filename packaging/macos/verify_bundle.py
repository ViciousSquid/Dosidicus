"""Reject any shipped Mach-O lacking either required architecture."""

from pathlib import Path
import subprocess
import sys

MACHO_MAGIC = {
    b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca",
}


def verify(bundle):
    count = 0
    for path in sorted(bundle.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as stream:
            if stream.read(4) not in MACHO_MAGIC:
                continue
        arches = subprocess.check_output(["lipo", "-archs", str(path)], text=True).split()
        if not {"x86_64", "arm64"}.issubset(arches):
            raise SystemExit(f"Not universal2: {path}: {arches}")
        count += 1
    if count == 0:
        raise SystemExit("No Mach-O files found")
    if not list(bundle.rglob("libqcocoa.dylib")):
        raise SystemExit("Qt Cocoa platform plugin is missing")
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(bundle)], check=True)
    print(f"Verified {count} universal2 native files and the app signature")


if __name__ == "__main__":
    verify(Path(sys.argv[1]).resolve(strict=True))
