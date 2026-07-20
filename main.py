from __future__ import annotations

import argparse
import traceback
import pandas as pd

from analysis import create_figures, run_statistics
from cms_downloader import download_complete_cms
from config import CMS_FILE, DATA_DIR, DIAGNOSTIC_DIR, FIGURE_DIR, LOG_DIR, OUTPUT_DIR
from data_sources import load_base_rates, load_bcbs, load_cms, to_long
from excel_output import write_master_workbook
from matching import match_bcbs, merge_cms
from reporting import create_powerpoint, create_word_report
from utils import ensure_directories


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument('--use-local-cms',action='store_true',help='Do not refresh CMS data. Use the local CMS CSV.'); args=parser.parse_args()
    ensure_directories(DATA_DIR,OUTPUT_DIR,FIGURE_DIR,LOG_DIR,DIAGNOSTIC_DIR)
    if not args.use_local_cms:
        download_complete_cms(CMS_FILE,force=True)
    print('1. Reading hospital base-rate data...'); base=load_base_rates(); print(f'   Loaded {len(base):,} hospitals.')
    print('2. Reading complete CMS Hospital General Information data...'); cms=load_cms(); print(f'   Loaded {len(cms):,} CMS hospitals.')
    print('3. Reading local BCBS Spine Surgery directory...'); bcbs=load_bcbs(); print(f'   Extracted {len(bcbs):,} BCBS hospital designations.')
    print('4. Matching CMS hospitals by CCN and fallback name...'); master,cms_review=merge_cms(base,cms)
    print('5. Matching Blue Distinction hospitals by state and name...'); master,bcbs_review=match_bcbs(master,bcbs)
    long_data=to_long(master)
    print('6. Running statistical analyses...'); results,summary,descriptive,model_text=run_statistics(master,long_data)
    figures=create_figures(summary,FIGURE_DIR)
    match_summary=pd.DataFrame([
        {'Metric':'Hospitals in base-rate dataset','Value':len(master)},
        {'Metric':'CMS source hospitals','Value':len(cms)},
        {'Metric':'CMS matches by CCN','Value':int((master['CMS_Match_Method']=='CCN').sum())},
        {'Metric':'CMS fallback name matches','Value':int((master['CMS_Match_Method']=='Exact/fuzzy hospital name').sum())},
        {'Metric':'CMS ratings available','Value':int(master['CMS_Star_Rating'].notna().sum())},
        {'Metric':'Blue Distinction accepted','Value':int((master['Blue_Distinction']=='Yes').sum())},
        {'Metric':'Blue Distinction manual review','Value':int((master['Blue_Distinction']=='Review').sum())},
    ])
    master_csv=OUTPUT_DIR/'Hospital_Quality_Master.csv'; master.to_csv(master_csv,index=False)
    combined_review=pd.concat([cms_review.assign(Review_Type='CMS'),bcbs_review.assign(Review_Type='BCBS')],ignore_index=True,sort=False)
    combined_review.to_excel(OUTPUT_DIR/'Manual_Review.xlsx',index=False)
    write_master_workbook(OUTPUT_DIR/'Hospital_Quality_Master.xlsx',**{'Master Data':master,'Long DRG Data':long_data,'CMS Source':cms,'BCBS Source':bcbs,'Manual Review':combined_review,'Hospital Summary':summary,'Match Summary':match_summary,'Statistical Results':results,'Descriptive Statistics':descriptive})
    write_master_workbook(OUTPUT_DIR/'Statistical_Results.xlsx',**{'Statistical Results':results,'Hospital Summary':summary,'Descriptive Statistics':descriptive,'Match Summary':match_summary,'Regression Output':pd.DataFrame({'Model Output':model_text.splitlines()})})
    create_word_report(OUTPUT_DIR/'Hospital_Quality_Report.docx',results,match_summary,figures)
    create_powerpoint(OUTPUT_DIR/'Hospital_Quality_Presentation.pptx',results,match_summary,figures)
    print('\nCompleted successfully.')
    for p in [master_csv,OUTPUT_DIR/'Hospital_Quality_Master.xlsx',OUTPUT_DIR/'Statistical_Results.xlsx',OUTPUT_DIR/'Hospital_Quality_Report.docx',OUTPUT_DIR/'Hospital_Quality_Presentation.pptx',OUTPUT_DIR/'Manual_Review.xlsx']:
        print(f'  {p}')

if __name__=='__main__':
    try: main()
    except Exception as error:
        print('\nPROJECT STOPPED'); print(str(error)); print('\nDetailed error:'); traceback.print_exc(); raise SystemExit(1)
