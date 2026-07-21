from __future__ import annotations

from pathlib import Path
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import mannwhitneyu, spearmanr, ttest_ind
from pathlib import Path
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from scipy.stats import (
    mannwhitneyu,
    spearmanr,
    ttest_ind,
)

def run_statistics(
    master: pd.DataFrame,
    long_data: pd.DataFrame,
):
    """
    Run hospital-level tests, DRG-adjusted regression,
    CMS correlation, and CMS regression.

    Returns
    -------
    results : pd.DataFrame
        Summary of statistical test and regression results.

    summary : pd.DataFrame
        Hospital-level analytical dataset.

    desc : pd.DataFrame
        Descriptive statistics by Blue Distinction status.

    model_text : str
        Full statsmodels regression summaries.
    """

    summary = hospital_summary(master, long_data)

    rows = []
    model_text = []

    # ---------------------------------------------------------
    # 1. BLUE DISTINCTION HOSPITAL-LEVEL GROUP COMPARISON
    # ---------------------------------------------------------

    eligible = summary[
        summary["Blue_Distinction"].isin(["Yes", "No"])
    ].copy()

    yes = eligible.loc[
        eligible["Blue_Distinction"] == "Yes",
        "Average_Base_Rate",
    ].dropna()

    no = eligible.loc[
        eligible["Blue_Distinction"] == "No",
        "Average_Base_Rate",
    ].dropna()

    if len(yes) >= 2 and len(no) >= 2:

        # One-sided Welch t-test.
        # H1: Blue Distinction hospitals have higher reimbursement.
        t_result = ttest_ind(
            yes,
            no,
            equal_var=False,
            alternative="greater",
        )

        # One-sided nonparametric test.
        mann_result = mannwhitneyu(
            yes,
            no,
            alternative="greater",
        )

        mean_difference = yes.mean() - no.mean()
        cohen_d = _cohen_d(yes, no)

        rows.extend(
            [
                {
                    "Analysis": "Hospital-level Welch t-test",
                    "Estimate": mean_difference,
                    "P_Value": t_result.pvalue,
                    "N": len(yes) + len(no),
                    "Effect_Size": cohen_d,
                    "Interpretation": (
                        "Mean reimbursement difference in dollars. "
                        "Blue Distinction minus non-Blue Distinction."
                    ),
                },
                {
                    "Analysis": "Mann-Whitney U test",
                    "Estimate": mann_result.statistic,
                    "P_Value": mann_result.pvalue,
                    "N": len(yes) + len(no),
                    "Effect_Size": np.nan,
                    "Interpretation": (
                        "One-sided nonparametric comparison of hospital "
                        "average base-rate distributions."
                    ),
                },
            ]
        )

    # ---------------------------------------------------------
    # 2. DRG-ADJUSTED BLUE DISTINCTION REGRESSION
    # ---------------------------------------------------------

    reg = long_data.copy()

    reg = reg[
        reg["Base_Rate"].gt(0)
        & reg["Blue_Distinction"].isin(["Yes", "No"])
    ].copy()

    if (
        reg["Blue_Distinction"].nunique() == 2
        and reg["DRG"].nunique() >= 2
    ):

        reg["Blue_Distinction_Flag"] = (
            reg["Blue_Distinction"] == "Yes"
        ).astype(int)

        reg["Log_Base_Rate"] = np.log(reg["Base_Rate"])

        try:
            drg_model = smf.ols(
                formula=(
                    "Log_Base_Rate ~ "
                    "Blue_Distinction_Flag + C(DRG)"
                ),
                data=reg,
            ).fit(
                cov_type="cluster",
                cov_kwds={"groups": reg["CCN"]},
            )

            coefficient = drg_model.params[
                "Blue_Distinction_Flag"
            ]

            percent_difference = (
                np.exp(coefficient) - 1
            ) * 100

            confidence_interval = drg_model.conf_int().loc[
                "Blue_Distinction_Flag"
            ]

            lower_percent = (
                np.exp(confidence_interval.iloc[0]) - 1
            ) * 100

            upper_percent = (
                np.exp(confidence_interval.iloc[1]) - 1
            ) * 100

            rows.append(
                {
                    "Analysis": (
                        "DRG-adjusted log-linear regression"
                    ),
                    "Estimate": percent_difference,
                    "P_Value": drg_model.pvalues[
                        "Blue_Distinction_Flag"
                    ],
                    "N": int(drg_model.nobs),
                    "Effect_Size": np.nan,
                    "Interpretation": (
                        "Estimated percent reimbursement difference "
                        "associated with Blue Distinction after controlling "
                        f"for DRG. 95% CI: {lower_percent:.2f}% to "
                        f"{upper_percent:.2f}%. "
                        f"Adjusted R-squared: {drg_model.rsquared_adj:.3f}."
                    ),
                }
            )

            model_text.append(
                "DRG-ADJUSTED BLUE DISTINCTION REGRESSION\n"
                + drg_model.summary().as_text()
            )

        except Exception as exc:
            warnings.warn(
                f"DRG-adjusted regression skipped: {exc}"
            )

    # ---------------------------------------------------------
    # 3. CMS STAR RATING ANALYSIS
    # ---------------------------------------------------------

    cms = summary.dropna(
        subset=[
            "CMS_Star_Rating",
            "Average_Base_Rate",
        ]
    ).copy()

    cms = cms[
        cms["Average_Base_Rate"] > 0
    ].copy()

    if (
        len(cms) >= 5
        and cms["CMS_Star_Rating"].nunique() >= 2
    ):

        # Spearman rank correlation.
        rho, correlation_p = spearmanr(
            cms["CMS_Star_Rating"],
            cms["Average_Base_Rate"],
        )

        rows.append(
            {
                "Analysis": "CMS Spearman correlation",
                "Estimate": rho,
                "P_Value": correlation_p,
                "N": len(cms),
                "Effect_Size": rho,
                "Interpretation": (
                    "Rank-based association between CMS Overall "
                    "Hospital Star Rating and average hospital base rate."
                ),
            }
        )

        # Log-linear regression.
        cms["Log_Average_Base_Rate"] = np.log(
            cms["Average_Base_Rate"]
        )

        cms_model = smf.ols(
            formula=(
                "Log_Average_Base_Rate ~ CMS_Star_Rating"
            ),
            data=cms,
        ).fit(cov_type="HC3")

        cms_coefficient = cms_model.params[
            "CMS_Star_Rating"
        ]

        cms_percent_difference = (
            np.exp(cms_coefficient) - 1
        ) * 100

        cms_confidence_interval = cms_model.conf_int().loc[
            "CMS_Star_Rating"
        ]

        cms_lower_percent = (
            np.exp(cms_confidence_interval.iloc[0]) - 1
        ) * 100

        cms_upper_percent = (
            np.exp(cms_confidence_interval.iloc[1]) - 1
        ) * 100

        rows.append(
            {
                "Analysis": "CMS log-linear regression",
                "Estimate": cms_percent_difference,
                "P_Value": cms_model.pvalues[
                    "CMS_Star_Rating"
                ],
                "N": int(cms_model.nobs),
                "Effect_Size": cms_model.rsquared,
                "Interpretation": (
                    "Estimated percent reimbursement difference "
                    "associated with one additional CMS star. "
                    f"95% CI: {cms_lower_percent:.2f}% to "
                    f"{cms_upper_percent:.2f}%. "
                    f"R-squared: {cms_model.rsquared:.3f}."
                ),
            }
        )

        model_text.append(
            "CMS STAR RATING LOG-LINEAR REGRESSION\n"
            + cms_model.summary().as_text()
        )

    # ---------------------------------------------------------
    # 4. DESCRIPTIVE STATISTICS
    # ---------------------------------------------------------

    desc = (
        summary.groupby(
            "Blue_Distinction",
            dropna=False,
        )["Average_Base_Rate"]
        .agg(
            [
                "count",
                "mean",
                "median",
                "std",
                "min",
                "max",
            ]
        )
        .reset_index()
    )

    results = pd.DataFrame(rows)

    return (
        results,
        summary,
        desc,
        "\n\n".join(model_text),
    )


def create_figures(
    summary: pd.DataFrame,
    folder: Path,
) -> list[Path]:
    """
    Create descriptive and regression figures.
    """

    folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    paths = []

    # ---------------------------------------------------------
    # 1. HISTOGRAM OF HOSPITAL AVERAGE BASE RATES
    # ---------------------------------------------------------

    rates = summary[
        "Average_Base_Rate"
    ].dropna()

    if not rates.empty:

        path = folder / "average_base_rate_histogram.png"

        plt.figure(figsize=(8, 5))

        plt.hist(
            rates,
            bins=25,
        )

        plt.xlabel(
            "Average hospital base rate"
        )

        plt.ylabel(
            "Number of hospitals"
        )

        plt.title(
            "Distribution of Average Hospital Base Rates"
        )

        plt.tight_layout()

        plt.savefig(
            path,
            dpi=200,
            bbox_inches="tight",
        )

        plt.close()

        paths.append(path)

    # ---------------------------------------------------------
    # 2. BLUE DISTINCTION BOXPLOT
    # ---------------------------------------------------------

    groups = summary[
        summary["Blue_Distinction"].isin(["Yes", "No"])
    ].copy()

    if groups["Blue_Distinction"].nunique() == 2:

        no = groups.loc[
            groups["Blue_Distinction"] == "No",
            "Average_Base_Rate",
        ].dropna()

        yes = groups.loc[
            groups["Blue_Distinction"] == "Yes",
            "Average_Base_Rate",
        ].dropna()

        if not no.empty and not yes.empty:

            path = folder / "blue_distinction_boxplot.png"

            plt.figure(figsize=(7, 5))

            plt.boxplot(
                [no, yes],
                tick_labels=["No", "Yes"],
            )

            plt.xlabel(
                "Blue Distinction status"
            )

            plt.ylabel(
                "Average hospital base rate"
            )

            plt.title(
                "Hospital Base Rates by Blue Distinction Status"
            )

            plt.tight_layout()

            plt.savefig(
                path,
                dpi=200,
                bbox_inches="tight",
            )

            plt.close()

            paths.append(path)

    # ---------------------------------------------------------
    # 3. CMS STAR RATING SCATTERPLOT WITH REGRESSION LINE
    # ---------------------------------------------------------

    cms = summary.dropna(
        subset=[
            "CMS_Star_Rating",
            "Average_Base_Rate",
        ]
    ).copy()

    cms = cms[
        cms["Average_Base_Rate"] > 0
    ].copy()

    if (
        len(cms) >= 2
        and cms["CMS_Star_Rating"].nunique() >= 2
    ):

        path = folder / "cms_rating_regression.png"

        x = cms["CMS_Star_Rating"].astype(float)
        y = cms["Average_Base_Rate"].astype(float)

        slope, intercept = np.polyfit(
            x,
            y,
            1,
        )

        x_line = np.linspace(
            x.min(),
            x.max(),
            100,
        )

        y_line = (
            intercept
            + slope * x_line
        )

        plt.figure(figsize=(7, 5))

        plt.scatter(
            x,
            y,
            alpha=0.65,
        )

        plt.plot(
            x_line,
            y_line,
            linewidth=2,
        )

        plt.xlabel(
            "CMS Overall Hospital Star Rating"
        )

        plt.ylabel(
            "Average hospital base rate"
        )

        plt.title(
            "CMS Star Rating and Average Hospital Base Rate"
        )

        plt.xticks(
            sorted(
                cms["CMS_Star_Rating"]
                .dropna()
                .unique()
            )
        )

        plt.tight_layout()

        plt.savefig(
            path,
            dpi=200,
            bbox_inches="tight",
        )

        plt.close()

        paths.append(path)

    # ---------------------------------------------------------
    # 4. CMS STAR RATING DISTRIBUTION
    # ---------------------------------------------------------

    ratings = (
        summary["CMS_Star_Rating"]
        .dropna()
        .astype(int)
        .value_counts()
        .sort_index()
    )

    if not ratings.empty:

        path = folder / "cms_star_rating_distribution.png"

        plt.figure(figsize=(7, 5))

        plt.bar(
            ratings.index.astype(str),
            ratings.values,
        )

        plt.xlabel(
            "CMS Overall Hospital Star Rating"
        )

        plt.ylabel(
            "Number of hospitals"
        )

        plt.title(
            "Distribution of CMS Overall Hospital Star Ratings"
        )

        plt.tight_layout()

        plt.savefig(
            path,
            dpi=200,
            bbox_inches="tight",
        )

        plt.close()

        paths.append(path)

    return paths