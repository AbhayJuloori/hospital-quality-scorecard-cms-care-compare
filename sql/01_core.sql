-- Core model: one long fact table for every CMS value, plus hospital, measure and footnote dimensions.
-- Inputs are the stg_* tables (raw CSV text, one row per source row, with a release column).

CREATE OR REPLACE MACRO num(v) AS try_cast(replace(trim(v), ',', '') AS DOUBLE);

CREATE OR REPLACE MACRO fn_list(f) AS
    CASE WHEN f IS NULL OR trim(f) = '' THEN []::VARCHAR[]
         ELSE list_transform(string_split(f, ','), lambda x: trim(x)) END;

-- Status of a single CMS cell. Order matters: a blank cell is "missing" even if footnoted;
-- a non-numeric cell with footnote 1 (too few cases) or 4 (suppressed by CMS) is "suppressed".
CREATE OR REPLACE MACRO cell_status(v, f) AS
    CASE
        WHEN v IS NULL OR trim(v) = '' THEN 'missing'
        WHEN num(v) IS NULL AND (trim(v) = 'Too Few to Report'
             OR list_contains(fn_list(f), '1') OR list_contains(fn_list(f), '4')) THEN 'suppressed'
        WHEN trim(v) IN ('Not Available', 'N/A', 'Not Applicable', '--') THEN 'not_available'
        WHEN num(v) IS NOT NULL AND len(fn_list(f)) > 0 THEN 'reported_footnoted'
        WHEN num(v) IS NOT NULL THEN 'reported'
        ELSE 'categorical'
    END;

CREATE OR REPLACE TABLE dim_footnote AS
SELECT CAST("Footnote" AS VARCHAR) AS footnote_code, "Footnote Text" AS footnote_text
FROM stg_footnote;

CREATE OR REPLACE TABLE dim_hospital AS
SELECT
    release,
    "Facility ID"                AS facility_id,
    "Facility Name"              AS facility_name,
    "City/Town"                  AS city,
    "State"                      AS state,
    "County/Parish"              AS county,
    "Hospital Type"              AS hospital_type,
    "Hospital Ownership"         AS ownership,
    "Emergency Services"         AS emergency_services,
    num("Hospital overall rating") AS overall_star_rating,
    "Hospital overall rating footnote" AS overall_star_footnote
FROM stg_general;

CREATE OR REPLACE TABLE fact_measure AS
WITH u AS (
    SELECT release, 'general' AS source, "Facility ID" AS facility_id,
           'STAR_OVERALL' AS measure_id, 'Hospital overall star rating' AS measure_name,
           "Hospital overall rating" AS value_raw, "Hospital overall rating footnote" AS footnote,
           NULL::VARCHAR AS start_raw, NULL::VARCHAR AS end_raw, NULL::VARCHAR AS denom_raw
    FROM stg_general
    UNION ALL
    SELECT release, 'hrrp', "Facility ID", "Measure Name", "Measure Name",
           "Excess Readmission Ratio", "Footnote", "Start Date", "End Date", "Number of Discharges"
    FROM stg_hrrp
    UNION ALL
    SELECT release, 'hcahps', "Facility ID", "HCAHPS Measure ID", "HCAHPS Answer Description",
           CASE WHEN "HCAHPS Measure ID" LIKE '%STAR_RATING' THEN "Patient Survey Star Rating"
                WHEN "HCAHPS Measure ID" LIKE '%LINEAR_SCORE' THEN "HCAHPS Linear Mean Value"
                ELSE "HCAHPS Answer Percent" END,
           CASE WHEN "HCAHPS Measure ID" LIKE '%STAR_RATING' THEN "Patient Survey Star Rating Footnote"
                WHEN "HCAHPS Measure ID" LIKE '%LINEAR_SCORE' THEN "Number of Completed Surveys Footnote"
                ELSE "HCAHPS Answer Percent Footnote" END,
           "Start Date", "End Date", "Number of Completed Surveys"
    FROM stg_hcahps
    UNION ALL
    SELECT release, 'hai', "Facility ID", "Measure ID", "Measure Name",
           "Score", "Footnote", "Start Date", "End Date", NULL
    FROM stg_hai
    UNION ALL
    SELECT release, 'tec', "Facility ID", "Measure ID", "Measure Name",
           "Score", "Footnote", "Start Date", "End Date", "Sample"
    FROM stg_tec
)
SELECT
    release, source, facility_id, measure_id, measure_name,
    value_raw,
    num(value_raw)                        AS value_num,
    NULLIF(trim(footnote), '')            AS footnote,
    cell_status(value_raw, footnote)      AS status,
    try_strptime(start_raw, '%m/%d/%Y')::DATE AS period_start,
    try_strptime(end_raw, '%m/%d/%Y')::DATE   AS period_end,
    num(denom_raw)                        AS denominator
FROM u;

CREATE OR REPLACE TABLE dim_measure AS
SELECT
    source,
    measure_id,
    arg_max(measure_name, release) AS measure_name,
    CASE
        WHEN source = 'hrrp' THEN 'Readmissions'
        WHEN source = 'hai' THEN 'Infections'
        WHEN source = 'hcahps' THEN 'Patient experience'
        WHEN source = 'tec' THEN 'Timely and effective care'
        ELSE 'Overall'
    END AS domain,
    CASE
        WHEN source = 'hrrp' OR measure_id LIKE 'HAI_%_SIR' OR measure_id IN ('OP_18a', 'OP_18b', 'OP_18c', 'OP_18d', 'OP_22')
            THEN 'lower_is_better'
        WHEN measure_id LIKE '%_A_P' OR measure_id IN ('H_HSP_RATING_9_10', 'H_RECMND_DY', 'H_COMP_6_Y_P', 'STAR_OVERALL')
             OR measure_id LIKE '%STAR_RATING'
            THEN 'higher_is_better'
        ELSE 'context'
    END AS direction,
    min(release) AS first_release,
    max(release) AS last_release
FROM fact_measure
GROUP BY source, measure_id;
