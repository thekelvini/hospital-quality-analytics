from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber


DATA_DIR = Path("data")

POSSIBLE_PDF_NAMES = [
    "Blue_Distinction_Spine_Surgery.pdf",
    "Blue_Distinction_Spine_Surgery.pdf.pdf",
    "Blue-Distinction-Spine-Surgery-Providers.pdf",
]


STATE_ABBREVIATIONS = {
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "DC",
}


def clean_text(value: object) -> str:
    """Convert extracted PDF content into clean text."""

    if value is None:
        return ""

    text = str(value)

    text = text.replace("\n", " ")
    text = text.replace("\r", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_hospital_name(value: object) -> str:
    """Create a standardized hospital name for matching."""

    text = clean_text(value).upper()

    replacements = {
        "&": " AND ",
        "SAINT": "ST",
        "ST.": "ST",
        "MEDICAL CENTER": "MED CTR",
        "MEDICAL CENTRE": "MED CTR",
        "HEALTH SYSTEM": "",
        "HEALTHCARE SYSTEM": "",
        "THE ": "",
    }

    for old_value, new_value in replacements.items():
        text = text.replace(old_value, new_value)

    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def find_local_pdf() -> Path:
    """Find the Blue Distinction PDF inside the data folder."""

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for filename in POSSIBLE_PDF_NAMES:
        candidate = DATA_DIR / filename

        if candidate.exists():
            print(f"Using local BCBS PDF: {candidate}")
            return candidate

    pdf_files = list(DATA_DIR.glob("*.pdf"))

    for candidate in pdf_files:
        filename_lower = candidate.name.lower()

        if (
            "blue" in filename_lower
            and "distinction" in filename_lower
            and "spine" in filename_lower
        ):
            print(f"Using local BCBS PDF: {candidate}")
            return candidate

    expected_location = (
        DATA_DIR / "Blue_Distinction_Spine_Surgery.pdf"
    )

    raise FileNotFoundError(
        "\nThe Blue Distinction Spine Surgery PDF was not found.\n"
        "Place the PDF inside the data folder.\n"
        f"Expected location: {expected_location.resolve()}\n"
    )


def detect_designation(row_text: str) -> str:
    """Identify whether a row represents BDC or BDC+."""

    text = row_text.upper()

    if (
        "BDC+" in text
        or "BDC +" in text
        or "CENTER+" in text
        or "CENTER +" in text
    ):
        return "BDC+"

    if (
        "BDC" in text
        or "BLUE DISTINCTION CENTER" in text
    ):
        return "BDC"

    return ""


def detect_state(values: list[str]) -> str:
    """Find a two-letter state abbreviation in an extracted row."""

    for value in values:
        candidate = clean_text(value).upper()

        if candidate in STATE_ABBREVIATIONS:
            return candidate

        state_matches = re.findall(
            r"\b[A-Z]{2}\b",
            candidate,
        )

        for state in state_matches:
            if state in STATE_ABBREVIATIONS:
                return state

    return ""


def is_header_row(values: list[str]) -> bool:
    """Determine whether a PDF row is a table header."""

    row_text = " ".join(values).lower()

    header_terms = [
        "facility name",
        "hospital name",
        "provider name",
        "city",
        "state",
        "designation",
        "blue distinction",
    ]

    matches = sum(
        term in row_text
        for term in header_terms
    )

    return matches >= 2


def identify_hospital_name(values: list[str]) -> str:
    """Select the most likely hospital name from a table row."""

    excluded_terms = [
        "BDC",
        "BDC+",
        "BLUE DISTINCTION",
        "CENTER",
        "CENTRE",
    ]

    candidates = []

    for value in values:
        text = clean_text(value)

        if not text:
            continue

        upper_text = text.upper()

        if upper_text in STATE_ABBREVIATIONS:
            continue

        if re.fullmatch(r"\d{5}(?:-\d{4})?", text):
            continue

        if re.fullmatch(r"\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}", text):
            continue

        if any(
            upper_text == term
            for term in excluded_terms
        ):
            continue

        score = len(text)

        hospital_terms = [
            "HOSPITAL",
            "MEDICAL",
            "HEALTH",
            "CLINIC",
            "CENTER",
            "CENTRE",
            "UNIVERSITY",
            "REGIONAL",
            "MEMORIAL",
        ]

        if any(
            term in upper_text
            for term in hospital_terms
        ):
            score += 100

        candidates.append(
            (score, text)
        )

    if not candidates:
        return ""

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return candidates[0][1]


def identify_city(
    values: list[str],
    hospital_name: str,
    state: str,
) -> str:
    """Select a likely city value from a table row."""

    for value in values:
        text = clean_text(value)

        if not text:
            continue

        if text == hospital_name:
            continue

        if text.upper() == state:
            continue

        if re.fullmatch(r"\d{5}(?:-\d{4})?", text):
            continue

        if detect_designation(text):
            continue

        if (
            len(text) <= 40
            and re.fullmatch(
                r"[A-Za-z .'-]+",
                text,
            )
        ):
            return text

    return ""


def parse_pdf_tables(
    pdf_path: Path,
) -> list[dict[str, object]]:
    """Extract records from tables within the BCBS PDF."""

    records: list[dict[str, object]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(
            pdf.pages,
            start=1,
        ):
            tables = page.extract_tables()

            for table in tables:
                if not table:
                    continue

                for raw_row in table:
                    if not raw_row:
                        continue

                    values = [
                        clean_text(value)
                        for value in raw_row
                        if clean_text(value)
                    ]

                    if len(values) < 2:
                        continue

                    if is_header_row(values):
                        continue

                    row_text = " | ".join(values)
                    state = detect_state(values)
                    designation = detect_designation(
                        row_text
                    )

                    hospital_name = identify_hospital_name(
                        values
                    )

                    if not hospital_name:
                        continue

                    city = identify_city(
                        values=values,
                        hospital_name=hospital_name,
                        state=state,
                    )

                    records.append(
                        {
                            "BCBS_Hospital": hospital_name,
                            "Hospital": hospital_name,
                            "BCBS_City": city,
                            "City": city,
                            "BCBS_State": state,
                            "State": state,
                            "BCBS_Designation": designation,
                            "Designation": designation,
                            "Blue_Distinction": "Yes",
                            "BCBS_Page": page_number,
                            "BCBS_Source_Row": row_text,
                        }
                    )

    return records


def parse_pdf_text(
    pdf_path: Path,
) -> list[dict[str, object]]:
    """Use page text as a fallback when table extraction fails."""

    records: list[dict[str, object]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(
            pdf.pages,
            start=1,
        ):
            page_text = page.extract_text() or ""

            lines = [
                clean_text(line)
                for line in page_text.splitlines()
                if clean_text(line)
            ]

            current_state = ""

            for line in lines:
                if line.upper() in STATE_ABBREVIATIONS:
                    current_state = line.upper()
                    continue

                upper_line = line.upper()

                hospital_terms = [
                    "HOSPITAL",
                    "MEDICAL CENTER",
                    "MEDICAL CENTRE",
                    "HEALTH CENTER",
                    "HEALTH CENTRE",
                    "REGIONAL MEDICAL",
                    "UNIVERSITY MEDICAL",
                    "CLINIC",
                ]

                if not any(
                    term in upper_line
                    for term in hospital_terms
                ):
                    continue

                designation = detect_designation(line)

                hospital_name = re.sub(
                    r"\bBDC\s*\+?\b",
                    "",
                    line,
                    flags=re.IGNORECASE,
                )

                hospital_name = re.sub(
                    r"BLUE DISTINCTION CENTER\s*\+?",
                    "",
                    hospital_name,
                    flags=re.IGNORECASE,
                )

                hospital_name = clean_text(
                    hospital_name
                )

                if not hospital_name:
                    continue

                records.append(
                    {
                        "BCBS_Hospital": hospital_name,
                        "Hospital": hospital_name,
                        "BCBS_City": "",
                        "City": "",
                        "BCBS_State": current_state,
                        "State": current_state,
                        "BCBS_Designation": designation,
                        "Designation": designation,
                        "Blue_Distinction": "Yes",
                        "BCBS_Page": page_number,
                        "BCBS_Source_Row": line,
                    }
                )

    return records


def clean_bcbs_records(
    records: list[dict[str, object]],
) -> pd.DataFrame:
    """Clean and deduplicate extracted BCBS records."""

    if not records:
        return pd.DataFrame(
            columns=[
                "BCBS_Hospital",
                "Hospital",
                "BCBS_City",
                "City",
                "BCBS_State",
                "State",
                "BCBS_Designation",
                "Designation",
                "Blue_Distinction",
                "BCBS_Page",
                "BCBS_Source_Row",
                "BCBS_Normalized_Hospital",
            ]
        )

    data = pd.DataFrame(records)

    data["BCBS_Hospital"] = (
        data["BCBS_Hospital"]
        .astype(str)
        .map(clean_text)
    )

    data["Hospital"] = data["BCBS_Hospital"]

    data["BCBS_State"] = (
        data["BCBS_State"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    data["State"] = data["BCBS_State"]

    data["BCBS_Designation"] = (
        data["BCBS_Designation"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    data.loc[
        ~data["BCBS_Designation"].isin(
            ["BDC", "BDC+"]
        ),
        "BCBS_Designation",
    ] = "BDC"

    data["Designation"] = (
        data["BCBS_Designation"]
    )

    data["Blue_Distinction"] = "Yes"

    data["BCBS_Normalized_Hospital"] = (
        data["BCBS_Hospital"]
        .map(normalize_hospital_name)
    )

    data = data.loc[
        data["BCBS_Normalized_Hospital"] != ""
    ].copy()

    data = data.drop_duplicates(
        subset=[
            "BCBS_Normalized_Hospital",
            "BCBS_State",
        ],
        keep="first",
    )

    data = data.sort_values(
        by=[
            "BCBS_State",
            "BCBS_Hospital",
        ],
        na_position="last",
    ).reset_index(drop=True)

    return data


def parse_bcbs_pdf() -> pd.DataFrame:
    """Load and parse the local BCBS spine surgery directory."""

    pdf_path = find_local_pdf()

    print("Extracting BCBS provider tables...")

    records = parse_pdf_tables(pdf_path)

    if len(records) == 0:
        print(
            "No table records were found. "
            "Trying text extraction..."
        )

        records = parse_pdf_text(pdf_path)

    bcbs_data = clean_bcbs_records(records)

    if bcbs_data.empty:
        raise RuntimeError(
            "\nThe BCBS PDF was found, but no provider records "
            "could be extracted.\n"
            "Confirm that the PDF opens normally and contains "
            "selectable text.\n"
        )

    output_path = DATA_DIR / "bcbs_spine_centers_extracted.csv"

    bcbs_data.to_csv(
        output_path,
        index=False,
    )

    print(
        f"Extracted {len(bcbs_data):,} BCBS facilities."
    )

    print(
        f"Saved extracted BCBS data to: {output_path}"
    )

    return bcbs_data


if __name__ == "__main__":
    result = parse_bcbs_pdf()

    print("\nFirst extracted records:")

    print(
        result.head(10).to_string(
            index=False
        )
    )