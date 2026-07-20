from __future__ import annotations

from pathlib import Path
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import mannwhitneyu, spearmanr, ttest_ind


def hospital_summary(master: pd.DataFrame,long_data: pd.DataFrame)->pd.DataFrame:
    rates=long_data.groupby('CCN',as_index=False).agg(Average_Base_Rate=('Base_Rate','mean'),Median_Base_Rate=('Base_Rate','median'),DRG_Count=('DRG','nunique'))
    cols=['CCN','Hospital','State','Blue_Distinction','Blue_Distinction_Type','CMS_Star_Rating','CMS_Match_Method','CMS_Hospital_Name','BCBS_Matched_Name','BCBS_Match_Score','BCBS_Match_Method']
    return master[[c for c in cols if c in master.columns]].drop_duplicates('CCN').merge(rates,on='CCN',how='left')


def _cohen_d(x: pd.Series,y: pd.Series)->float:
    nx,ny=len(x),len(y)
    pooled=np.sqrt(((nx-1)*x.var(ddof=1)+(ny-1)*y.var(ddof=1))/(nx+ny-2))
    return float((x.mean()-y.mean())/pooled) if pooled and not np.isnan(pooled) else np.nan


def run_statistics(master: pd.DataFrame,long_data: pd.DataFrame):
    summary=hospital_summary(master,long_data); rows=[]; model_text=[]
    eligible=summary[summary['Blue_Distinction'].isin(['Yes','No'])]
    yes=eligible.loc[eligible['Blue_Distinction']=='Yes','Average_Base_Rate'].dropna(); no=eligible.loc[eligible['Blue_Distinction']=='No','Average_Base_Rate'].dropna()
    if len(yes)>=2 and len(no)>=2:
        t=ttest_ind(yes,no,equal_var=False,alternative='greater')
        u=mannwhitneyu(yes,no,alternative='greater')
        rows += [
            {'Analysis':'Hospital-level Welch t-test','Estimate':yes.mean()-no.mean(),'P_Value':t.pvalue,'N':len(yes)+len(no),'Effect_Size':_cohen_d(yes,no),'Interpretation':'Mean difference: Blue Distinction minus non-Blue Distinction'},
            {'Analysis':'Mann-Whitney U test','Estimate':u.statistic,'P_Value':u.pvalue,'N':len(yes)+len(no),'Effect_Size':np.nan,'Interpretation':'Nonparametric comparison of hospital average base rates'},
        ]
    reg=long_data.copy()
    reg=reg[reg['Base_Rate'].gt(0)&reg['Blue_Distinction'].isin(['Yes','No'])].copy()
    if reg['Blue_Distinction'].nunique()==2 and reg['DRG'].nunique()>=2:
        reg['Blue_Distinction_Flag']=(reg['Blue_Distinction']=='Yes').astype(int); reg['Log_Base_Rate']=np.log(reg['Base_Rate'])
        try:
            m=smf.ols('Log_Base_Rate ~ Blue_Distinction_Flag + C(DRG)',data=reg).fit(cov_type='cluster',cov_kwds={'groups':reg['CCN']})
            coef=m.params['Blue_Distinction_Flag']
            rows.append({'Analysis':'DRG-adjusted log-linear regression','Estimate':(np.exp(coef)-1)*100,'P_Value':m.pvalues['Blue_Distinction_Flag'],'N':int(m.nobs),'Effect_Size':np.nan,'Interpretation':'Percent difference associated with Blue Distinction'})
            model_text.append(m.summary().as_text())
        except Exception as e: warnings.warn(f'DRG regression skipped: {e}')
    cms=summary.dropna(subset=['CMS_Star_Rating','Average_Base_Rate']).copy()
    if len(cms)>=5 and cms['CMS_Star_Rating'].nunique()>=2:
        rho,p=spearmanr(cms['CMS_Star_Rating'],cms['Average_Base_Rate'])
        rows.append({'Analysis':'CMS Spearman correlation','Estimate':rho,'P_Value':p,'N':len(cms),'Effect_Size':np.nan,'Interpretation':'Association between CMS stars and average base rate'})
        cms['Log_Average_Base_Rate']=np.log(cms['Average_Base_Rate'])
        m=smf.ols('Log_Average_Base_Rate ~ CMS_Star_Rating',data=cms).fit(cov_type='HC3')
        coef=m.params['CMS_Star_Rating']
        rows.append({'Analysis':'CMS log-linear regression','Estimate':(np.exp(coef)-1)*100,'P_Value':m.pvalues['CMS_Star_Rating'],'N':int(m.nobs),'Effect_Size':np.nan,'Interpretation':'Percent difference per additional CMS star'})
        model_text.append(m.summary().as_text())
    desc=summary.groupby('Blue_Distinction',dropna=False)['Average_Base_Rate'].agg(['count','mean','median','std','min','max']).reset_index()
    return pd.DataFrame(rows), summary, desc, "\n\n".join(model_text)


def create_figures(summary: pd.DataFrame,folder: Path)->list[Path]:
    folder.mkdir(parents=True,exist_ok=True); paths=[]
    rates=summary['Average_Base_Rate'].dropna()
    if not rates.empty:
        p=folder/'average_base_rate_histogram.png'; plt.figure(figsize=(8,5)); plt.hist(rates,bins=25); plt.xlabel('Average hospital base rate'); plt.ylabel('Hospitals'); plt.title('Distribution of Average Hospital Base Rates'); plt.tight_layout(); plt.savefig(p,dpi=200); plt.close(); paths.append(p)
    groups=summary[summary['Blue_Distinction'].isin(['Yes','No'])]
    if groups['Blue_Distinction'].nunique()==2:
        no=groups.loc[groups['Blue_Distinction']=='No','Average_Base_Rate'].dropna(); yes=groups.loc[groups['Blue_Distinction']=='Yes','Average_Base_Rate'].dropna()
        if not no.empty and not yes.empty:
            p=folder/'blue_distinction_boxplot.png'; plt.figure(figsize=(7,5)); plt.boxplot([no,yes],tick_labels=['No','Yes']); plt.xlabel('Blue Distinction'); plt.ylabel('Average hospital base rate'); plt.title('Base Rates by Blue Distinction Status'); plt.tight_layout(); plt.savefig(p,dpi=200); plt.close(); paths.append(p)
    cms=summary.dropna(subset=['CMS_Star_Rating','Average_Base_Rate'])
    if len(cms)>=2:
        p=folder/'cms_rating_scatterplot.png'; plt.figure(figsize=(7,5)); plt.scatter(cms['CMS_Star_Rating'],cms['Average_Base_Rate']); plt.xlabel('CMS Overall Hospital Star Rating'); plt.ylabel('Average hospital base rate'); plt.title('CMS Star Rating and Average Base Rate'); plt.tight_layout(); plt.savefig(p,dpi=200); plt.close(); paths.append(p)
    return paths
