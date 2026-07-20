import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from scipy.stats import mannwhitneyu, spearmanr, ttest_ind

from dashboard_common import footer, format_currency, inject_css, load_data, sidebar_filters

st.set_page_config(page_title="Analytics Lab", page_icon="📊", layout="wide")
inject_css()
master, stats, _ = load_data(show_uploader=True)
filtered = sidebar_filters(master, "analytics")

st.markdown(
    '<div class="hero"><h1>Analytics Lab</h1>'
    '<p>Explore reimbursement distributions and calculate live statistical comparisons.</p></div>',
    unsafe_allow_html=True,
)

yes = filtered.loc[filtered["Blue_Distinction"] == "Yes", "Average_Base_Rate"].dropna()
no = filtered.loc[filtered["Blue_Distinction"] == "No", "Average_Base_Rate"].dropna()

results = []
if len(yes) >= 2 and len(no) >= 2:
    welch = ttest_ind(yes, no, equal_var=False)
    mann = mannwhitneyu(yes, no, alternative="two-sided")
    pooled = np.sqrt(((len(yes)-1)*yes.var(ddof=1) + (len(no)-1)*no.var(ddof=1)) / (len(yes)+len(no)-2))
    d = (yes.mean() - no.mean()) / pooled if pooled else np.nan
    results.extend([
        {"Analysis": "Blue Distinction mean rate", "Estimate": yes.mean(), "P-value": np.nan},
        {"Analysis": "Non-Blue mean rate", "Estimate": no.mean(), "P-value": np.nan},
        {"Analysis": "Welch t-test", "Estimate": yes.mean()-no.mean(), "P-value": welch.pvalue},
        {"Analysis": "Mann-Whitney U", "Estimate": mann.statistic, "P-value": mann.pvalue},
        {"Analysis": "Cohen's d", "Estimate": d, "P-value": np.nan},
    ])

corr = filtered[["CMS_Star_Rating", "Average_Base_Rate"]].dropna()
if len(corr) >= 3:
    rho, pvalue = spearmanr(corr["CMS_Star_Rating"], corr["Average_Base_Rate"])
    results.append({"Analysis": "CMS Spearman correlation", "Estimate": rho, "P-value": pvalue})

if results:
    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

left, right = st.columns(2)
with left:
    box = filtered[filtered["Blue_Distinction"].isin(["Yes", "No"])]
    fig = px.box(
        box, x="Blue_Distinction", y="Average_Base_Rate",
        points="outliers", title="Base Rate by Blue Distinction",
    )
    fig.update_yaxes(tickprefix="$", separatethousands=True)
    st.plotly_chart(fig, use_container_width=True)

with right:
    scatter = corr.copy()
    fig = px.scatter(
        scatter, x="CMS_Star_Rating", y="Average_Base_Rate",
        trendline="ols" if len(scatter) >= 3 else None,
        title="CMS Stars and Base Rates",
    )
    fig.update_xaxes(dtick=1)
    fig.update_yaxes(tickprefix="$", separatethousands=True)
    st.plotly_chart(fig, use_container_width=True)

if not stats.empty:
    with st.expander("Generated statistical workbook"):
        st.dataframe(stats, use_container_width=True, hide_index=True)

footer()
