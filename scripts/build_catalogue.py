name: Squid Exchange Submission

on:
  issues:
    types: [opened, labeled]

jobs:
  process-submission:
    if: contains(github.event.issue.labels.*.name, 'squid-submission')

    runs-on: ubuntu-latest

    permissions:
      contents: write
      issues: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Read submission
        env:
          ISSUE_BODY: ${{ github.event.issue.body }}
        run: |
          python - <<'PY'
          import os
          import re

          body = os.environ["ISSUE_BODY"]

          def field(name):
              match = re.search(
                  rf"### {re.escape(name)}\s*\n+(.+?)(?=\n### |\Z)",
                  body,
                  re.DOTALL
              )

              if not match:
                  return ""

              value = match.group(1).strip()

              if value == "_No response_":
                  return ""

              return value

          nickname = field("Squid Nickname")
          save_url = field("Save File (.zip)")
          parent_id = field("Parent Specimen ID")
          description = field("About this squid")

          if not nickname:
              raise SystemExit(
                  "Squid nickname is required."
              )

          if not save_url:
              raise SystemExit(
                  "Save file URL is required."
              )

          url_match = re.search(
              r"\]\((https://github\.com/user-attachments/files/[^)]+)\)",
              save_url
          )

          if url_match:
              save_url = url_match.group(1)

          with open(
              os.environ["GITHUB_ENV"],
              "a"
          ) as env:

              env.write(
                  f"NICKNAME={nickname}\n"
              )

              env.write(
                  f"FILE_URL={save_url}\n"
              )

              env.write(
                  f"PARENT_ID={parent_id}\n"
              )

              env.write(
                  "DESCRIPTION<<EOF\n"
              )

              env.write(description)

              env.write(
                  "\nEOF\n"
              )

          print(
              f"Nickname: {nickname}"
          )

          print(
              f"Save URL: {save_url}"
          )

          print(
              f"Parent: {parent_id}"
          )
          PY

      - name: Determine generation
        run: |
          if [ -z "$PARENT_ID" ]; then
            echo "GENERATION=1" >> "$GITHUB_ENV"
            exit 0
          fi

          python - <<'PY'
          import json
          import os
          from pathlib import Path

          parent_id = os.environ["PARENT_ID"]

          for path in Path("squids").glob("*/metadata.json"):
              try:
                  data = json.loads(
                      path.read_text(
                          encoding="utf-8"
                      )
                  )

              except Exception:
                  continue

              if data.get(
                  "specimen_id"
              ) == parent_id:

                  generation = data.get(
                      "generation",
                      1
                  )

                  if not isinstance(
                      generation,
                      int
                  ):
                      raise SystemExit(
                          "Parent generation is invalid."
                      )

                  with open(
                      os.environ["GITHUB_ENV"],
                      "a"
                  ) as env:

                      env.write(
                          f"GENERATION={generation + 1}\n"
                      )

                  print(
                      f"Parent verified: {parent_id}"
                  )

                  print(
                      f"Generation: {generation + 1}"
                  )

                  break

          else:
              raise SystemExit(
                  f"Parent specimen not found: {parent_id}"
              )
          PY

      - name: Download squid
        run: |
          curl -L "$FILE_URL" -o squid.zip

          file squid.zip

      - name: Validate save
        run: |
          python - <<'PY'
          import zipfile

          required = {
              "game_state.json",
              "brain_state.json",
              "ShortTerm.json",
              "LongTerm.json",
              "statistics.json",
              "uuid.txt",
          }

          with zipfile.ZipFile(
              "squid.zip"
          ) as archive:

              names = set(
                  archive.namelist()
              )

              missing = (
                  required
                  - names
              )

              if missing:
                  raise SystemExit(
                      "Missing required files: "
                      + ", ".join(
                          sorted(missing)
                      )
                  )

              if archive.testzip() is not None:
                  raise SystemExit(
                      "ZIP contains corrupt data."
                  )

          print(
              "Dosidicus save is valid."
          )
          PY

      - name: Extract neural statistics
        run: |
          python - <<'PY'
          import json
          import zipfile

          with zipfile.ZipFile(
              "squid.zip",
              "r"
          ) as archive:

              with archive.open(
                  "brain_state.json"
              ) as file:

                  brain = json.load(file)

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

          functional_neurons = (
              enhanced_neurogenesis.get(
                  "functional_neurons",
                  {}
              )
          )

          statistics = {
              "neuron_count": len(
                  neuron_positions
              ),
              "neurons_generated": len(
                  functional_neurons
              ),
              "connection_count": len(
                  weights
              )
          }

          with open(
              "neural_statistics.json",
              "w"
          ) as file:

              json.dump(
                  statistics,
                  file,
                  indent=4
              )

          print(
              json.dumps(
                  statistics,
                  indent=2
              )
          )
          PY

      - name: Read UUID
        run: |
          UUID=$(unzip -p squid.zip uuid.txt | head -n 1 | xargs)

          if [ -z "$UUID" ]; then
            echo "UUID is empty."
            exit 1
          fi

          echo "UUID=$UUID" >> "$GITHUB_ENV"

      - name: Create specimen
        run: |
          DIRECTORY="squids/$NICKNAME"

          if [ -e "$DIRECTORY" ]; then
            echo "A squid with this name already exists."
            exit 1
          fi

          mkdir -p "$DIRECTORY"

          cp squid.zip \
            "$DIRECTORY/${NICKNAME}_${UUID}.zip"

          python - <<'PY'
          import json
          import os
          from pathlib import Path

          directory = (
              Path("squids")
              / os.environ["NICKNAME"]
          )

          statistics = json.loads(
              Path(
                  "neural_statistics.json"
              ).read_text(
                  encoding="utf-8"
              )
          )

          name = os.environ["NICKNAME"]
          uuid = os.environ["UUID"]

          specimen_id = (
              f"dosidicus-{uuid}"
          )

          description = os.environ.get(
              "DESCRIPTION",
              ""
          ).strip()

          raised_by = (
              "@"
              + os.environ.get(
                  "GITHUB_ACTOR",
                  "unknown"
              )
          )

          parent_id = (
              os.environ["PARENT_ID"]
              or None
          )

          generation = int(
              os.environ["GENERATION"]
          )

          metadata = {
              "name": name,
              "specimen_id": specimen_id,
              "description": description,
              "raised_by": raised_by,
              "parent_id": parent_id,
              "generation": generation,
              "neuron_count": statistics[
                  "neuron_count"
              ],
              "neurons_generated": statistics[
                  "neurons_generated"
              ],
              "connection_count": statistics[
                  "connection_count"
              ]
          }

          (
              directory
              / "metadata.json"
          ).write_text(
              json.dumps(
                  metadata,
                  indent=4
              )
              + "\n",
              encoding="utf-8"
          )

          manifest = {
              "format": "dosidicus-squid-exchange",
              "version": 1,
              "specimen_id": specimen_id,
              "archive": (
                  f"{name}_{uuid}.zip"
              ),
              "verified": True
          }

          (
              directory
              / "manifest.json"
          ).write_text(
              json.dumps(
                  manifest,
                  indent=4
              )
              + "\n",
              encoding="utf-8"
          )

          readme = f"""# {name}

          ## Squid Exchange Specimen

          **Specimen ID:** `{specimen_id}`

          **Raised by:** {raised_by}

          **Generation:** {generation}

          **Parent:** {parent_id or "None"}

          ## Neural Statistics

          - **Neurons:** {statistics["neuron_count"]}
          - **Neurons generated:** {statistics["neurons_generated"]}
          - **Connections:** {statistics["connection_count"]}

          ## Description

          {description or "No description provided."}

          This specimen was automatically verified and added to the Dosidicus Squid Exchange.
          """

          (
              directory
              / "README.md"
          ).write_text(
              readme,
              encoding="utf-8"
          )
          PY

      - name: Update catalogue
        run: |
          python scripts/build_catalogue.py

      - name: Commit specimen
        run: |
          git config user.name "SquidBot"
          git config user.email "bot@github.com"

          git add squids/ README.md

          git commit \
            -m "Add Squid Exchange specimen: $NICKNAME"

          git push

      - name: Close submission
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ISSUE_NUMBER: ${{ github.event.issue.number }}
        run: |
          gh issue comment "$ISSUE_NUMBER" --body \
            "🦑 **Squid accepted!**

          **Name:** $NICKNAME

          **Specimen ID:** \`dosidicus-$UUID\`

          **Generation:** $GENERATION

          **Parent:** ${PARENT_ID:-None}

          The squid has been added to the Squid Exchange."

          gh issue close "$ISSUE_NUMBER"
