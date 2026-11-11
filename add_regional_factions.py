"""Register the newly independent regional factions without changing territory."""
from __future__ import annotations

import utils.http_session
import utils.transport
import utils.session
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CAMPAIGN = ROOT / "campaign.json"

FACTIONS = [
    ("Balcoth", "#6E1E24"),
    ("Haerrim", "#B65A2A"),
    ("Feredrim", "#4F7A4E"),
    ("Beorings", "#8A6A2E"),
    ("Eotheod", "#5A8FC8"),
    ("GreenWood", "#246B47"),
    ("Drudain", "#71412F"),
    ("Northern Endwaith", "#4C5963"),
    ("Southern Endwaith", "#8B6B3C"),
]


def main() -> None:
    state = json.loads(CAMPAIGN.read_text(encoding="utf-8"))
    ids = {faction["id"] for faction in state["factions"]}
    added = []
    for faction_id, colour in FACTIONS:
        if faction_id in ids:
            continue
        state["factions"].append({"id": faction_id, "name": faction_id, "color": colour,
                                  "treasury": 5000, "capital": "", "zeal": 6})
        added.append(faction_id)
    state["order"] = sorted(set(state["order"]) | {name for name, _ in FACTIONS}, key=str.casefold)
    CAMPAIGN.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Added: " + (", ".join(added) if added else "none (already present)"))


if __name__ == "__main__":
    main()
