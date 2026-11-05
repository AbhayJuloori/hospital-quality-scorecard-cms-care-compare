"""Load raw CMS CSVs into DuckDB and run the SQL model."""
from __future__ import annotations

import glob
from pathlib import Path

import duckdb

from . import config

SQL_DIR = config.ROOT / "sql"


def _csv(path: Path) -> str:
    # all_varchar keeps CMS text codes ("Not Available", "Too Few to Report") intact for flagging
    return f"read_csv('{path.as_posix()}', all_varchar=true, header=true, quote='\"', escape='\"')"


def stage(con: duckdb.DuckDBPyConnection, raw: Path = config.RAW) -> dict[str, dict[str, int]]:
    """Create stg_<source> tables as the union of every release. Returns raw row counts."""
    counts: dict[str, dict[str, int]] = {}
    for source, pattern in config.SOURCE_GLOBS.items():
        parts = []
        for release in config.RELEASES:
            files = sorted(glob.glob(str(raw / release / pattern)))
            if len(files) != 1:
                raise FileNotFoundError(f"{release}/{pattern}: expected 1 file, found {len(files)}")
            n = con.execute(f"SELECT count(*) FROM {_csv(Path(files[0]))}").fetchone()[0]
            counts.setdefault(source, {})[release] = n
            parts.append(f"SELECT '{release}' AS release, * FROM {_csv(Path(files[0]))}")
        con.execute(f"CREATE OR REPLACE TABLE stg_{source} AS " + " UNION ALL BY NAME ".join(parts))
    con.execute(f"CREATE OR REPLACE TABLE stg_footnote AS SELECT * FROM {_csv(raw / 'Footnote_Crosswalk.csv')}")
    con.execute("CREATE OR REPLACE TABLE kpi_topbox (measure_id VARCHAR, label VARCHAR)")
    con.executemany("INSERT INTO kpi_topbox VALUES (?, ?)", list(config.HCAHPS_TOP_BOX.items()))
    return counts


def model(con: duckdb.DuckDBPyConnection) -> None:
    for f in sorted(SQL_DIR.glob("*.sql")):
        con.execute(f.read_text())


def build(db_path: Path = config.DB_PATH, raw: Path = config.RAW) -> tuple[duckdb.DuckDBPyConnection, dict]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    con.execute("SET threads TO 4")
    counts = stage(con, raw)
    model(con)
    return con, counts


def export(con: duckdb.DuckDBPyConnection, out: Path = config.EXPORT) -> list[Path]:
    """CSV extracts for Power BI / Excel (star schema)."""
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for t in ["fact_measure", "dim_hospital", "dim_measure", "dim_footnote", "mart_hrrp", "mart_hai",
              "mart_hcahps_topbox", "mart_ed", "mart_scorecard", "mart_peer", "mart_percentile"]:
        p = out / f"{t}.csv"
        con.execute(f"COPY {t} TO '{p.as_posix()}' (HEADER)")
        paths.append(p)
    return paths
