"""Releases, source files and scorecard settings."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
WORK = ROOT / "data" / "work"
DB_PATH = WORK / "hqs.duckdb"
EXPORT = ROOT / "data" / "export"
DOCS_DATA = ROOT / "docs" / "data"

# Care Compare refreshes quarterly; we keep the summer release of three years.
# The 2024 and 2025 files come from the CMS hospitals archive, 2026 from the live catalog.
CMS = "https://data.cms.gov/provider-data"
RELEASES = {
    "2024-07": {"archive": f"{CMS}/sites/default/files/dataset-archives/theme/hospitals/hospitals_2024-07-31.zip"},
    "2025-07": {"archive": f"{CMS}/sites/default/files/dataset-archives/theme/hospitals/hospitals_2025-08-14.zip"},
    "2026-07": {"live": True},
}

# Provider Data Catalog dataset ids for the live release.
LIVE_DATASETS = {
    "general": "xubh-q36u",
    "hrrp": "9n3s-kdb3",
    "hcahps": "dgck-syfz",
    "hai": "77hc-ibv8",
    "tec": "yv7e-xc69",
}
FOOTNOTE_DATASET = "y9us-9xdf"

# file name pattern inside each release folder
SOURCE_GLOBS = {
    "general": "Hospital_General_Information.csv",
    "hrrp": "FY_*_Hospital_Readmissions_Reduction_Program_Hospital.csv",
    "hcahps": "HCAHPS-Hospital.csv",
    "hai": "Healthcare_Associated_Infections-Hospital.csv",
    "tec": "Timely_and_Effective_Care-Hospital.csv",
}

FOCUS_STATES = ["IN", "NJ"]
PEER_TYPE = "Acute Care Hospitals"

HRRP_CONDITIONS = {
    "READM-30-AMI-HRRP": "Heart attack (AMI)",
    "READM-30-HF-HRRP": "Heart failure",
    "READM-30-PN-HRRP": "Pneumonia",
    "READM-30-COPD-HRRP": "COPD",
    "READM-30-HIP-KNEE-HRRP": "Hip/knee replacement",
    "READM-30-CABG-HRRP": "CABG surgery",
}

HAI_MEASURES = {
    "HAI_1": "CLABSI",
    "HAI_2": "CAUTI",
    "HAI_3": "SSI colon",
    "HAI_4": "SSI abdominal hysterectomy",
    "HAI_5": "MRSA bacteremia",
    "HAI_6": "C. difficile",
}

# HCAHPS "top box" = most positive answer category.
HCAHPS_TOP_BOX = {
    "H_COMP_1_A_P": "Nurse communication",
    "H_COMP_2_A_P": "Doctor communication",
    "H_COMP_5_A_P": "Communication about medicines",
    "H_COMP_6_Y_P": "Discharge information",
    "H_CLEAN_HSP_A_P": "Room always clean",
    "H_QUIET_HSP_A_P": "Always quiet at night",
    "H_HSP_RATING_9_10": "Overall rating 9-10",
    "H_RECMND_DY": "Definitely recommend",
}

ED_MEASURES = {
    "OP_18b": "Median ED time, arrival to departure (min)",
    "OP_22": "Left before being seen (%)",
}
