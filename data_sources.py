from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber

from config import BASE_RATE_FILE, BCBS_FILE_NAMES, CMS_FILE, DATA_DIR, DIAGNOSTIC_DIR
from utils import find_column, find_existing_file, normalize_ccn, normalize_name, normalize_state, parse_money

STATE_CODES = {"AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"}


def load_base_rates() -> pd.DataFrame:
    if not BASE_RATE_FILE.exists():
        raise FileNotFoundError(f"Base-rate file not found: {BASE_RATE_FILE}")
    df = pd.read_csv(BASE_RATE_FILE, dtype=str, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    hospital = find_column(df.columns, ["Hospital", "Hospital Name", "Facility Name"])
    ccn = find_column(df.columns, ["CCN", "Facility ID", "Provider ID"])
    state = find_column(df.columns, ["State"])
    if not all([hospital, ccn, state]):
        raise ValueError(f"Base file must contain Hospital, CCN, and State. Columns: {list(df.columns)}")
    df = df.rename(columns={hospital:"Hospital", ccn:"CCN", state:"State"})
    df["CCN"] = df["CCN"].map(normalize_ccn)
    df["State"] = df["State"].map(normalize_state)
    df["Hospital_Normalized"] = df["Hospital"].map(normalize_name)
    drgs = [c for c in df.columns if str(c).strip().isdigit()]
    if not drgs:
        raise ValueError("No numeric DRG columns were found.")
    for col in drgs:
        df[col] = parse_money(df[col])
    df["Average_Base_Rate"] = df[drgs].mean(axis=1, skipna=True)
    df["Positive_DRG_Count"] = (df[drgs].fillna(0) > 0).sum(axis=1)
    return df


def load_cms() -> pd.DataFrame:
    if not CMS_FILE.exists():
        raise FileNotFoundError(f"CMS file not found: {CMS_FILE}")
    cms = pd.read_csv(CMS_FILE, dtype=str, low_memory=False)
    ccn = find_column(cms.columns, ["facility_id","facility id","ccn","provider id"])
    name = find_column(cms.columns, ["facility_name","facility name","hospital name","provider name"])
    state = find_column(cms.columns, ["state","hospital_state"])
    city = find_column(cms.columns, ["citytown","city/town","city","hospital_city"])
    rating = find_column(cms.columns, ["hospital_overall_rating","hospital overall rating","overall hospital rating","overall_rating","star rating"])
    if not all([ccn, name, rating]):
        raise ValueError(f"CMS file lacks CCN, hospital name, or rating. Columns: {list(cms.columns)}")
    result = pd.DataFrame({
        "CCN": cms[ccn].map(normalize_ccn),
        "CMS_Hospital_Name": cms[name].astype(str).str.strip(),
        "CMS_State": cms[state].map(normalize_state) if state else "",
        "CMS_City": cms[city].astype(str).str.strip() if city else "",
        "CMS_Star_Rating": pd.to_numeric(cms[rating].replace({"Not Available":pd.NA,"Not Applicable":pd.NA,"N/A":pd.NA,"":pd.NA}), errors="coerce"),
    })
    result["CMS_Normalized_Name"] = result["CMS_Hospital_Name"].map(normalize_name)
    return result[result["CCN"] != ""].drop_duplicates("CCN", keep="first").reset_index(drop=True)


def _clean(value: object) -> str:
    if value is None: return ""
    return re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip()


def _designation(values: list[str]) -> str:
    text = " ".join(values).upper()
    if re.search(r"\bBDC\s*\+", text): return "BDC+"
    if re.search(r"\bBDC\b", text): return "BDC"
    return ""


def _state(values: list[str]) -> str:
    for value in values:
        value = value.upper().strip()
        if value in STATE_CODES: return value
    for value in values:
        for token in re.findall(r"\b[A-Z]{2}\b", value.upper()):
            if token in STATE_CODES: return token
    return ""


def _provider(values: list[str]) -> str:
    if values:
        first = _clean(values[0])
        if first and first.upper() not in {"PROVIDER NAME","FACILITY NAME"}: return first
    terms=("HOSPITAL","MEDICAL","HEALTH","CLINIC","UNIVERSITY","REGIONAL","MEMORIAL","SURGICAL")
    candidates=[]
    for value in values:
        text=_clean(value); upper=text.upper()
        if not text or upper in STATE_CODES or re.fullmatch(r"BDC\+?", upper): continue
        candidates.append((len(text)+(100 if any(t in upper for t in terms) else 0), text))
    return max(candidates, default=(0,""))[1]


def _parse_bcbs_pdf(path: Path) -> pd.DataFrame:
    records=[]; diagnostics=[]
    with pdfplumber.open(path) as pdf:
        for page_num,page in enumerate(pdf.pages,start=1):
            for table_num,table in enumerate(page.extract_tables() or [],start=1):
                for row_num,row in enumerate(table or [],start=1):
                    values=[_clean(v) for v in (row or [])]; nonempty=[v for v in values if v]
                    if not nonempty: continue
                    diagnostics.append({"Page":page_num,"Table":table_num,"Row":row_num,"Extracted_Row":" | ".join(nonempty)})
                    joined=" ".join(nonempty).upper()
                    if "PROVIDER NAME" in joined or "DESIGNATION TYPE" in joined: continue
                    designation=_designation(nonempty); state=_state(nonempty); provider=_provider(values)
                    center_type=next((v for v in nonempty if v.upper() in {"HOSPITAL","ASC"}),"")
                    if provider and designation and state and center_type.upper() != "ASC":
                        records.append({"BCBS_Hospital_Name":provider,"BCBS_State":state,"BCBS_Designation":designation,"BCBS_Page":page_num,"BCBS_Source_Row":" | ".join(nonempty)})
    pd.DataFrame(diagnostics).to_csv(DIAGNOSTIC_DIR/'bcbs_pdf_extraction_diagnostic.csv',index=False)
    if not records:
        raise RuntimeError("The BCBS PDF opened, but no hospital records were extracted. See output/diagnostics/bcbs_pdf_extraction_diagnostic.csv.")
    return pd.DataFrame(records)


def _load_bcbs_csv(path: Path) -> pd.DataFrame:
    df=pd.read_csv(path,dtype=str,low_memory=False)
    name=find_column(df.columns,["BCBS_Hospital_Name","Hospital","Facility Name","Provider Name"])
    state=find_column(df.columns,["BCBS_State","State"])
    designation=find_column(df.columns,["BCBS_Designation","Designation","Designation Type","Blue Distinction"])
    if name is None or state is None: raise ValueError("BCBS CSV requires hospital and state columns.")
    return pd.DataFrame({"BCBS_Hospital_Name":df[name].astype(str).str.strip(),"BCBS_State":df[state].map(normalize_state),"BCBS_Designation":df[designation].astype(str).str.strip() if designation else "BDC","BCBS_Page":"","BCBS_Source_Row":""})


def load_bcbs() -> pd.DataFrame:
    path=find_existing_file(DATA_DIR,BCBS_FILE_NAMES)
    if path is None:
        raise FileNotFoundError("Place Blue_Distinction_Spine_Surgery.pdf in the data folder before running the project.")
    data=_load_bcbs_csv(path) if path.suffix.lower()=='.csv' else _parse_bcbs_pdf(path)
    data["BCBS_State"]=data["BCBS_State"].map(normalize_state)
    designation=data["BCBS_Designation"].astype(str).str.upper().str.replace(" ","",regex=False)
    data["BCBS_Designation"]=designation.where(designation.isin(["BDC","BDC+"]),"BDC")
    data["BCBS_Normalized_Name"]=data["BCBS_Hospital_Name"].map(normalize_name)
    data=data[(data["BCBS_Normalized_Name"]!="")&(data["BCBS_State"]!="")]
    data=data.drop_duplicates(["BCBS_Normalized_Name","BCBS_State","BCBS_Designation"],keep="first")
    data.to_csv(DATA_DIR/'bcbs_spine_centers_extracted.csv',index=False)
    return data.reset_index(drop=True)


def to_long(master: pd.DataFrame) -> pd.DataFrame:
    drgs=[c for c in master.columns if str(c).isdigit()]
    ids=[c for c in master.columns if c not in drgs]
    long=master.melt(id_vars=ids,value_vars=drgs,var_name='DRG',value_name='Base_Rate')
    long['DRG']=long['DRG'].astype(str)
    long['Base_Rate']=pd.to_numeric(long['Base_Rate'],errors='coerce')
    return long[long['Base_Rate'].notna() & (long['Base_Rate']>0)].copy()
