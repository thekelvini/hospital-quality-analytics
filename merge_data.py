from __future__ import annotations

import pandas as pd
from rapidfuzz import fuzz
from rapidfuzz import process

from config import AUTO_ACCEPT_SCORE
from config import REVIEW_SCORE
from utils import normalize_ccn
from utils import normalize_name
from utils import parse_money


def load_base_rates(path) -> pd.DataFrame:
    """Load and clean the hospital base-rate dataset."""

    data = pd.read_csv(
        path,
        dtype=str,
        low_memory=False,
    )

    data.columns = [
        str(column).strip()
        for column in data.columns
    ]

    required_columns = {
        "Hospital",
        "CCN",
        "State",
    }

    missing_columns = (
        required_columns - set(data.columns)
    )

    if missing_columns:
        raise KeyError(
            "Missing required columns: "
            f"{sorted(missing_columns)}"
        )

    data["CCN"] = data["CCN"].map(
        normalize_ccn
    )

    data["State"] = (
        data["State"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    data["Hospital_Normalized"] = (
        data["Hospital"]
        .map(normalize_name)
    )

    drg_columns = [
        column
        for column in data.columns
        if str(column).isdigit()
    ]

    if not drg_columns:
        raise ValueError(
            "No numeric DRG columns were found."
        )

    for column in drg_columns:
        data[column] = parse_money(
            data[column]
        )

    data["Average_Base_Rate"] = (
        data[drg_columns]
        .mean(
            axis=1,
            skipna=True,
        )
    )

    data["Positive_DRG_Count"] = (
        data[drg_columns] > 0
    ).sum(axis=1)

    return data


def merge_cms(
    base: pd.DataFrame,
    cms: pd.DataFrame,
) -> pd.DataFrame:
    """Merge CMS hospital information into the base-rate dataset."""

    base_data = base.copy()
    cms_data = cms.copy()

    base_data["CCN"] = (
        base_data["CCN"]
        .map(normalize_ccn)
    )

    cms_data["CCN"] = (
        cms_data["CCN"]
        .map(normalize_ccn)
    )

    if "CMS_Star_Rating" not in cms_data.columns:
        raise KeyError(
            "CMS_Star_Rating is missing from the CMS dataset. "
            f"Available columns: {list(cms_data.columns)}"
        )

    cms_data["CMS_Star_Rating"] = (
        pd.to_numeric(
            cms_data["CMS_Star_Rating"],
            errors="coerce",
        )
    )

    cms_data = cms_data.drop_duplicates(
        subset=["CCN"],
        keep="first",
    )

    merged = base_data.merge(
        cms_data,
        on="CCN",
        how="left",
        validate="m:1",
    )

    matched_names = int(
        merged["CMS_Hospital_Name"]
        .notna()
        .sum()
    )

    available_ratings = int(
        merged["CMS_Star_Rating"]
        .notna()
        .sum()
    )

    print(
        f"CMS hospital-name matches: "
        f"{matched_names:,} of {len(merged):,}"
    )

    print(
        f"CMS star ratings available: "
        f"{available_ratings:,} of {len(merged):,}"
    )

    return merged


def match_bcbs(
    base: pd.DataFrame,
    bcbs: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Match hospitals to Blue Distinction providers."""

    result = base.copy()
    bcbs_data = bcbs.copy()

    required_bcbs_columns = {
        "BCBS_Hospital_Name",
        "BCBS_State",
        "BCBS_Normalized_Name",
        "BCBS_Designation",
    }

    missing_columns = (
        required_bcbs_columns
        - set(bcbs_data.columns)
    )

    if missing_columns:
        raise KeyError(
            "BCBS data are missing required columns: "
            f"{sorted(missing_columns)}. "
            f"Available columns: {list(bcbs_data.columns)}"
        )

    result["Blue_Distinction"] = "No"
    result["Blue_Distinction_Type"] = pd.NA
    result["BCBS_Matched_Name"] = pd.NA
    result["BCBS_Match_Score"] = pd.NA
    result["BCBS_Match_Method"] = pd.NA
    result["BCBS_Match_Status"] = (
        "No state candidate"
    )

    review_records = []

    grouped = {
        state: group.reset_index(drop=True)
        for state, group in bcbs_data.groupby(
            "BCBS_State"
        )
    }

    for index, row in result.iterrows():
        state = row["State"]
        hospital_name = row[
            "Hospital_Normalized"
        ]

        candidates = grouped.get(state)

        if (
            candidates is None
            or candidates.empty
            or not hospital_name
        ):
            continue

        exact_matches = candidates.loc[
            candidates[
                "BCBS_Normalized_Name"
            ]
            == hospital_name
        ]

        if not exact_matches.empty:
            candidate = exact_matches.iloc[0]

            result.at[
                index,
                "Blue_Distinction",
            ] = "Yes"

            result.at[
                index,
                "Blue_Distinction_Type",
            ] = candidate[
                "BCBS_Designation"
            ]

            result.at[
                index,
                "BCBS_Matched_Name",
            ] = candidate[
                "BCBS_Hospital_Name"
            ]

            result.at[
                index,
                "BCBS_Match_Score",
            ] = 100.0

            result.at[
                index,
                "BCBS_Match_Method",
            ] = "Exact normalized name"

            result.at[
                index,
                "BCBS_Match_Status",
            ] = "Auto accepted"

            continue

        choices = candidates[
            "BCBS_Normalized_Name"
        ].tolist()

        match = process.extractOne(
            hospital_name,
            choices,
            scorer=fuzz.token_set_ratio,
        )

        if match is None:
            continue

        _, score, position = match

        candidate = candidates.iloc[
            position
        ]

        result.at[
            index,
            "BCBS_Matched_Name",
        ] = candidate[
            "BCBS_Hospital_Name"
        ]

        result.at[
            index,
            "BCBS_Match_Score",
        ] = float(score)

        result.at[
            index,
            "BCBS_Match_Method",
        ] = "Fuzzy name"

        if score >= AUTO_ACCEPT_SCORE:
            result.at[
                index,
                "Blue_Distinction",
            ] = "Yes"

            result.at[
                index,
                "Blue_Distinction_Type",
            ] = candidate[
                "BCBS_Designation"
            ]

            result.at[
                index,
                "BCBS_Match_Status",
            ] = "Auto accepted"

        elif score >= REVIEW_SCORE:
            result.at[
                index,
                "Blue_Distinction",
            ] = "Review"

            result.at[
                index,
                "Blue_Distinction_Type",
            ] = candidate[
                "BCBS_Designation"
            ]

            result.at[
                index,
                "BCBS_Match_Status",
            ] = "Manual review"

            review_records.append(
                {
                    "Hospital": row[
                        "Hospital"
                    ],
                    "CCN": row["CCN"],
                    "State": row["State"],
                    "Candidate": candidate[
                        "BCBS_Hospital_Name"
                    ],
                    "Candidate_Type": candidate[
                        "BCBS_Designation"
                    ],
                    "Match_Score": float(
                        score
                    ),
                    "Decision": "",
                }
            )

        else:
            result.at[
                index,
                "BCBS_Match_Status",
            ] = "Low score"

    review_data = pd.DataFrame(
        review_records
    )

    yes_count = int(
        (
            result["Blue_Distinction"]
            == "Yes"
        ).sum()
    )

    review_count = int(
        (
            result["Blue_Distinction"]
            == "Review"
        ).sum()
    )

    print(
        f"Blue Distinction matches accepted: "
        f"{yes_count:,}"
    )

    print(
        f"Blue Distinction matches for review: "
        f"{review_count:,}"
    )

    return result, review_data


def to_long(
    master: pd.DataFrame,
) -> pd.DataFrame:
    """Convert DRG columns from wide format to long format."""

    drg_columns = [
        column
        for column in master.columns
        if str(column).isdigit()
    ]

    identifier_columns = [
        column
        for column in master.columns
        if column not in drg_columns
    ]

    long_data = master.melt(
        id_vars=identifier_columns,
        value_vars=drg_columns,
        var_name="DRG",
        value_name="Base_Rate",
    )

    long_data["DRG"] = (
        long_data["DRG"]
        .astype(str)
    )

    long_data["Base_Rate"] = (
        pd.to_numeric(
            long_data["Base_Rate"],
            errors="coerce",
        )
    )

    long_data = long_data.loc[
        long_data["Base_Rate"].notna()
        & (long_data["Base_Rate"] > 0)
    ].copy()

    return long_data