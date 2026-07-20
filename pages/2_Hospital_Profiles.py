import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard_common import footer, format_currency, inject_css, load_data, metric_card

st.set_page_config(page_title="Hospital Profiles", page_icon="🏥", layout="wide")
inject_css()
master, _, _ = load_data(show_uploader=True)

st.markdown(
    '<div class="hero"><h1>Hospital Profile</h1>'
    '<p>Inspect quality designations, reimbursement metrics, and DRG-level rates for one hospital.</p></div>',
    unsafe_allow_html=True,
)

states = sorted(master["State"].dropna().unique())
state = st.selectbox("State", states)
options = sorted(master.loc[master["State"] == state, "Hospital"].dropna().unique())
hospital = st.selectbox("Hospital", options)
row = master.loc[(master["State"] == state) & (master["Hospital"] == hospital)].iloc[0]

cols = st.columns(6)
with cols[0]: metric_card("CMS stars", f"{row['CMS_Star_Rating']:.0f}" if pd.notna(row["CMS_Star_Rating"]) else "N/A")
with cols[1]: metric_card("Blue Distinction", str(row["Blue_Distinction"]), str(row.get("Blue_Distinction_Type", "")))
with cols[2]: metric_card("Average rate", format_currency(row["Average_Base_Rate"]))
with cols[3]: metric_card("Median rate", format_currency(row["Median_Base_Rate"]))
with cols[4]: metric_card("Minimum rate", format_currency(row["Minimum_Base_Rate"]))
with cols[5]: metric_card("Maximum rate", format_currency(row["Maximum_Base_Rate"]))

info = {
    "Hospital": row["Hospital"],
    "CCN": row["CCN"],
    "State": row["State"],
    "CMS match method": row.get("CMS_Match_Method", ""),
    "BCBS match method": row.get("BCBS_Match_Method", ""),
    "BCBS matched name": row.get("BCBS_Matched_Name", ""),
    "BCBS match score": row.get("BCBS_Match_Score", ""),
}
st.dataframe(pd.DataFrame([info]), use_container_width=True, hide_index=True)

drg_cols = [c for c in master.columns if str(c).isdigit()]
drg = pd.DataFrame({
    "DRG": drg_cols,
    "Base Rate": [row[c] for c in drg_cols],
})
drg = drg[pd.to_numeric(drg["Base Rate"], errors="coerce") > 0]
drg["Base Rate"] = pd.to_numeric(drg["Base Rate"], errors="coerce")

if not drg.empty:
    fig = px.bar(
        drg, x="DRG", y="Base Rate",
        title=f"DRG Base Rates for {hospital}",
        text_auto=".3s",
    )
    fig.update_yaxes(tickprefix="$", separatethousands=True)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        drg,
        use_container_width=True,
        hide_index=True,
        column_config={"Base Rate": st.column_config.NumberColumn(format="$%.0f")},
    )

footer()
