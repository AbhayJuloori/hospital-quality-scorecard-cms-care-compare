# Power BI model

The Power BI layer sits on the same star schema the SQL builds. Nothing here is a screenshot of a finished
report: Power BI Desktop only runs on Windows and this project was built on a Mac, so the model is
delivered as load steps plus the DAX in [`measures.dax`](measures.dax). The numbers you would see in Power BI
are the ones in `mart_peer`, the Excel workbook and the web page, because every DAX measure follows the
pooling rule that `sql/02_marts.sql` implements.

## Load

1. `python -m hqs.run` writes CSVs to `data/export/`.
2. Get Data > Text/CSV for: `dim_hospital` (name it **Hospital**), `mart_hrrp` (**HRRP**), `mart_hai` (**HAI**),
   `mart_hcahps_topbox` (**TopBox**), `mart_scorecard` (**Scorecard**), `fact_measure` (**Fact**), `dim_measure`,
   `dim_footnote`. Keep `facility_id` as text (leading zeros matter: CCN `010001`).
3. Add `HospitalKey = [release] & "|" & [facility_id]` to every table, and a `Release = DISTINCT(Hospital[release])` table.
4. Relationships: `Release[release]` 1:* `Hospital[release]`; `Hospital[HospitalKey]` 1:* each fact table.
   Single direction.
5. Paste the measures from `measures.dax`.

## Pages

| Page | Visuals |
|---|---|
| State scorecard | Slicers: Release, State, Hospital type. Table: hospital, stars, ERR Mean, Conditions ERR > 1, SIR Pooled by HAI type, Top Box % for nurse communication / rating 9-10 / recommend, ED Median Minutes, Flagged Cell %. Background colour from the `... vs National` measures. Card row with state and national benchmarks. |
| Readmissions | ERR by condition (matrix: hospital x measure_id), ERR distribution histogram with the national median line. |
| Infections | SIR Pooled by HAI type for hospital / state / national; observed vs predicted bar. |
| Patient experience | Top box % by HCAHPS composite, hospital vs state vs national. |
| ED timeliness | OP-18b by hospital with national median-of-medians reference line. |
| Data quality | Flagged Cell % by source and release; suppressed cells by measure; footnote legend from `dim_footnote`. |

## Why the benchmarks are not simple averages

- **SIR** is pooled as sum(observed) / sum(predicted). An average of SIRs lets a hospital with 0.4 predicted
  infections count as much as one with 40.
- **ERR** peer value is the median of hospital means. CMS hides discharge counts when readmissions are under 11,
  so weighting by discharges would silently drop the small hospitals.
- **HCAHPS** top box is weighted by completed surveys.
- **OP-18b** is already a median of visits; medians cannot be averaged, so the peer value is the median of medians.
