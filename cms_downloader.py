from __future__ import annotations

import json
import time
from pathlib import Path

import certifi
import pandas as pd
import requests

from config import CMS_API_URL, CMS_BATCH_SIZE, CMS_FILE, CMS_MIN_EXPECTED_ROWS


def _extract_rows(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("results", "data", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def download_complete_cms(output_path: Path = CMS_FILE, force: bool = True) -> Path:
    """Download every CMS row with API pagination.

    CMS limits each response to about 1,500 records. This function increments
    the offset until the API returns no additional rows.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not force:
        existing = pd.read_csv(output_path, dtype=str, low_memory=False)
        if len(existing) >= CMS_MIN_EXPECTED_ROWS:
            print(f"Using complete local CMS file with {len(existing):,} rows.")
            return output_path

    session = requests.Session()
    session.headers.update({"User-Agent": "HospitalQualityProject/4.0"})
    rows: list[dict[str, object]] = []
    offset = 0

    print("Downloading complete CMS Hospital General Information dataset...")
    while True:
        params = {"offset": offset, "limit": CMS_BATCH_SIZE}
        response = session.get(CMS_API_URL, params=params, timeout=120, verify=certifi.where())
        response.raise_for_status()
        batch = _extract_rows(response.json())
        if not batch:
            break
        rows.extend(batch)
        print(f"  Downloaded {len(rows):,} rows...")
        if len(batch) < CMS_BATCH_SIZE:
            break
        offset += CMS_BATCH_SIZE
        time.sleep(0.2)

    if len(rows) < CMS_MIN_EXPECTED_ROWS:
        raise RuntimeError(
            f"CMS download returned only {len(rows):,} rows. "
            "The API may be unavailable or the response format may have changed. "
            "Download the full CSV from the official CMS Provider Data Catalog and save it as "
            f"{output_path}."
        )

    data = pd.DataFrame(rows)
    data.to_csv(output_path, index=False)
    print(f"Saved {len(data):,} CMS hospitals to {output_path}")
    return output_path
