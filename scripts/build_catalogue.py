from pathlib import Path
import json

SQUIDS_DIR = Path("squids")
README_PATH = Path("README.md")

BEGIN_MARKER = "<!-- BEGIN CATALOGUE -->"
END_MARKER = "<!-- END CATALOGUE -->"


def get_specimens():
    specimens = []

    if not SQUIDS_DIR.exists():
        return specimens

    for folder in sorted(SQUIDS_DIR.iterdir(), key=lambda p: p.name.lower()):
        if not folder.is_dir():
            continue

        metadata = {}

        metadata_file = folder / "metadata.json"

        if metadata_file.exists():
            try:
                metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"Warning: Could not read {metadata_file}: {e}")

        specimens.append({
            "name": metadata.get("name", folder.name),
            "description": metadata.get("description", ""),
            "path": folder.as_posix(),
            "has_zip": any(folder.glob("*.zip"))
        })

    return specimens


def generate_catalogue(specimens):
    lines = []

    if not specimens:
        lines.append("_No specimens currently available in the catalogue._")
    else:
        lines.append("| Specimen | Description | Archive |")
        lines.append("| :--- | :--- | :---: |")

        for spec in specimens:
            archive = "✅" if spec["has_zip"] else "—"

            lines.append(
                f"| **[{spec['name']}]({spec['path']})** | "
                f"{spec['description']} | "
                f"{archive} |"
            )

    return "\n".join(lines)


def update_readme(catalogue):
    if not README_PATH.exists():
        raise FileNotFoundError(f"{README_PATH} not found.")

    readme = README_PATH.read_text(encoding="utf-8")

    start = readme.find(BEGIN_MARKER)
    end = readme.find(END_MARKER)

    if start == -1 or end == -1:
        raise RuntimeError(
            "README.md is missing the catalogue markers:\n"
            "<!-- BEGIN CATALOGUE -->\n"
            "<!-- END CATALOGUE -->"
        )

    start += len(BEGIN_MARKER)

    new_readme = (
        readme[:start]
        + "\n\n"
        + catalogue
        + "\n\n"
        + readme[end:]
    )

    README_PATH.write_text(new_readme, encoding="utf-8")


def main():
    specimens = get_specimens()

    catalogue = generate_catalogue(specimens)

    update_readme(catalogue)

    print(f"Updated README.md with {len(specimens)} specimen(s).")


if __name__ == "__main__":
    main()
