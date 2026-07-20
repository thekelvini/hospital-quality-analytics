import io
import json
import re
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config import CMS_DATASET_PAGE, CMS_LOCAL_FILE
from utils import find_column, normalize_ccn

HEADERS = {"User-Agent": "Mozilla/5.0 HospitalQualityAcademicProject/1.0"}


def _read_csv_bytes(content: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(content), dtype=str, low_memory=False)


def _candidate_urls_from_page() -> list[str]:
    response = requests.get(CMS_DATASET_PAGE, headers=HEADERS, timeout=60)
    response.raise_for_status()
    urls: list[str] = []
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup.find_all(["a", "script"]):
        value = tag.get("href") or tag.get("src") or ""
        if ".csv" in value.lower():
            urls.append(urljoin(CMS_DATASET_PAGE, value))
    for match in re.findall(r'https?://[^"\\s]+?\.csv(?:\?[^"\\s]*)?', response.text):
        urls.append(match.replace("\\u0026", "&"))
    # CMS bulk data endpoint pattern. This endpoint has been stable across Provider Data Catalog releases.
    urls.extend([
        "https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0?offset=0&count=true&results=true",
        "https://data.cms.gov/provider-data/sites/default/files/resources/csv/Hospital_General_Information.csv",
    ])
    return list(dict.fromkeys(urls))


def _download_from_api(url: str) -> pd.DataFrame | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=90)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "csv" in content_type or url.lower().endswith(".csv"):
            df = _read_csv_bytes(response.content)
            return df if len(df.columns) > 5 else None
        payload = response.json()
        rows = payload.get("results") or payload.get("data")
        if rows:
            return pd.DataFrame(rows)
    except Exception:
        return None
    return None


def load_cms() -> pd.DataFrame:
    if CMS_LOCAL_FILE.exists():
        raw = pd.read_csv(CMS_LOCAL_FILE, dtype=str, low_memory=False)
    else:
        raw = None
        for url in _candidate_urls_from_page():
            raw = _download_from_api(url)
            if raw is not None and len(raw) > 100:
                break
        if raw is None:
            raise RuntimeError(
                "CMS download failed. Download Hospital General Information from the CMS Provider Data Catalog and save it as data/cms_hospital_general_information.csv."
            )
        raw.to_csv(CMS_LOCAL_FILE, index=False)

    ccn_col = find_column(raw.columns, ["facility", "id"])
    name_col = find_column(raw.columns, ["facility", "name"])
    state_col = find_column(raw.columns, ["state"])
    rating_col = find_column(raw.columns, ["overall", "rating"])

    out = raw[[ccn_col, name_col, state_col, rating_col]].copy()
    out.columns = ["CCN", "CMS_Hospital_Name", "CMS_State", "CMS_Star_Rating"]
    out["CCN"] = out["CCN"].map(normalize_ccn)
    out["CMS_Star_Rating"] = pd.to_numeric(out["CMS_Star_Rating"], errors="coerce")
    out = out.drop_duplicates("CCN", keep="first")
    return out
