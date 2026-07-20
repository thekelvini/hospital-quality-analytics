import pandas as pd
import streamlit as st

from dashboard_common import dataframe_download, footer, inject_css, load_data, pct

st.set_page_config(page_title="Data Quality", page_icon="✅", layout="wide")
inject_css()
master, _, sheets = load_data(show_uploader=True)

st.markdown(
    '<div class="hero"><h1>Data Quality and Match Review</h1>'
    '<p>Audit CMS coverage, BCBS matching, manual reviews, and missing values.</p></div>',
    unsafe_allow_html=True,
)

n = len(master)
checks = pd.DataFrame([
    {"Check": "Hospitals in master data", "Count": n, "Coverage": 100.0},
    {"Check": "CMS star rating available", "Count": int(master["CMS_Star_Rating"].notna().sum()),
     "Coverage": 100*master["CMS_Star_Rating"].notna().mean()},
    {"Check": "Accepted Blue Distinction", "Count": int((master["Blue_Distinction"] == "Yes").sum()),
     "Coverage": 100*(master["Blue_Distinction"] == "Yes").mean()},
    {"Check": "Manual Blue Distinction review", "Count": int((master["Blue_Distinction"] == "Review").sum()),
     "Coverage": 100*(master["Blue_Distinction"] == "Review").mean()},
    {"Check": "Average base rate available", "Count": int(master["Average_Base_Rate"].notna().sum()),
     "Coverage": 100*master["Average_Base_Rate"].notna().mean()},
])
st.dataframe(
    checks, use_container_width=True, hide_index=True,
    column_config={"Coverage": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%")},
)

unrated = master.loc[
    master["CMS_Star_Rating"].isna(),
    ["Hospital", "CCN", "State", "CMS_Match_Method"],
]
reviews_cols = [
    c for c in [
        "Hospital", "CCN", "State", "BCBS_Matched_Name",
        "BCBS_Match_Score", "Blue_Distinction_Type", "BCBS_Match_Method",
    ] if c in master.columns
]
reviews = master.loc[master["Blue_Distinction"] == "Review", reviews_cols]

c1, c2 = st.columns(2)
with c1:
    st.subheader(f"CMS rating unavailable: {len(unrated):,}")
    st.dataframe(unrated, use_container_width=True, hide_index=True)
    dataframe_download(unrated, "cms_unmatched.csv", "Download CMS unmatched")
with c2:
    st.subheader(f"BCBS manual review: {len(reviews):,}")
    st.dataframe(reviews, use_container_width=True, hide_index=True)
    dataframe_download(reviews, "bcbs_manual_review.csv", "Download BCBS review")

with st.expander("Workbook sheets"):
    st.write(list(sheets.keys()))

footer()
