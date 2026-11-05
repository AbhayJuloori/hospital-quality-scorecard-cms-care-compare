-- KPI marts. Every value here is a CMS published value or a documented aggregate of them.

-- Readmissions (HRRP): one row per hospital x condition x release.
CREATE OR REPLACE TABLE mart_hrrp AS
SELECT
    release,
    "Facility ID"                              AS facility_id,
    "Measure Name"                             AS measure_id,
    num("Number of Discharges")                AS discharges,
    num("Excess Readmission Ratio")            AS excess_readmission_ratio,
    num("Predicted Readmission Rate")          AS predicted_rate,
    num("Expected Readmission Rate")           AS expected_rate,
    num("Number of Readmissions")              AS readmissions,
    NULLIF(trim("Footnote"), '')               AS footnote,
    cell_status("Excess Readmission Ratio", "Footnote") AS status,
    try_strptime("Start Date", '%m/%d/%Y')::DATE AS period_start,
    try_strptime("End Date", '%m/%d/%Y')::DATE   AS period_end
FROM stg_hrrp;

-- Infections (HAI): pivot the six rows CMS publishes per infection type into one.
-- NUMERATOR = observed infections, ELIGCASES = predicted infections, SIR = observed / predicted.
CREATE OR REPLACE TABLE mart_hai AS
SELECT
    release,
    facility_id,
    split_part(measure_id, '_', 1) || '_' || split_part(measure_id, '_', 2) AS hai_id,
    max(value_num) FILTER (WHERE measure_id LIKE '%_SIR')       AS sir,
    max(value_num) FILTER (WHERE measure_id LIKE '%_NUMERATOR') AS observed,
    max(value_num) FILTER (WHERE measure_id LIKE '%_ELIGCASES') AS predicted,
    max(value_num) FILTER (WHERE measure_id LIKE '%_CILOWER')   AS ci_lower,
    max(value_num) FILTER (WHERE measure_id LIKE '%_CIUPPER')   AS ci_upper,
    max(value_num) FILTER (WHERE measure_id LIKE '%_DOPC')      AS device_or_patient_days,
    max(status)    FILTER (WHERE measure_id LIKE '%_SIR')       AS sir_status,
    max(footnote)  FILTER (WHERE measure_id LIKE '%_SIR')       AS sir_footnote
FROM fact_measure
WHERE source = 'hai'
GROUP BY ALL;

CREATE OR REPLACE TABLE mart_hai_compared AS
SELECT release, "Facility ID" AS facility_id,
       split_part("Measure ID", '_', 1) || '_' || split_part("Measure ID", '_', 2) AS hai_id,
       "Compared to National" AS compared_to_national
FROM stg_hai WHERE "Measure ID" LIKE '%_SIR';

-- Patient experience (HCAHPS) top box: the most positive answer for each composite.
CREATE OR REPLACE TABLE mart_hcahps_topbox AS
SELECT
    f.release, f.facility_id, f.measure_id, f.value_num AS top_box_pct, f.status, f.footnote,
    f.denominator AS completed_surveys
FROM fact_measure f
JOIN kpi_topbox k USING (measure_id)
WHERE f.source = 'hcahps';

-- Emergency department timeliness.
CREATE OR REPLACE TABLE mart_ed AS
SELECT release, facility_id, measure_id, value_num AS value, status, footnote, denominator AS sample
FROM fact_measure
WHERE source = 'tec' AND measure_id IN ('OP_18b', 'OP_22');

-- One row per hospital per release: the scorecard grain.
CREATE OR REPLACE TABLE mart_scorecard AS
WITH r AS (
    SELECT release, facility_id,
           avg(excess_readmission_ratio)                         AS err_mean,
           count(excess_readmission_ratio)                       AS err_conditions_reported,
           count(*) FILTER (WHERE excess_readmission_ratio > 1)  AS err_conditions_above_1,
           max(excess_readmission_ratio) FILTER (WHERE measure_id = 'READM-30-HF-HRRP') AS err_hf,
           max(excess_readmission_ratio) FILTER (WHERE measure_id = 'READM-30-PN-HRRP') AS err_pn,
           max(excess_readmission_ratio) FILTER (WHERE measure_id = 'READM-30-AMI-HRRP') AS err_ami,
           max(excess_readmission_ratio) FILTER (WHERE measure_id = 'READM-30-COPD-HRRP') AS err_copd
    FROM mart_hrrp GROUP BY ALL
), h AS (
    SELECT release, facility_id,
           max(sir) FILTER (WHERE hai_id = 'HAI_1') AS sir_clabsi,
           max(sir) FILTER (WHERE hai_id = 'HAI_2') AS sir_cauti,
           max(sir) FILTER (WHERE hai_id = 'HAI_3') AS sir_ssi_colon,
           max(sir) FILTER (WHERE hai_id = 'HAI_5') AS sir_mrsa,
           max(sir) FILTER (WHERE hai_id = 'HAI_6') AS sir_cdiff
    FROM mart_hai GROUP BY ALL
), p AS (
    SELECT release, facility_id,
           max(top_box_pct) FILTER (WHERE measure_id = 'H_COMP_1_A_P')      AS hcahps_nurse_comm,
           max(top_box_pct) FILTER (WHERE measure_id = 'H_COMP_2_A_P')      AS hcahps_doctor_comm,
           max(top_box_pct) FILTER (WHERE measure_id = 'H_CLEAN_HSP_A_P')   AS hcahps_clean,
           max(top_box_pct) FILTER (WHERE measure_id = 'H_HSP_RATING_9_10') AS hcahps_rating_9_10,
           max(top_box_pct) FILTER (WHERE measure_id = 'H_RECMND_DY')       AS hcahps_recommend,
           max(completed_surveys)                                          AS hcahps_surveys
    FROM mart_hcahps_topbox GROUP BY ALL
), e AS (
    SELECT release, facility_id,
           max(value) FILTER (WHERE measure_id = 'OP_18b') AS ed_median_minutes,
           max(value) FILTER (WHERE measure_id = 'OP_22')  AS ed_left_without_seen_pct
    FROM mart_ed GROUP BY ALL
)
SELECT d.release, d.facility_id, d.facility_name, d.city, d.state, d.hospital_type, d.ownership,
       d.emergency_services, d.overall_star_rating,
       r.* EXCLUDE (release, facility_id),
       h.* EXCLUDE (release, facility_id),
       p.* EXCLUDE (release, facility_id),
       e.* EXCLUDE (release, facility_id)
FROM dim_hospital d
LEFT JOIN r USING (release, facility_id)
LEFT JOIN h USING (release, facility_id)
LEFT JOIN p USING (release, facility_id)
LEFT JOIN e USING (release, facility_id);

-- Peer benchmarks. Pooling rules differ by KPI and are documented in the data dictionary:
--   ERR: median of hospital ERRs (CMS publishes no discharge counts for small cells, so a weighted pool would drop them)
--   SIR: sum(observed) / sum(predicted), the CDC NHSN way to pool SIRs
--   HCAHPS top box: completed-survey weighted mean of hospital percentages
--   ED median time: median of hospital medians (medians cannot be averaged)
CREATE OR REPLACE TABLE mart_peer AS
WITH groups AS (
    SELECT release, facility_id, 'National acute care' AS peer_group
    FROM dim_hospital WHERE hospital_type = 'Acute Care Hospitals'
    UNION ALL
    SELECT release, facility_id, state || ' acute care'
    FROM dim_hospital WHERE hospital_type = 'Acute Care Hospitals'
)
SELECT g.release, g.peer_group, 'ERR (median of hospital mean ERR)' AS kpi,
       median(s.err_mean) AS value, count(s.err_mean) AS hospitals
FROM groups g JOIN mart_scorecard s USING (release, facility_id) GROUP BY ALL
UNION ALL
SELECT g.release, g.peer_group, 'SIR ' || h.hai_id,
       sum(h.observed) / NULLIF(sum(h.predicted), 0), count(h.sir)
FROM groups g JOIN mart_hai h USING (release, facility_id)
WHERE h.sir IS NOT NULL GROUP BY ALL
UNION ALL
SELECT g.release, g.peer_group, 'Top box ' || t.measure_id,
       sum(t.top_box_pct * t.completed_surveys) / NULLIF(sum(t.completed_surveys), 0), count(t.top_box_pct)
FROM groups g JOIN mart_hcahps_topbox t USING (release, facility_id)
WHERE t.top_box_pct IS NOT NULL AND t.completed_surveys IS NOT NULL GROUP BY ALL
UNION ALL
SELECT g.release, g.peer_group, 'ED median minutes (OP_18b)',
       median(s.ed_median_minutes), count(s.ed_median_minutes)
FROM groups g JOIN mart_scorecard s USING (release, facility_id) GROUP BY ALL
UNION ALL
SELECT g.release, g.peer_group, 'Overall star rating (mean)',
       avg(s.overall_star_rating), count(s.overall_star_rating)
FROM groups g JOIN mart_scorecard s USING (release, facility_id) GROUP BY ALL;

-- Within-release national percentile for focus-state hospitals (acute care only).
CREATE OR REPLACE TABLE mart_percentile AS
SELECT release, facility_id, facility_name, state,
       CASE WHEN err_mean IS NOT NULL THEN round(100 * (1 - percent_rank() OVER (PARTITION BY release, err_mean IS NULL ORDER BY err_mean)), 1) END          AS err_pctile,
       CASE WHEN ed_median_minutes IS NOT NULL THEN round(100 * (1 - percent_rank() OVER (PARTITION BY release, ed_median_minutes IS NULL ORDER BY ed_median_minutes)), 1) END AS ed_pctile,
       CASE WHEN hcahps_rating_9_10 IS NOT NULL THEN round(100 * percent_rank() OVER (PARTITION BY release, hcahps_rating_9_10 IS NULL ORDER BY hcahps_rating_9_10), 1) END      AS hcahps_rating_pctile
FROM mart_scorecard
WHERE hospital_type = 'Acute Care Hospitals';
