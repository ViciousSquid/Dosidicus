from pathlib import Path
import json
import sys
import zipfile


REQUIRED_SAVE_FILES = {
    "game_state.json",
    "brain_state.json",
    "ShortTerm.json",
    "LongTerm.json",
    "plugin_data.json",
    "statistics.json",
    "uuid.txt",
}


def validate_specimen(folder):
    errors = []

    if not folder.is_dir():
        errors.append("Specimen directory does not exist.")
        return errors

    # --------------------------------------------------
    # Exchange files
    # --------------------------------------------------

    for filename in ("README.md", "metadata.json"):
        if not (folder / filename).is_file():
            errors.append(f"Missing {filename}")

    # --------------------------------------------------
    # Metadata
    # --------------------------------------------------

    metadata_path = folder / "metadata.json"

    metadata = None

    if metadata_path.is_file():
        try:
            metadata = json.loads(
                metadata_path.read_text(encoding="utf-8")
            )

        except json.JSONDecodeError as exc:
            errors.append(
                f"metadata.json contains invalid JSON: {exc}"
            )

    if metadata is not None:
        if not metadata.get("name"):
            errors.append(
                "metadata.json is missing 'name'."
            )

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

    # --------------------------------------------------
    # Dosidicus save ZIP
    # --------------------------------------------------

    zip_files = list(folder.glob("*.zip"))

    if not zip_files:
        errors.append(
            "No exported Dosidicus save ZIP found."
        )

        return errors

    if len(zip_files) > 1:
        errors.append(
            "Multiple exported Dosidicus save ZIP files found."
        )

        return errors

    archive = zip_files[0]

    try:
        with zipfile.ZipFile(archive, "r") as z:

            # Check ZIP integrity
            bad_file = z.testzip()

            if bad_file is not None:
                errors.append(
                    f"Corrupt file inside ZIP: {bad_file}"
                )

            filenames = set(z.namelist())

            # Check actual Dosidicus save structure
            missing = REQUIRED_SAVE_FILES - filenames

            for filename in sorted(missing):
                errors.append(
                    f"Dosidicus save is missing {filename}"
                )

            # Validate JSON files
            for filename in REQUIRED_SAVE_FILES:
                if not filename.endswith(".json"):
                    continue

                if filename not in filenames:
                    continue

                try:
                    with z.open(filename) as file:
                        json.load(file)

                except json.JSONDecodeError as exc:
                    errors.append(
                        f"{filename} contains invalid JSON: {exc}"
                    )

    except zipfile.BadZipFile:
        errors.append(
            "Exported squid file is not a valid ZIP."
        )

    except Exception as exc:
        errors.append(
            f"Could not inspect exported squid: {exc}"
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
        print("SPECIMEN INVALID")
        print()

        for error in errors:
            print(f"  - {error}")

        return 1

    print("SPECIMEN VALID")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
