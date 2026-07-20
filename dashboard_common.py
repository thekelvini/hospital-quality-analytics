from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = APP_DIR / "output"
DEFAULT_MASTER_FILE = OUTPUT_DIR / "Hospital_Quality_Master.xlsx"
DEFAULT_STATS_FILE = OUTPUT_DIR / "Statistical_Results.xlsx"

US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1500px;}
        [data-testid="stSidebar"] {background: linear-gradient(180deg, #111827 0%, #1f2937 100%);}
        [data-testid="stSidebar"] * {color: #f9fafb;}
        .hero {
            padding: 2rem 2.2rem;
            border-radius: 22px;
            background: linear-gradient(120deg, #0f172a 0%, #1e3a8a 58%, #0f766e 100%);
            box-shadow: 0 18px 50px rgba(15, 23, 42, .30);
            margin-bottom: 1.4rem;
        }
        .hero h1 {color: white; font-size: 2.45rem; margin: 0 0 .45rem 0;}
        .hero p {color: #dbeafe; font-size: 1.05rem; margin: 0; max-width: 900px;}
        .section-label {
            font-size: .82rem; letter-spacing: .12em; text-transform: uppercase;
            color: #64748b; font-weight: 700; margin: .5rem 0;
        }
        .metric-card {
            border: 1px solid rgba(148,163,184,.25);
            border-radius: 18px;
            padding: 1.15rem 1.25rem;
            background: rgba(255,255,255,.035);
            min-height: 125px;
        }
        .metric-label {color: #94a3b8; font-size: .86rem; font-weight: 700;}
        .metric-value {font-size: 2rem; font-weight: 800; margin-top: .35rem;}
        .metric-note {color: #94a3b8; font-size: .78rem; margin-top: .25rem;}
        .insight-box {
            border-left: 5px solid #14b8a6;
            background: rgba(20,184,166,.08);
            padding: 1.15rem 1.3rem;
            border-radius: 0 15px 15px 0;
            line-height: 1.65;
        }
        .status-pill {
            display:inline-block; border-radius:999px; padding:.25rem .65rem;
            background:#0f766e; color:white; font-size:.78rem; font-weight:700;
        }
        div[data-testid="stDataFrame"] {border-radius: 16px; overflow: hidden;}
        .footer {color:#64748b; font-size:.78rem; text-align:center; margin-top:2rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def first_existing(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    lookup = {str(column).strip().lower(): column for column in columns}
    for candidate in candidates:
        found = lookup.get(candidate.lower())
        if found is not None:
            return found
    return None


def clean_master_data(data: pd.DataFrame) -> pd.DataFrame:
    df = data.copy()
    df.columns = [str(c).strip() for c in df.columns]

    aliases = {
        "Hospital": ["Hospital", "Hospital Name", "Facility Name"],
        "CCN": ["CCN", "Facility ID"],
        "State": ["State", "CMS_State"],
        "CMS_Star_Rating": ["CMS_Star_Rating", "CMS Star Rating", "Hospital Overall Rating"],
        "Blue_Distinction": ["Blue_Distinction", "Blue Distinction"],
        "Blue_Distinction_Type": ["Blue_Distinction_Type", "BCBS_Designation"],
        "CMS_Match_Method": ["CMS_Match_Method", "CMS Match Method"],
        "BCBS_Match_Method": ["BCBS_Match_Method", "BCBS Match Method"],
    }
    rename = {}
    for standard, candidates in aliases.items():
        found = first_existing(df.columns, candidates)
        if found:
            rename[found] = standard
    df = df.rename(columns=rename)

    for column in aliases:
        if column not in df.columns:
            df[column] = pd.NA

    df["Hospital"] = df["Hospital"].astype("string").str.strip()
    df["State"] = df["State"].astype("string").str.strip().str.upper()
    df["CCN"] = (
        df["CCN"].astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"\D", "", regex=True)
        .str.zfill(6)
    )
    df["CMS_Star_Rating"] = pd.to_numeric(df["CMS_Star_Rating"], errors="coerce")
    df["Blue_Distinction"] = (
        df["Blue_Distinction"].astype("string").fillna("No").str.strip().str.title()
    )

    drg_columns = [c for c in df.columns if str(c).isdigit()]
    for column in drg_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    if drg_columns:
        positive = df[drg_columns].where(df[drg_columns] > 0)
        df["Average_Base_Rate"] = positive.mean(axis=1)
        df["Median_Base_Rate"] = positive.median(axis=1)
        df["Minimum_Base_Rate"] = positive.min(axis=1)
        df["Maximum_Base_Rate"] = positive.max(axis=1)
        df["Positive_DRG_Count"] = positive.count(axis=1)
    else:
        for col in ["Average_Base_Rate", "Median_Base_Rate", "Minimum_Base_Rate", "Maximum_Base_Rate"]:
            if col not in df.columns:
                df[col] = pd.NA
            df[col] = pd.to_numeric(df[col], errors="coerce")
        if "Positive_DRG_Count" not in df.columns:
            df["Positive_DRG_Count"] = pd.NA

    return df


@st.cache_data(show_spinner=False)
def _load_default_data() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    if not DEFAULT_MASTER_FILE.exists():
        raise FileNotFoundError(f"Run python main.py first. Missing: {DEFAULT_MASTER_FILE}")
    excel = pd.ExcelFile(DEFAULT_MASTER_FILE)
    sheets = {sheet: pd.read_excel(excel, sheet_name=sheet) for sheet in excel.sheet_names}
    master_sheet = "Master Data" if "Master Data" in sheets else excel.sheet_names[0]
    master = clean_master_data(sheets[master_sheet])
    if DEFAULT_STATS_FILE.exists():
        stats_excel = pd.ExcelFile(DEFAULT_STATS_FILE)
        stats = pd.read_excel(stats_excel, sheet_name=stats_excel.sheet_names[0])
    else:
        stats = pd.DataFrame()
    return master, stats, sheets


def _read_uploaded_master(raw: bytes, filename: str) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        data = pd.read_csv(io.BytesIO(raw), dtype=str, low_memory=False)
        return clean_master_data(data), {"Uploaded Data": data}
    excel = pd.ExcelFile(io.BytesIO(raw))
    sheets = {sheet: pd.read_excel(excel, sheet_name=sheet) for sheet in excel.sheet_names}
    preferred = next((name for name in ["Master Data", "Master", "Data"] if name in sheets), excel.sheet_names[0])
    return clean_master_data(sheets[preferred]), sheets


def load_data(show_uploader: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    if show_uploader:
        st.sidebar.markdown("## Data")
        uploaded = st.sidebar.file_uploader(
            "Upload a replacement master workbook or CSV",
            type=["xlsx", "xls", "csv"],
            key="global_master_upload",
            help="The included Hospital_Quality_Master.xlsx remains the default.",
        )
        if uploaded is not None:
            st.session_state["uploaded_master_bytes"] = uploaded.getvalue()
            st.session_state["uploaded_master_name"] = uploaded.name
    raw = st.session_state.get("uploaded_master_bytes")
    filename = st.session_state.get("uploaded_master_name")
    if raw and filename:
        master, sheets = _read_uploaded_master(raw, filename)
        if show_uploader:
            st.sidebar.success(f"Uploaded data loaded: {filename}")
        return master, pd.DataFrame(), sheets
    master, stats, sheets = _load_default_data()
    if show_uploader:
        st.sidebar.success("Included master workbook loaded.")
    return master, stats, sheets


def format_currency(value) -> str:
    return "Not available" if pd.isna(value) else f"${value:,.0f}"


def pct(n, d) -> str:
    return "0.0%" if not d else f"{100*n/d:.1f}%"


def metric_card(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
          <div class="metric-label">{label}</div>
          <div class="metric-value">{value}</div>
          <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_filters(df: pd.DataFrame, key_prefix: str = "") -> pd.DataFrame:
    st.sidebar.markdown("## Filters")
    states = sorted(df["State"].dropna().unique())
    selected_states = st.sidebar.multiselect("State", states, default=states, key=f"{key_prefix}_states")
    statuses = [s for s in ["Yes", "No", "Review"] if s in set(df["Blue_Distinction"].dropna())]
    selected_status = st.sidebar.multiselect("Blue Distinction", statuses, default=statuses, key=f"{key_prefix}_status")
    ratings = df["CMS_Star_Rating"].dropna()
    default_rating = (int(max(1, ratings.min())), int(min(5, ratings.max()))) if not ratings.empty else (1, 5)
    selected_rating = st.sidebar.slider("CMS star rating", 1, 5, default_rating, key=f"{key_prefix}_rating", help="Hospitals without a CMS rating remain visible.")
    search = st.sidebar.text_input("Hospital search", key=f"{key_prefix}_search")
    result = df.copy()
    result = result[result["State"].isin(selected_states)] if selected_states else result.iloc[0:0]
    result = result[result["Blue_Distinction"].isin(selected_status)] if selected_status else result.iloc[0:0]
    mask = result["CMS_Star_Rating"].between(selected_rating[0], selected_rating[1], inclusive="both") | result["CMS_Star_Rating"].isna()
    result = result[mask]
    if search.strip():
        result = result[result["Hospital"].str.contains(search.strip(), case=False, na=False, regex=False)]
    return result


def executive_summary(df: pd.DataFrame) -> str:
    total = len(df)
    rated = int(df["CMS_Star_Rating"].notna().sum())
    blue = int((df["Blue_Distinction"] == "Yes").sum())
    review = int((df["Blue_Distinction"] == "Review").sum())
    blue_mean = df.loc[df["Blue_Distinction"] == "Yes", "Average_Base_Rate"].mean()
    no_mean = df.loc[df["Blue_Distinction"] == "No", "Average_Base_Rate"].mean()
    corr_data = df[["CMS_Star_Rating", "Average_Base_Rate"]].dropna()
    rho = corr_data.corr(method="spearman").iloc[0, 1] if len(corr_data) >= 3 else np.nan

    text = (
        f"The analysis includes {total:,} hospitals. "
        f"CMS ratings are available for {rated:,} hospitals ({pct(rated, total)}). "
        f"The accepted Blue Distinction group includes {blue:,} hospitals. "
        f"Another {review:,} hospitals require manual review."
    )
    if pd.notna(blue_mean) and pd.notna(no_mean):
        diff = blue_mean - no_mean
        text += (
            f" Accepted Blue Distinction hospitals have an average base rate "
            f"{format_currency(abs(diff))} {'higher' if diff >= 0 else 'lower'} "
            f"than non-designated hospitals."
        )
    if pd.notna(rho):
        strength = "weak" if abs(rho) < .30 else "moderate" if abs(rho) < .50 else "strong"
        text += (
            f" CMS star ratings show a {strength} "
            f"{'positive' if rho >= 0 else 'negative'} association with average base rates "
            f"(Spearman rho = {rho:.2f})."
        )
    return text


def dataframe_download(df: pd.DataFrame, filename: str, label: str) -> None:
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )


def footer() -> None:
    st.markdown(
        '<div class="footer">Hospital Quality and Reimbursement Analytics | '
        'CMS Hospital General Information and BCBS Blue Distinction Spine Surgery</div>',
        unsafe_allow_html=True,
    )
