# Hospital Quality Scorecard (CMS Care Compare data)

**Live page:** https://abhayjuloori.github.io/hospital-quality-scorecard-cms-care-compare/

A reporting pipeline that turns five public CMS Care Compare files into a hospital quality scorecard:
overall star rating, readmissions (HRRP excess readmission ratio), infections (HAI standardized infection
ratio), patient experience (HCAHPS top box) and emergency department timeliness (OP-18b median time).
It joins three annual releases (2024, 2025, 2026) in DuckDB SQL, flags every suppressed, footnoted,
unavailable or missing cell, ties each KPI back to the published CMS values, and compares Indiana and
New Jersey hospitals with state and national acute care peers in an Excel workbook, a Power BI model
definition and a static web page.

## Problem

Care Compare publishes each domain as a separate long CSV with its own layout: HRRP has one row per
hospital and condition, HAI has six rows per infection type (SIR, observed, predicted, two CI bounds, days),
HCAHPS has one row per answer category, and every file mixes numbers with text codes such as
`Not Available`, `Too Few to Report` and footnote lists like `5, 24`. A hospital quality analyst needs one
row per hospital, peer benchmarks that are pooled correctly, and a clear record of which cells CMS withheld.

## Data

| File (CMS Provider Data Catalog, hospitals theme) | Grain | Rows 2024 / 2025 / 2026 |
|---|---|---|
| Hospital General Information | hospital | 5,398 / 5,381 / 5,419 |
| Hospital Readmissions Reduction Program (FY 2024 / 2025 / 2026) | hospital x condition | 18,774 / 18,510 / 18,330 |
| HCAHPS Patient Survey - Hospital | hospital x answer | 445,563 / 442,215 / 325,720 |
| Healthcare Associated Infections - Hospital | hospital x HAI field | 172,476 / 171,180 / 172,440 |
| Timely and Effective Care - Hospital | hospital x measure | 105,455 / 117,933 / 138,084 |
| Footnote Crosswalk | footnote code | 32 |

2024 and 2025 come from the CMS hospitals archive (`hospitals_2024-07-31.zip`, `hospitals_2025-08-14.zip`),
2026 from the live catalog API (July 2026 refresh). `python -m hqs.ingest` downloads all of it;
`data/raw/manifest.json` records size, line count and sha256 of every file used for the published numbers.

Reporting periods differ by domain: HRRP uses a rolling 3-year discharge window (FY 2026 file: Jul 2021 to Jun 2024),
HAI, HCAHPS and ED timeliness use one year (2026 release: Oct 2024 to Sep 2025).

## Method

```
data/raw/<release>/*.csv
   -> stg_<source>        all text, one table per file type, union of releases (UNION ALL BY NAME)
   -> fact_measure        one row per release x source x hospital x measure: value_raw, value_num,
                          footnote, status, period, denominator
   -> dim_hospital, dim_measure (domain, direction, first/last release), dim_footnote
   -> mart_hrrp, mart_hai (pivoted), mart_hcahps_topbox, mart_ed
   -> mart_scorecard      one row per hospital per release
   -> mart_peer           state and national acute care benchmarks per KPI
   -> mart_percentile     national percentile per hospital
```

**Cell status.** Every value gets one of `reported`, `reported_footnoted`, `suppressed` (non-numeric with
`Too Few to Report` or footnote 1 / 4), `not_available`, `missing`, or `categorical` (e.g. ED volume "high").
Suppressed and unavailable cells stay blank in the scorecard with a count per hospital; they are never zero.

**Pooling rules** (the part most dashboards get wrong):

| KPI | Hospital value | Peer benchmark |
|---|---|---|
| Excess readmission ratio | published ERR per condition; hospital summary = mean of reported conditions | median of hospital summaries (CMS hides discharges when readmissions < 11, so weighting would drop small hospitals) |
| SIR | published SIR per infection type | sum(observed) / sum(predicted), the CDC NHSN method |
| HCAHPS top box | published percent | completed-survey weighted mean |
| OP-18b median ED minutes | published median | median of hospital medians |
| Star rating | published 1-5 | mean of rated hospitals |

## Results

`python -m hqs.run`: 2,162,878 CMS cells across 3 releases and 172 distinct measures, built in about 4 seconds on a laptop.
All 13 checks pass:

| Check | Rows checked | Result |
|---|---|---|
| Raw rows = staged rows = fact rows, per file and release | 2,162,878 | 0 breaks |
| One fact row per release x source x hospital x measure | 2,162,878 | 0 duplicates |
| Measure-file hospitals present in General Information | 16,285 | 87 HRRP hospitals not listed (0.53%, tolerated, reported) |
| Every cell classified; no numeric KPI left unparsed | 2,162,878 | 0 |
| Star rating integer 1-5 | 8,880 | 0 |
| One reporting period per release (HRRP, HAI) | 6 | 0 |
| Discharges hidden exactly when readmissions are "Too Few to Report" | 35,724 | 0 |
| ERR = predicted / expected rate | 35,724 | max diff 0.00007 |
| SIR = observed / predicted (predicted >= 1) | 33,918 | max diff 0.0005 |
| SIR inside its published 95% CI | 33,918 | 0 outside |
| CMS "better / worse than national" label agrees with CI vs 1.0 | 33,918 | 0 disagreements |
| HCAHPS always + usually + sometimes/never = 100% (+/- 2) | 170,304 | 0 |
| IN / NJ scorecard cells equal the raw CMS cells (independent SQL path) | 3,405 | 0 mismatches |

**Cell status, 2026 release:** 659,993 cells; 45,994 suppressed, 45,140 reported with a footnote,
199,289 not available, 0 blank. 290,423 cells carry at least one footnote code.

**Measure set changes found between releases:** 42 measures appear or disappear. The 2026 release, following the HCAHPS survey update,
dropped the staff responsiveness (H_COMP_3), care transition (H_COMP_7, H_CT_*) and bathroom/call-button items;
the Hospital Harm measures were renamed (HH_01 / HH_02 -> HH_HYPO / HH_HYPER) and HH_ORAE and the
Global Malnutrition Composite were added in 2026; ED_2 strata and HCP COVID-19 were dropped.
A trend chart built on measure IDs alone would silently break at those points.

**Indiana vs New Jersey, 2026 release (acute care hospitals):**

| KPI | Indiana | New Jersey | National |
|---|---|---|---|
| Hospitals (acute care) | 82 | 61 | 3,107 |
| Mean overall star rating | 3.36 (73 rated) | 3.17 (60) | 3.16 (2,663) |
| Median hospital ERR | 0.993 | 1.027 | 1.000 |
| Hospitals with mean ERR > 1 | 34 of 76 | 50 of 61 | |
| CLABSI pooled SIR | 0.513 | 0.421 | 0.583 |
| C. diff pooled SIR | 0.359 | 0.335 | 0.333 |
| HCAHPS rating 9-10 (survey weighted) | 70.3% | 67.4% | 69.3% |
| Median OP-18b ED minutes | 157 | 185 | 170 |

Over three releases New Jersey's mean star rating rose from 2.68 to 3.17 and its rating 9-10 share from 64.0%
to 67.4%, while its median ERR stayed above 1 (1.036 -> 1.027) and its median ED time stayed above the national
median (195 -> 185 vs 174 -> 170). These are descriptive comparisons of published measures, not causal claims.

## Deliverables

- `deliverables/hospital_quality_scorecard.xlsx`: Read me, Data dictionary (definition, CMS file and field,
  hospital formula, peer rule, direction, DAX measure per KPI), Requirements, Test cases (each check mapped to a
  requirement, PASS/FAIL), Quality flags (status counts per file and release + footnote legend), Measure changes,
  IN and NJ scorecards with state and national benchmark rows and green/red formatting, Trend.
- `powerbi/measures.dax` + `powerbi/README.md`: star schema load steps, relationships and DAX measures
  (ERR mean and peer median, pooled SIR, survey-weighted top box, ED median of medians, flagged cell %,
  better/worse-than-national flags).
- `docs/`: static page with the scorecard, benchmarks, trends and quality flags (GitHub Pages).
- `data/export/*.csv`: star schema extracts (not committed; regenerate with the run).

## Limitations

- Power BI Desktop is Windows only and this was built on a Mac. The DAX measures are written against the
  exported tables and follow the same rules as the SQL, but they were not executed here; the numbers on the
  page and in Excel come from DuckDB.
- Peer groups are state and national acute care hospitals. CMS does not publish bed counts in these files,
  so there is no size- or teaching-status peer group.
- HRRP windows overlap by two of three years between releases, so year-over-year ERR changes are smoothed.
- The hospital summary ERR is an unweighted mean of up to six conditions; it is a reporting convenience,
  not a CMS measure, and is not the HRRP payment adjustment.
- HCAHPS top box values are CMS patient-mix adjusted; the survey-weighted peer mean is an approximation of the
  CMS state/national averages, which CMS publishes in separate files that this project does not use.
- OP-18b covers hospitals that submit outpatient ED data; critical access hospitals are often absent.

## How to run

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
PYTHONPATH=src .venv/bin/python -m hqs.ingest     # ~600 MB of CMS CSVs into data/raw
PYTHONPATH=src .venv/bin/python -m hqs.run        # model, checks, docs/data/report.json, Excel, CSV extracts
PYTHONPATH=src .venv/bin/python -m pytest -q      # synthetic fixture tests, no download needed
```

`hqs.run` exits non-zero if any check fails. Change `FOCUS_STATES` in `src/hqs/config.py` to build the
scorecard for other states.

## Layout

```
sql/01_core.sql        status macros, fact_measure, dimensions
sql/02_marts.sql       KPI marts, scorecard, peer benchmarks, percentiles
src/hqs/ingest.py      download + manifest
src/hqs/build.py       staging, model, CSV export
src/hqs/checks.py      data quality checks and CMS tie-outs
src/hqs/kpis.py        KPI dictionary, requirements, check-to-requirement map
src/hqs/excel.py       workbook
src/hqs/run.py         end-to-end run and report JSON
powerbi/               DAX measures and model notes
docs/                  GitHub Pages site
tests/                 pytest suite on a synthetic fixture
```
