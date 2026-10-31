"""Noise injection: one noised copy of the golden set per (drift level, seed) (TS-3).

Run from the repo root (after `python -m src.golden`):

    python -m src.noise.inject

Two kinds of noise:
  - schema drift (TS-3.2): some headers renamed; depends on level and seed
  - carrier notes (TS-3.3): a free-text `carrier_notes` column; depends on the
    seed only, so every drift level of a seed has the same notes (D16)

For each variant it writes data/noised/{level}/{seed}/:
  noised.csv          golden rows, some headers renamed, plus carrier_notes
  header_map.json     ground truth for field mapping (TS-7.1)
  delay_facts.jsonl   ground truth for extraction, one line per row (TS-7.2)
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.contracts import DelayFact
from src.schema import CANONICAL_FIELDS

ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_CSV = ROOT / "data" / "golden" / "golden_500.csv"
NOISED_DIR = ROOT / "data" / "noised"
EXPERIMENT_YAML = ROOT / "config" / "experiment.yaml"
RENAME_POOL_YAML = Path(__file__).resolve().parent / "rename_pool.yaml"
NOTE_TEMPLATES_YAML = Path(__file__).resolve().parent / "note_templates.yaml"

BENIGN_NOTE_SHARE = 0.2  # rows with delay_days <= 0 that get a benign note (TS-3.3)
NOTES_STREAM = 1000  # keeps the notes generator separate from the header generator
NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
NUMERIC_FACT_FIELDS = ("delay_hours", "delay_days")

# Never renamed: the join key must survive (TS-3.2)
PROTECTED_FIELDS = ["order_id", "order_item_id"]
RENAMABLE_FIELDS = [f for f in CANONICAL_FIELDS if f not in PROTECTED_FIELDS]


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def level_name(level: float) -> str:
    """0.05 -> '05', 0.30 -> '30' (folder names sort correctly)."""
    return f"{round(level * 100):02d}"


def variant_rng(level: float, seed: int) -> np.random.Generator:
    return np.random.default_rng([seed, round(level * 100)])


def n_renamed(level: float) -> int:
    """Headers to rename at this level: round(level * 16) -> 1 / 2 / 5."""
    return round(level * len(CANONICAL_FIELDS))


def drift_headers(level: float, seed: int, pool: dict[str, list[str]]) -> dict[str, str]:
    """Pick which headers to rename and their new names: {canonical: noisy}."""
    rng = variant_rng(level, seed)
    chosen = rng.choice(RENAMABLE_FIELDS, size=n_renamed(level), replace=False)
    return {field: pool[field][rng.integers(len(pool[field]))] for field in sorted(chosen)}


def note_values(delay: int, rng: np.random.Generator, pools: dict) -> dict:
    """Placeholder values for one late row; numbers agree with its delay_days."""
    values = {name: str(rng.choice(options)) for name, options in pools.items()}
    values["days"] = delay
    values["days_word"] = NUMBER_WORDS[delay] if delay < len(NUMBER_WORDS) else str(delay)
    values["hours"] = int(rng.integers((delay - 1) * 24 + 1, delay * 24 + 1))  # rounds up to delay
    if delay >= 2:
        values["days1"] = int(rng.integers(1, delay))
        values["days2"] = delay - values["days1"]
    return values


def fill_facts(fact_templates: list[dict], values: dict) -> list[dict]:
    """Fill placeholders in a template's facts and validate them as DelayFacts."""
    facts = []
    for fact in fact_templates:
        filled = {}
        for key, value in fact.items():
            text = str(value).format(**values)
            filled[key] = int(text) if key in NUMERIC_FACT_FIELDS else text
        facts.append(DelayFact(**filled).model_dump(exclude_none=True))
    return facts


def make_note(delay: int, rng: np.random.Generator, templates: dict) -> tuple[str, list[dict], str | None]:
    """Return (note text, facts, template id) for one row."""
    if delay <= 0:
        if rng.random() < BENIGN_NOTE_SHARE:
            benign = templates["benign_templates"][rng.integers(len(templates["benign_templates"]))]
            return benign["template"], [], benign["id"]
        return "", [], None

    # Two-fact templates use {days1}/{days2}, so they need at least 2 days to split
    usable = [t for t in templates["delay_templates"] if delay >= 2 or "{days1}" not in t["template"]]
    template = usable[rng.integers(len(usable))]
    values = note_values(delay, rng, templates["value_pools"])
    return template["template"].format(**values), fill_facts(template["facts"], values), template["id"]


def make_notes(golden: pd.DataFrame, seed: int, templates: dict) -> tuple[list[str], list[dict]]:
    """Carrier notes for every golden row, plus one delay-facts record per row."""
    rng = np.random.default_rng([seed, NOTES_STREAM])
    notes, records = [], []
    for row in golden.to_dict("records"):
        delay = int(row["days_shipping_real"]) - int(row["days_shipping_scheduled"])
        note, facts, template_id = make_note(delay, rng, templates)
        notes.append(note)
        records.append({"order_item_id": int(row["order_item_id"]), "template_id": template_id, "delay_facts": facts})
    return notes, records


def make_variant(
    golden: pd.DataFrame, level: float, seed: int, pool: dict, templates: dict
) -> tuple[pd.DataFrame, dict, list[dict]]:
    """Return the noised rows, header-map ground truth and delay-facts ground truth."""
    renames = drift_headers(level, seed, pool)
    noised = golden.rename(columns=renames)
    notes, delay_facts = make_notes(golden, seed, templates)
    noised["carrier_notes"] = notes

    header_map = {
        "level": level,
        "seed": seed,
        "renamed": {noisy: canonical for canonical, noisy in renames.items()},
        # every data header in the noised file -> its canonical field (carrier_notes is extra)
        "header_map": {renames.get(f, f): f for f in CANONICAL_FIELDS},
    }
    return noised, header_map, delay_facts


def write_variant(noised: pd.DataFrame, header_map: dict, delay_facts: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    noised.to_csv(out_dir / "noised.csv", index=False, encoding="utf-8")
    with open(out_dir / "header_map.json", "w") as f:
        json.dump(header_map, f, indent=2)
    with open(out_dir / "delay_facts.jsonl", "w") as f:
        for record in delay_facts:
            f.write(json.dumps(record) + "\n")


def main() -> None:
    config = load_yaml(EXPERIMENT_YAML)
    pool = load_yaml(RENAME_POOL_YAML)
    templates = load_yaml(NOTE_TEMPLATES_YAML)
    golden = pd.read_csv(GOLDEN_CSV)

    for level in config["drift_levels"]:
        for seed in config["seeds"]:
            noised, header_map, delay_facts = make_variant(golden, level, seed, pool, templates)
            out_dir = NOISED_DIR / level_name(level) / str(seed)
            write_variant(noised, header_map, delay_facts, out_dir)
            renamed = ", ".join(f"{c} -> {n!r}" for n, c in header_map["renamed"].items())
            print(f"level {level_name(level)} seed {seed}: {renamed}")


if __name__ == "__main__":
    main()
