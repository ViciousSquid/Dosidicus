from pathlib import Path
import json
import zipfile
import sys


def extract_brain_statistics(zip_path):
    """
    Read brain_state.json from a Dosidicus save ZIP
    and return basic neural statistics.
    """

    with zipfile.ZipFile(zip_path, "r") as archive:

        if "brain_state.json" not in archive.namelist():
            raise ValueError(
                "Dosidicus save does not contain brain_state.json"
            )

        with archive.open("brain_state.json") as file:
            brain = json.load(file)

    # --------------------------------------------------
    # Current neuron count
    # --------------------------------------------------

    neuron_positions = brain.get(
        "neuron_positions",
        {}
    )

    neuron_count = len(neuron_positions)

    # --------------------------------------------------
    # Generated neurons
    # --------------------------------------------------

    enhanced = brain.get(
        "enhanced_neurogenesis",
        {}
    )

    functional_neurons = enhanced.get(
        "functional_neurons",
        {}
    )

    neurons_generated = len(
        functional_neurons
    )

    # --------------------------------------------------
    # Connection count
    # --------------------------------------------------

    weights = brain.get(
        "weights_list",
        []
    )

    connection_count = len(weights)

    # --------------------------------------------------
    # Result
    # --------------------------------------------------

    return {
        "neuron_count": neuron_count,
        "neurons_generated": neurons_generated,
        "connection_count": connection_count
    }


def main():
    if len(sys.argv) != 2:
        print(
            "Usage: python scripts/extract_metadata.py "
            "<squid.zip>"
        )
        return 1

    zip_path = Path(sys.argv[1])

    if not zip_path.is_file():
        print(
            f"File not found: {zip_path}"
        )
        return 1

    try:
        statistics = extract_brain_statistics(
            zip_path
        )

    except Exception as exc:
        print(
            f"Could not read squid: {exc}"
        )
        return 1

    print(
        json.dumps(
            statistics,
            indent=4
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
