import streamlit as st
import plotly.express as px

from dashboard_common import (
    dataframe_download, executive_summary, footer, format_currency, inject_css, load_data,
    metric_card, pct, sidebar_filters,
)

st.set_page_config(
    page_title="Hospital Quality Analytics",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

master, stats, sheets = load_data()
filtered = sidebar_filters(master, "home")

st.markdown(
    """
    <div class="hero">
      <h1>Hospital Quality and Reimbursement Analytics</h1>
      <p>A decision-support platform that integrates hospital base rates, CMS star ratings,
      and Blue Distinction Spine Surgery designations.</p>
    <p> Develop by Kelvin Iyenoma | Olukayode Onasoga|Linnet Bariu | Kelvin Wachira.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

total = len(filtered)
rated = int(filtered["CMS_Star_Rating"].notna().sum())
blue = int((filtered["Blue_Distinction"] == "Yes").sum())
review = int((filtered["Blue_Distinction"] == "Review").sum())
mean_rate = filtered["Average_Base_Rate"].mean()
avg_stars = filtered["CMS_Star_Rating"].mean()

cols = st.columns(6)
with cols[0]: metric_card("Hospitals", f"{total:,}", "Active filtered cohort")
with cols[1]: metric_card("CMS rated", f"{rated:,}", pct(rated, total))
with cols[2]: metric_card("Average CMS stars", f"{avg_stars:.2f}" if avg_stars == avg_stars else "N/A", "Among rated hospitals")
with cols[3]: metric_card("Blue Distinction", f"{blue:,}", pct(blue, total))
with cols[4]: metric_card("Manual review", f"{review:,}", "Borderline BCBS matches")
with cols[5]: metric_card("Mean base rate", format_currency(mean_rate), "Across positive DRG rates")

tabs = st.tabs(["Executive Summary", "Dashboard", "Statistical Results", "Filtered Data"])

with tabs[0]:
    st.markdown('<div class="section-label">Executive insight</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="insight-box">{executive_summary(filtered)}</div>', unsafe_allow_html=True)

with tabs[1]:
    st.markdown("### Quality and reimbursement overview")

    left, right = st.columns(2)

    with left:
        status = (
            filtered["Blue_Distinction"].value_counts()
            .rename_axis("Status").reset_index(name="Hospitals")
        )
        fig = px.bar(
            status, x="Status", y="Hospitals", color="Status",
            title="Blue Distinction Classification", text_auto=True,
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        ratings = (
            filtered["CMS_Star_Rating"].dropna().astype(int).value_counts()
            .sort_index().rename_axis("CMS Stars").reset_index(name="Hospitals")
        )
        fig = px.bar(
            ratings, x="CMS Stars", y="Hospitals",
            title="CMS Star Rating Distribution", text_auto=True,
        )
        fig.update_xaxes(dtick=1)
        st.plotly_chart(fig, use_container_width=True)

    state_summary = (
        filtered.groupby("State")
        .agg(
            Hospitals=("Hospital", "count"),
            Mean_Base_Rate=("Average_Base_Rate", "mean"),
            Average_CMS_Stars=("CMS_Star_Rating", "mean"),
            Blue_Distinction=("Blue_Distinction", lambda x: int((x == "Yes").sum())),
        )
        .reset_index()
    )

    if not state_summary.empty:
        fig = px.choropleth(
            state_summary,
            locations="State",
            locationmode="USA-states",
            color="Mean_Base_Rate",
            hover_data={
                "Hospitals": True,
                "Average_CMS_Stars": ":.2f",
                "Blue_Distinction": True,
                "Mean_Base_Rate": ":$,.0f",
            },
            scope="usa",
            title="Mean Base Rate by State",
        )
        st.plotly_chart(fig, use_container_width=True)

with tabs[2]:
    if stats.empty:
        st.info("No separate statistical workbook is available for the uploaded dataset.")
    else:
        st.dataframe(stats, use_container_width=True, hide_index=True)

with tabs[3]:
    cols = [c for c in ["Hospital","CCN","State","CMS_Star_Rating","Blue_Distinction","Blue_Distinction_Type","Average_Base_Rate","Positive_DRG_Count","CMS_Match_Method","BCBS_Match_Method"] if c in filtered.columns]
    table = filtered[cols].sort_values(["State","Hospital"], na_position="last")
    st.dataframe(table, use_container_width=True, hide_index=True)
    dataframe_download(table, "filtered_hospitals.csv", "Download filtered hospitals")

st.markdown("### Fast access")

c1, c2, c3 = st.columns(3)

with c1:
    if st.button(
        "🔎 Hospital Explorer",
        use_container_width=True,
        help="Search, rank, filter, and export hospitals.",
    ):
        st.switch_page("pages/1_Hospital_Explorer.py")

with c2:
    if st.button(
        "🏥 Hospital Profiles",
        use_container_width=True,
        help="Inspect one hospital and its DRG rates.",
    ):
        st.switch_page("pages/2_Hospital_Profiles.py")

with c3:
    if st.button(
        "📊 Analytics Lab",
        use_container_width=True,
        help="Compare quality measures and reimbursement.",
    ):
        st.switch_page("pages/4_Analytics_Lab.py")

c4, c5, c6 = st.columns(3)

with c4:
    if st.button(
        "⚖️ Compare Hospitals",
        use_container_width=True,
    ):
        st.switch_page("pages/3_Compare_Hospitals.py")

with c5:
    if st.button(
        "✅ Data Quality",
        use_container_width=True,
    ):
        st.switch_page("pages/5_Data_Quality.py")

with c6:
    if st.button(
        "📥 Reports and Downloads",
        use_container_width=True,
    ):
        st.switch_page("pages/6_Reports_and_Downloads.py")

footer()
