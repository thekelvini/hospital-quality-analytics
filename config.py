from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"
FIGURE_DIR = OUTPUT_DIR / "figures"
LOG_DIR = OUTPUT_DIR / "logs"
DIAGNOSTIC_DIR = OUTPUT_DIR / "diagnostics"

BASE_RATE_FILE = DATA_DIR / "Hospital_Base_Rates_Simple_with_DRG_Legend.csv"
CMS_FILE = DATA_DIR / "cms_hospital_general_information.csv"
CMS_DATASET_ID = "xubh-q36u"
CMS_API_URL = f"https://data.cms.gov/provider-data/api/1/datastore/query/{CMS_DATASET_ID}/0"
CMS_BATCH_SIZE = 1500
CMS_MIN_EXPECTED_ROWS = 4000

BCBS_FILE_NAMES = [
    "Blue_Distinction_Spine_Surgery.pdf",
    "Blue_Distinction_Spine_Surgery.pdf.pdf",
    "Blue-Distinction-Spine-Surgery-Providers.pdf",
    "bcbs_spine_centers.csv",
]

AUTO_ACCEPT_SCORE = 92.0
REVIEW_SCORE = 82.0
CMS_NAME_ACCEPT_SCORE = 95.0
