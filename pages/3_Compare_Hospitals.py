import plotly.express as px
import streamlit as st

from dashboard_common import footer, inject_css, load_data

st.set_page_config(page_title="Compare Hospitals", page_icon="⚖️", layout="wide")
inject_css()
master, _, _ = load_data(show_uploader=True)

st.markdown(
    '<div class="hero"><h1>Compare Hospitals</h1>'
    '<p>Compare up to five hospitals across quality and reimbursement measures.</p></div>',
    unsafe_allow_html=True,
)

options = sorted(master["Hospital"].dropna().unique())
selected = st.multiselect("Select two to five hospitals", options, max_selections=5)

if len(selected) < 2:
    st.info("Select at least two hospitals.")
else:
    cols = [
        "Hospital", "CCN", "State", "CMS_Star_Rating", "Blue_Distinction",
        "Blue_Distinction_Type", "Average_Base_Rate", "Median_Base_Rate",
        "Minimum_Base_Rate", "Maximum_Base_Rate", "Positive_DRG_Count",
    ]
    comp = master.loc[master["Hospital"].isin(selected), cols]
    st.dataframe(
        comp, use_container_width=True, hide_index=True,
        column_config={
            "CMS_Star_Rating": st.column_config.NumberColumn("CMS Stars", format="%.0f"),
            "Average_Base_Rate": st.column_config.NumberColumn(format="$%.0f"),
            "Median_Base_Rate": st.column_config.NumberColumn(format="$%.0f"),
            "Minimum_Base_Rate": st.column_config.NumberColumn(format="$%.0f"),
            "Maximum_Base_Rate": st.column_config.NumberColumn(format="$%.0f"),
        },
    )

    fig = px.bar(
        comp, x="Hospital", y="Average_Base_Rate",
        color="Blue_Distinction", text_auto=".3s",
        title="Average Base Rate Comparison",
    )
    fig.update_yaxes(tickprefix="$", separatethousands=True)
    st.plotly_chart(fig, use_container_width=True)

    drg_cols = [c for c in master.columns if str(c).isdigit()]
    drg_long = master.loc[master["Hospital"].isin(selected), ["Hospital"] + drg_cols].melt(
        id_vars="Hospital", var_name="DRG", value_name="Base Rate"
    )
    drg_long = drg_long[drg_long["Base Rate"] > 0]
    fig = px.line(
        drg_long, x="DRG", y="Base Rate", color="Hospital",
        markers=True, title="DRG Rate Profiles",
    )
    fig.update_yaxes(tickprefix="$", separatethousands=True)
    st.plotly_chart(fig, use_container_width=True)

footer()
