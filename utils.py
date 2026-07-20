from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import pandas as pd


def ensure_directories(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def normalize_ccn(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = re.sub(r"\D", "", str(value).strip())
    if not text:
        return ""
    return text.zfill(6)[-6:]


def normalize_state(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().upper()


def normalize_name(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).upper().strip()
    replacements = {
        "&": " AND ", "SAINT": "ST", "ST.": "ST", "THE ": "",
        "MEDICAL CENTER": "MED CTR", "MEDICAL CENTRE": "MED CTR",
        "HEALTHCARE SYSTEM": "", "HEALTH SYSTEM": "", "HOSPITAL SYSTEM": "",
        "INCORPORATED": "", " INC ": " ", " LLC ": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    stop = {"OF", "THE", "AT"}
    tokens = [t for t in text.split() if t not in stop]
    return " ".join(tokens)


def parse_money(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(r"[$,]", "", regex=True)
        .str.replace(r"^\s*$", "", regex=True)
        .replace({"nan": pd.NA, "None": pd.NA, "N/A": pd.NA})
    )
    return pd.to_numeric(cleaned, errors="coerce")


def find_column(columns: Iterable[object], aliases: list[str]) -> str | None:
    normalized = {re.sub(r"[^a-z0-9]", "", str(c).lower()): str(c) for c in columns}
    for alias in aliases:
        key = re.sub(r"[^a-z0-9]", "", alias.lower())
        if key in normalized:
            return normalized[key]
    return None


def find_existing_file(folder: Path, names: list[str]) -> Path | None:
    for name in names:
        candidate = folder / name
        if candidate.exists():
            return candidate
    for candidate in folder.iterdir() if folder.exists() else []:
        low = candidate.name.lower()
        if candidate.is_file() and "blue" in low and "distinction" in low and "spine" in low:
            return candidate
    return None
