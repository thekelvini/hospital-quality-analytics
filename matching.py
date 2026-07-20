from __future__ import annotations

import pandas as pd
from rapidfuzz import fuzz, process

from config import AUTO_ACCEPT_SCORE, REVIEW_SCORE, CMS_NAME_ACCEPT_SCORE


def merge_cms(base: pd.DataFrame, cms: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    result=base.merge(cms,on='CCN',how='left',validate='many_to_one')
    result['CMS_Match_Method']=result['CMS_Hospital_Name'].notna().map({True:'CCN',False:'No match'})
    result['CMS_Name_Match_Score']=pd.NA
    reviews=[]
    grouped={s:g.reset_index(drop=True) for s,g in cms.groupby('CMS_State')}
    for idx,row in result[result['CMS_Hospital_Name'].isna()].iterrows():
        candidates=grouped.get(row['State'])
        if candidates is None or candidates.empty: continue
        choice=process.extractOne(row['Hospital_Normalized'],candidates['CMS_Normalized_Name'].tolist(),scorer=fuzz.token_set_ratio)
        if choice is None: continue
        _,score,pos=choice; candidate=candidates.iloc[pos]
        result.at[idx,'CMS_Name_Match_Score']=round(float(score),1)
        if score>=CMS_NAME_ACCEPT_SCORE:
            for col in ['CMS_Hospital_Name','CMS_State','CMS_City','CMS_Star_Rating','CMS_Normalized_Name']:
                result.at[idx,col]=candidate[col]
            result.at[idx,'CMS_Match_Method']='Exact/fuzzy hospital name'
        elif score>=85:
            reviews.append({'Hospital':row['Hospital'],'CCN':row['CCN'],'State':row['State'],'CMS_Candidate':candidate['CMS_Hospital_Name'],'Candidate_CCN':candidate['CCN'],'Candidate_Stars':candidate['CMS_Star_Rating'],'Match_Score':round(float(score),1),'Decision':''})
    return result,pd.DataFrame(reviews)


def match_bcbs(base: pd.DataFrame, bcbs: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    result=base.copy()
    result['Blue_Distinction']='No'; result['Blue_Distinction_Type']=pd.NA
    result['BCBS_Matched_Name']=pd.NA; result['BCBS_Match_Score']=pd.NA
    result['BCBS_Match_Method']='No match'; reviews=[]
    grouped={s:g.reset_index(drop=True) for s,g in bcbs.groupby('BCBS_State')}
    for idx,row in result.iterrows():
        candidates=grouped.get(row['State']); query=row['Hospital_Normalized']
        if candidates is None or candidates.empty or not query: continue
        exact=candidates[candidates['BCBS_Normalized_Name']==query]
        if not exact.empty:
            candidate=exact.iloc[0]; score=100.0; method='Exact normalized name'
        else:
            choice=process.extractOne(query,candidates['BCBS_Normalized_Name'].tolist(),scorer=fuzz.token_set_ratio)
            if choice is None: continue
            _,score,pos=choice; candidate=candidates.iloc[pos]; method='Fuzzy name'
        result.at[idx,'BCBS_Matched_Name']=candidate['BCBS_Hospital_Name']
        result.at[idx,'BCBS_Match_Score']=round(float(score),1)
        result.at[idx,'BCBS_Match_Method']=method
        if score>=AUTO_ACCEPT_SCORE:
            result.at[idx,'Blue_Distinction']='Yes'; result.at[idx,'Blue_Distinction_Type']=candidate['BCBS_Designation']
        elif score>=REVIEW_SCORE:
            result.at[idx,'Blue_Distinction']='Review'; result.at[idx,'Blue_Distinction_Type']=candidate['BCBS_Designation']
            reviews.append({'Hospital':row['Hospital'],'CCN':row['CCN'],'State':row['State'],'BCBS_Candidate':candidate['BCBS_Hospital_Name'],'Candidate_Type':candidate['BCBS_Designation'],'Match_Score':round(float(score),1),'Decision':''})
    return result,pd.DataFrame(reviews)
