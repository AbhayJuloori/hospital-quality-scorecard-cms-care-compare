"""Download the three Care Compare releases used by the scorecard.

Writes data/raw/<release>/<file>.csv plus data/raw/manifest.json with sizes,
row counts and sha256 so a rerun can confirm it is reading the same files.
"""
from __future__ import annotations

import hashlib
import io
import json
import urllib.request
import zipfile

from . import config


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "hqs-scorecard/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def _live_url(dataset_id: str) -> str:
    meta = json.loads(_get(f"{config.CMS}/api/1/metastore/schemas/dataset/items/{dataset_id}"))
    return meta["distribution"][0]["downloadURL"]


def _wanted(name: str) -> bool:
    from fnmatch import fnmatch

    return any(fnmatch(name, pat) for pat in config.SOURCE_GLOBS.values())


def download(force: bool = False) -> None:
    config.RAW.mkdir(parents=True, exist_ok=True)
    for release, spec in config.RELEASES.items():
        out = config.RAW / release
        if out.exists() and any(out.glob("*.csv")) and not force:
            print(f"{release}: present, skip")
            continue
        out.mkdir(parents=True, exist_ok=True)
        if spec.get("live"):
            for ds in config.LIVE_DATASETS.values():
                url = _live_url(ds)
                (out / url.rsplit("/", 1)[-1]).write_bytes(_get(url))
        else:
            with zipfile.ZipFile(io.BytesIO(_get(spec["archive"]))) as z:
                for name in z.namelist():
                    if _wanted(name):
                        (out / name).write_bytes(z.read(name))
        print(f"{release}: {sorted(p.name for p in out.glob('*.csv'))}")
    fn = config.RAW / "Footnote_Crosswalk.csv"
    if not fn.exists() or force:
        fn.write_bytes(_get(_live_url(config.FOOTNOTE_DATASET)))
    write_manifest()


def write_manifest() -> dict:
    files = {}
    for p in sorted(config.RAW.rglob("*.csv")):
        data = p.read_bytes()
        files[str(p.relative_to(config.RAW))] = {
            "bytes": len(data),
            "lines": data.count(b"\n"),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    (config.RAW / "manifest.json").write_text(json.dumps(files, indent=1))
    return files


if __name__ == "__main__":
    download()
