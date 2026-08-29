from pathlib import Path
import json
import sys
import zipfile


def validate_specimen(folder):
    errors = []

    if not folder.is_dir():
        errors.append("Specimen directory does not exist.")
        return errors

    # Required files
    for filename in ("README.md", "metadata.json"):
        if not (folder / filename).is_file():
            errors.append(f"Missing {filename}")

    # Export ZIP
    zip_files = list(folder.glob("*.zip"))

    if not zip_files:
        errors.append("No exported squid ZIP found.")

    elif len(zip_files) > 1:
        errors.append("Multiple exported squid ZIP files found.")

    else:
        archive = zip_files[0]

        try:
            with zipfile.ZipFile(archive, "r") as z:
                if z.testzip() is not None:
                    errors.append("Exported squid ZIP is corrupt.")

        except zipfile.BadZipFile:
            errors.append("Exported squid ZIP is not a valid ZIP file.")

    # Metadata
    metadata_path = folder / "metadata.json"

    if metadata_path.is_file():
        try:
            metadata = json.loads(
                metadata_path.read_text(encoding="utf-8")
            )

            if not metadata.get("name"):
                errors.append("metadata.json is missing 'name'.")

            if not metadata.get("specimen_id"):
                errors.append(
                    "metadata.json is missing 'specimen_id'."
                )

            if "generation" not in metadata:
                errors.append(
                    "metadata.json is missing 'generation'."
                )

            if "parent_id" not in metadata:
                errors.append(
                    "metadata.json is missing 'parent_id'."
                )

        except json.JSONDecodeError as exc:
            errors.append(
                f"metadata.json contains invalid JSON: {exc}"
            )

    return errors


def main():
    if len(sys.argv) != 2:
        print(
            "Usage: python scripts/validate_specimen.py "
            "<specimen directory>"
        )
        return 1

    folder = Path(sys.argv[1])

    errors = validate_specimen(folder)

    if errors:
        print("❌ SPECIMEN INVALID")
        print()

        for error in errors:
            print(f"  - {error}")

        return 1

    print("✅ SPECIMEN VALID")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
