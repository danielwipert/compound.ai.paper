"""Download the DataCo CSV and prepare a clean 16-column copy (TS-2.1, TS-2.2).

Run from the repo root:

    python -m src.data_prep

Steps:
  1. Download DataCoSupplyChainDataset.csv from Mendeley into data/raw/
     (skipped if already there) and check its SHA-256 hash.
  2. Read it as latin-1, check the 16 headers match TS-2.2 exactly.
  3. Keep only those 16 columns, rename to canonical names, convert dates
     to ISO format, and write data/raw/dataco_clean.csv as UTF-8.

Both files live in data/raw/, which is git-ignored; this script recreates them.
"""

import hashlib
import shutil
import urllib.request
from pathlib import Path

import pandas as pd

from src.schema import CANONICAL_FIELDS, COLUMNS, DATACO_TO_CANONICAL

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
RAW_CSV = RAW_DIR / "DataCoSupplyChainDataset.csv"
CLEAN_CSV = RAW_DIR / "dataco_clean.csv"

# Mendeley Data, DOI 10.17632/8gx2fvg2k6.5 (version 5), licence CC BY 4.0
DOWNLOAD_URL = (
    "https://data.mendeley.com/public-files/datasets/8gx2fvg2k6/files/"
    "72784be5-36d3-44fe-b75d-0edbf1999f65/file_downloaded"
)
EXPECTED_SHA256 = "fa6d022ed437155e1a2f0378710602848703c8a7f203f7ff5d77805bf8480aa6"
EXPECTED_ROWS = 180_519
EXPECTED_COLUMNS = 53

# DataCo dates look like "1/31/2018 22:56"
DATACO_DATE_FORMAT = "%m/%d/%Y %H:%M"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(dest: Path = RAW_CSV) -> Path:
    """Download the raw CSV if missing, then verify its hash."""
    if dest.exists():
        print(f"Already downloaded: {dest}")
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading DataCo CSV (~96 MB) to {dest} ...")
        tmp = dest.with_suffix(".part")
        # Mendeley rejects Python's default User-Agent with 403
        request = urllib.request.Request(
            DOWNLOAD_URL, headers={"User-Agent": "compound-ai-benchmark/0.1"}
        )
        with urllib.request.urlopen(request) as response, open(tmp, "wb") as out:
            shutil.copyfileobj(response, out)
        tmp.rename(dest)

    actual = sha256_of(dest)
    if actual != EXPECTED_SHA256:
        raise ValueError(
            f"SHA-256 mismatch for {dest}: got {actual}, expected {EXPECTED_SHA256}. "
            "Delete the file and run again."
        )
    print("SHA-256 hash OK")
    return dest


def check_headers(headers: list[str]) -> None:
    """Every TS-2.2 header must be present, byte-for-byte."""
    missing = [h for _, h, _ in COLUMNS if h not in headers]
    if missing:
        raise ValueError(f"DataCo headers not found: {missing}")


def prepare(raw: pd.DataFrame) -> pd.DataFrame:
    """Keep the 16 columns, rename to canonical, convert dates to ISO strings."""
    check_headers(list(raw.columns))
    df = raw[list(DATACO_TO_CANONICAL)].rename(columns=DATACO_TO_CANONICAL)

    for canonical, _, kind in COLUMNS:
        if kind == "datetime":
            parsed = pd.to_datetime(df[canonical], format=DATACO_DATE_FORMAT)
            df[canonical] = parsed.dt.strftime("%Y-%m-%dT%H:%M")

    if not df["order_item_id"].is_unique:
        raise ValueError("order_item_id is not unique")
    if df.isna().any().any():
        raise ValueError("Unexpected nulls in the 16 columns")
    return df[CANONICAL_FIELDS]


def main() -> None:
    raw_path = download()
    raw = pd.read_csv(raw_path, encoding="latin-1")
    if raw.shape != (EXPECTED_ROWS, EXPECTED_COLUMNS):
        raise ValueError(f"Unexpected shape {raw.shape}")

    clean = prepare(raw)
    clean.to_csv(CLEAN_CSV, index=False, encoding="utf-8")
    print(f"Wrote {len(clean):,} rows x {clean.shape[1]} columns to {CLEAN_CSV}")


if __name__ == "__main__":
    main()
