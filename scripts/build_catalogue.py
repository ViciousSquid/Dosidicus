from pathlib import Path
import json
import zipfile


SQUIDS_DIR = Path("squids")
README_PATH = Path("README.md")

BEGIN_MARKER = "<!-- BEGIN CATALOGUE -->"
END_MARKER = "<!-- END CATALOGUE -->"


def get_brain_statistics(zip_path):
    """
    Read brain_state.json from a Dosidicus save ZIP
    and extract basic neural statistics.
    """

    try:
        with zipfile.ZipFile(zip_path, "r") as archive:

            if "brain_state.json" not in archive.namelist():
                return {
                    "neuron_count": "—",
                    "neurons_generated": "—",
                    "connection_count": "—"
                }

            with archive.open("brain_state.json") as file:
                brain = json.load(file)

    except Exception:
        return {
            "neuron_count": "—",
            "neurons_generated": "—",
            "connection_count": "—"
        }

    neuron_positions = brain.get(
        "neuron_positions",
        {}
    )

    weights = brain.get(
        "weights_list",
        []
    )

    enhanced_neurogenesis = brain.get(
        "enhanced_neurogenesis",
        {}
    )

    functional_neurons = enhanced_neurogenesis.get(
        "functional_neurons",
        {}
    )

    return {
        "neuron_count": len(neuron_positions),
        "neurons_generated": len(functional_neurons),
        "connection_count": len(weights)
    }


def escape_table_text(value):
    """
    Prevent user-provided text from breaking the
    Markdown catalogue table.
    """

    if value is None:
        return ""

    return str(value).replace("|", "\\|").replace(
        "\n",
        " "
    ).strip()


def get_specimens():
    specimens = []

    if not SQUIDS_DIR.exists():
        return specimens

    for folder in sorted(
        SQUIDS_DIR.iterdir(),
        key=lambda p: p.name.lower()
    ):

        if not folder.is_dir():
            continue

        metadata = {}

        metadata_file = folder / "metadata.json"

        if metadata_file.exists():

            try:
                metadata = json.loads(
                    metadata_file.read_text(
                        encoding="utf-8"
                    )
                )

            except Exception as exc:

                print(
                    f"Warning: Could not read "
                    f"{metadata_file}: {exc}"
                )

        zip_files = sorted(
            folder.glob("*.zip")
        )

        if zip_files:

            zip_path = zip_files[0]

            brain_statistics = get_brain_statistics(
                zip_path
            )

            has_zip = True

            archive_path = zip_path.as_posix()

        else:

            brain_statistics = {
                "neuron_count": "—",
                "neurons_generated": "—",
                "connection_count": "—"
            }

            has_zip = False
            archive_path = ""

        specimens.append(
            {
                "name": metadata.get(
                    "name",
                    folder.name
                ),

                "specimen_id": metadata.get(
                    "specimen_id",
                    "—"
                ),

                "description": metadata.get(
                    "description",
                    ""
                ),

                "raised_by": metadata.get(
                    "raised_by",
                    "—"
                ),

                "generation": metadata.get(
                    "generation",
                    "—"
                ),

                "neuron_count": brain_statistics[
                    "neuron_count"
                ],

                "neurons_generated": brain_statistics[
                    "neurons_generated"
                ],

                "connection_count": brain_statistics[
                    "connection_count"
                ],

                "path": folder.as_posix(),

                "archive_path": archive_path,

                "has_zip": has_zip
            }
        )

    return specimens


def generate_catalogue(specimens):
    lines = []

    if not specimens:

        lines.append(
            "_No specimens currently available "
            "in the catalogue._"
        )

        return "\n".join(lines)

    lines.append(
        "| Specimen | Generation | Neurons | "
        "Grown | Connections | Description | Archive |"
    )

    lines.append(
        "| :--- | ---: | ---: | ---: | "
        "---: | :--- | :---: |"
    )

    for spec in specimens:

        archive = "—"

        if spec["has_zip"]:

            archive = (
                f"[ZIP]({spec['archive_path']})"
            )

        grown = spec["neurons_generated"]

        if isinstance(grown, int):
            grown = f"+{grown}"

        name = escape_table_text(
            spec["name"]
        )

        description = escape_table_text(
            spec["description"]
        )

        lines.append(
            f"| **[{name}]"
            f"({spec['path']})** "
            f"| {spec['generation']} "
            f"| {spec['neuron_count']} "
            f"| {grown} "
            f"| {spec['connection_count']} "
            f"| {description} "
            f"| {archive} |"
        )

    return "\n".join(lines)


def update_readme(catalogue):

    if not README_PATH.exists():

        raise FileNotFoundError(
            f"{README_PATH} not found."
        )

    readme = README_PATH.read_text(
        encoding="utf-8"
    )

    start = readme.find(
        BEGIN_MARKER
    )

    end = readme.find(
        END_MARKER
    )

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

    README_PATH.write_text(
        new_readme,
        encoding="utf-8"
    )


def main():

    specimens = get_specimens()

    catalogue = generate_catalogue(
        specimens
    )

    update_readme(
        catalogue
    )

    print(
        f"Updated README.md with "
        f"{len(specimens)} specimen(s)."
    )


if __name__ == "__main__":
    main()
