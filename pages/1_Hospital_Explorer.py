import streamlit as st
import plotly.express as px

from dashboard_common import (
    dataframe_download, footer, inject_css, load_data, sidebar_filters,
)

st.set_page_config(page_title="Hospital Explorer", page_icon="🔎", layout="wide")
inject_css()
master, _, _ = load_data(show_uploader=True)
filtered = sidebar_filters(master, "explorer")

st.markdown(
    '<div class="hero"><h1>Hospital Explorer</h1>'
    '<p>Search, rank, filter, and export hospitals across the integrated dataset.</p></div>',
    unsafe_allow_html=True,
)

rank_metric = st.selectbox(
    "Rank hospitals by",
    ["Average_Base_Rate", "CMS_Star_Rating", "Maximum_Base_Rate", "Positive_DRG_Count"],
)
ascending = st.toggle("Lowest first", value=False)

display_cols = [
    "Hospital", "CCN", "State", "CMS_Star_Rating", "Blue_Distinction",
    "Blue_Distinction_Type", "Average_Base_Rate", "Median_Base_Rate",
    "Minimum_Base_Rate", "Maximum_Base_Rate", "Positive_DRG_Count",
    "CMS_Match_Method", "BCBS_Match_Method",
]
display_cols = [c for c in display_cols if c in filtered.columns]
table = filtered[display_cols].sort_values(rank_metric, ascending=ascending, na_position="last")

st.dataframe(
    table,
    use_container_width=True,
    hide_index=True,
    column_config={
        "CMS_Star_Rating": st.column_config.NumberColumn("CMS Stars", format="%.0f"),
        "Average_Base_Rate": st.column_config.NumberColumn("Average Rate", format="$%.0f"),
        "Median_Base_Rate": st.column_config.NumberColumn("Median Rate", format="$%.0f"),
        "Minimum_Base_Rate": st.column_config.NumberColumn("Minimum Rate", format="$%.0f"),
        "Maximum_Base_Rate": st.column_config.NumberColumn("Maximum Rate", format="$%.0f"),
    },
)

dataframe_download(table, "hospital_explorer.csv", "Download current table")

top = table.dropna(subset=[rank_metric]).head(20)
if not top.empty:
    fig = px.bar(
        top.sort_values(rank_metric),
        x=rank_metric,
        y="Hospital",
        orientation="h",
        color="Blue_Distinction",
        title=f"Top Hospitals by {rank_metric.replace('_', ' ')}",
    )
    if "Rate" in rank_metric:
        fig.update_xaxes(tickprefix="$", separatethousands=True)
    st.plotly_chart(fig, use_container_width=True)

footer()
