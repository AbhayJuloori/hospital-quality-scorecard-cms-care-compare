"""KPI definitions shared by the data dictionary, the Excel workbook and the DAX measures."""
from __future__ import annotations

KPI_DEFS = [
    {
        "kpi": "Overall star rating",
        "column": "overall_star_rating",
        "domain": "Overall",
        "source_file": "Hospital_General_Information.csv",
        "cms_field": "Hospital overall rating",
        "definition": "CMS overall hospital quality star rating (1-5), built by CMS from up to 5 measure groups.",
        "hospital_formula": "Published value; 'Not Available' kept as blank with its footnote.",
        "peer_rule": "Mean of rated hospitals",
        "direction": "higher is better",
        "dax": "Avg Star Rating",
    },
    {
        "kpi": "Excess readmission ratio (ERR)",
        "column": "err_mean",
        "domain": "Readmissions",
        "source_file": "FY_<year>_Hospital_Readmissions_Reduction_Program_Hospital.csv",
        "cms_field": "Excess Readmission Ratio (6 conditions: AMI, HF, PN, COPD, hip/knee, CABG)",
        "definition": "Predicted / expected 30-day readmission rate under HRRP. Above 1.0 means more readmissions "
                      "than an average hospital with the same patients.",
        "hospital_formula": "Per condition: published ERR (ties out to predicted / expected). "
                            "Hospital summary: unweighted mean of reported condition ERRs.",
        "peer_rule": "Median of hospital summary ERRs (discharge counts are suppressed for small cells, "
                     "so a discharge-weighted pool would silently drop small hospitals)",
        "direction": "lower is better",
        "dax": "ERR Mean / ERR Peer Median / Conditions ERR > 1",
    },
    {
        "kpi": "Standardized infection ratio (SIR)",
        "column": "sir_clabsi, sir_cauti, sir_ssi_colon, sir_mrsa, sir_cdiff",
        "domain": "Infections",
        "source_file": "Healthcare_Associated_Infections-Hospital.csv",
        "cms_field": "HAI_n_SIR, HAI_n_NUMERATOR (observed), HAI_n_ELIGCASES (predicted), CI bounds",
        "definition": "Observed / predicted healthcare-associated infections (CDC NHSN baseline). "
                      "Below 1.0 means fewer infections than predicted.",
        "hospital_formula": "Published SIR per infection type (ties out to observed / predicted).",
        "peer_rule": "Pooled SIR = sum(observed) / sum(predicted), the NHSN method; never an average of SIRs",
        "direction": "lower is better",
        "dax": "SIR Pooled",
    },
    {
        "kpi": "HCAHPS top box %",
        "column": "hcahps_nurse_comm, hcahps_doctor_comm, hcahps_clean, hcahps_rating_9_10, hcahps_recommend",
        "domain": "Patient experience",
        "source_file": "HCAHPS-Hospital.csv",
        "cms_field": "HCAHPS Answer Percent for *_A_P, H_HSP_RATING_9_10, H_RECMND_DY, H_COMP_6_Y_P",
        "definition": "Share of surveyed patients giving the most positive answer (e.g. nurses 'always' "
                      "communicated well; rating 9-10; 'definitely' recommend). CMS publishes these "
                      "patient-mix adjusted.",
        "hospital_formula": "Published percent; footnote 6/10 (fewer than 100/50 surveys) kept as a caution flag.",
        "peer_rule": "Completed-survey weighted mean of hospital percents",
        "direction": "higher is better",
        "dax": "Top Box % (Survey Weighted)",
    },
    {
        "kpi": "Median ED time (OP-18b)",
        "column": "ed_median_minutes",
        "domain": "ED timeliness",
        "source_file": "Timely_and_Effective_Care-Hospital.csv",
        "cms_field": "OP_18b Score",
        "definition": "Median minutes from ED arrival to departure for discharged patients, excluding "
                      "psychiatric/mental health patients and transfers.",
        "hospital_formula": "Published median.",
        "peer_rule": "Median of hospital medians (medians cannot be averaged or pooled)",
        "direction": "lower is better",
        "dax": "ED Median Minutes / ED Peer Median",
    },
    {
        "kpi": "Left before being seen (OP-22)",
        "column": "ed_left_without_seen_pct",
        "domain": "ED timeliness",
        "source_file": "Timely_and_Effective_Care-Hospital.csv",
        "cms_field": "OP_22 Score",
        "definition": "Percent of ED patients who left before being seen by a provider.",
        "hospital_formula": "Published percent.",
        "peer_rule": "Median of hospital values",
        "direction": "lower is better",
        "dax": "LWBS %",
    },
]

REQUIREMENTS = [
    ("REQ-01", "Scorecard lists every hospital in the focus state for the latest release, with star rating, "
               "readmissions, infections, patient experience and ED timeliness on one row."),
    ("REQ-02", "Every KPI value traces back to a single published CMS cell or a documented aggregate of them."),
    ("REQ-03", "Suppressed, footnoted, unavailable and missing values are flagged, never shown as zero."),
    ("REQ-04", "Peer benchmarks (state and national acute care) use the pooling rule defined per KPI."),
    ("REQ-05", "Trend view covers three annual releases; measures retired or renamed between releases are listed."),
    ("REQ-06", "Raw-to-model row counts reconcile for every file and release before the scorecard refreshes."),
]

# which requirement each automated check evidences
CHECK_REQ = {
    "DQ01": "REQ-06", "DQ02": "REQ-02", "DQ03": "REQ-02", "DQ04": "REQ-03", "DQ05": "REQ-03",
    "DQ06": "REQ-05", "DQ07": "REQ-03", "TO01": "REQ-02", "TO02": "REQ-02", "TO03": "REQ-02",
    "TO04": "REQ-02", "TO05": "REQ-02", "TO06": "REQ-01",
}
