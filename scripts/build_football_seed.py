"""Create an attributed CC0 starter archive with real European league results.

This runs BEFORE PyInstaller on each platform's CI runner. It is intentionally
not generated from fake players, not re-scraped, and does not include athlete
goals/assists, which the openfootball source does not provide.

Exit nonzero if the public starter is too sparse: never publish a Windows
installer that opens on a 35-row "all football" archive by accident.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
import gzip
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import time
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # Running python scripts/build_football_seed.py from CI
# Provider subclasses are registered from gamesense.providers at import time;
# initialize the registry before importing a subclass directly.
from gamesense import providers as _providers
from gamesense.openfootball_provider import DEFAULT_LEAGUES, REPO, fixture_records
DEST = ROOT / "data" / "seed_soccer_cc0.jsonl.gz"
FIRST = 2010
LAST = 2026  # 2026-27 results only when the match has actually finished


def fetch(year: int, code: str):
    season=f"{year}-{(year+1)%100:02d}"
    url=f"{REPO}/{season}/{code}.json"
    for attempt in range(3):
        try:
            req=Request(url,headers={
                "User-Agent":"GameSense-CC0-Seed-Builder/0.8 (sports data attribution)",
                "Accept":"application/json"})
            with urlopen(req,timeout=30) as stream:
                payload=json.load(stream)
            return fixture_records(payload,season,code,today=date.today())
        except HTTPError as exc:
            if exc.code==404:
                return []
            if exc.code not in (408,429,500,502,503,504) or attempt==2:
                raise
        except (URLError,TimeoutError):
            if attempt==2: raise
        time.sleep(1+attempt*2)
    return []


def build(path=DEST):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    leagues=Counter()
    seasons=Counter()
    total=0
    # Use a distinct file: preserve all previously packaged F1 and NBA seeds.
    with gzip.open(path,"wt",encoding="utf-8",compresslevel=7) as out:
        for year in range(FIRST,LAST+1):
            season=f"{year}-{(year+1)%100:02d}"
            for code in DEFAULT_LEAGUES:
                rows=fetch(year,code)
                for row in rows:
                    out.write(json.dumps(row,ensure_ascii=False,separators=(",",":"))+"\n")
                total+=len(rows)
                if rows:
                    leagues[code]+=1
                    seasons[season]+=len(rows)
                print(f"{season} {code}: {len(rows):,} team records",flush=True)
            time.sleep(.15)
    print(f"CC0 football seed: {total:,} team rows, "
          f"{len(seasons)} seasons, {len(leagues)} leagues; "
          f"{path.stat().st_size:,} compressed bytes",flush=True)
    if len(seasons)<5 or len(leagues)<5 or total<7500:
        path.unlink(missing_ok=True)
        raise RuntimeError("OpenFootball source coverage is insufficient for a real "
                           "historical multi-league starter; refusing to package.")
    manifest=path.parent/"SOCCER_SEED_COVERAGE.json"
    manifest.write_text(json.dumps({
        "source":"openfootball/football.json", "license":"CC0-1.0",
        "source_url":"https://github.com/openfootball/football.json",
        "grain":"club team match; no player stats, assists or rosters",
        "seasons":sorted(seasons), "leagues":dict(leagues),
        "team_records":total,
        "partial_seasons":True,
        "last_download_utc":__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat()
    },indent=2),encoding="utf-8")
    return total


if __name__=="__main__":
    build()
