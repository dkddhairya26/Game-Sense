"""Optional AFL player-game statistics from a third-party public research archive.

This is NEVER bundled into a public GameSense installer. The research project
uses an MIT licence and attributes records to AFL Tables, whose original data
rights must still be checked independently before any public redistribution.
GameSense only downloads it locally after the user explicitly opts in.

The archive can be substantial. We parse it incrementally, never execute code
from the ZIP, cap compressed/uncompressed sizes, and retain per-player IDs.
"""
from __future__ import annotations

import csv
from datetime import date
import io
import re
import threading
import zipfile

from .archive import data_directory
from .http import Cancelled
from .provider_base import Provider, ProviderMeta, _base, _client

ARCHIVE_URL = "https://codeload.github.com/akareen/AFL-Data-Analysis/zip/refs/heads/main"
REPO_URL = "https://github.com/akareen/AFL-Data-Analysis"
YEAR_FIRST = 1897
YEAR_LAST = 2025  # repository's stated scope, not a guarantee of every stat

# Preserve all nonempty numeric AFL player-game fields.
STATS = {
    "kicks": "kicks", "marks": "marks", "handballs": "handballs",
    "disposals": "disposals", "goals": "goals", "behinds": "behinds",
    "hit_outs": "hitouts", "tackles": "tackles",
    "rebound_50s": "rebound_50s", "inside_50s": "inside_50s",
    "clearances": "clearances", "clangers": "clangers",
    "free_kicks_for": "free_kicks_for", "free_kicks_against": "free_kicks_against",
    "brownlow_votes": "brownlow_votes",
    "contested_possessions": "contested_possessions",
    "uncontested_possessions": "uncontested_possessions",
    "contested_marks": "contested_marks",
    "marks_inside_50": "marks_inside_50",
    "one_percenters": "one_percenters", "bounces": "bounces",
    "goal_assist": "goal_assists",
    "percentage_of_game_played": "time_on_ground_pct",
}


def _value(number):
    if number is None or str(number).strip() == "":
        return None
    try:
        return float(number)
    except (TypeError, ValueError):
        return None


def normalize_player_rows(file_path: str, rows: list[dict]):
    """Translate one real source CSV, retaining player and season identifiers.

    The source has 'year' and 'round' but generally NO game calendar date.
    The 1 January date is explicitly marked as a sorting marker, not a match
    date. Disposals and other box-score fields are NOT inferred when absent.
    """
    filename = file_path.rsplit("/", 1)[-1]
    if not filename.endswith("_performance_details.csv"):
        return []
    identity = filename.removesuffix("_performance_details.csv")
    parts = identity.split("_")
    if len(parts) < 3:
        return []
    family, given = parts[0].title(), " ".join(x.title() for x in parts[1:-1])
    name = (given+" "+family).strip()
    meta = AFLPlayerArchiveProvider.meta
    result=[]
    for idx, raw in enumerate(rows):
        try:
            year=int(raw.get("year", ""))
        except (ValueError, TypeError):
            continue
        if year < YEAR_FIRST or year > date.today().year:
            continue
        team=str(raw.get("team") or "").strip()
        if not team:
            continue
        record = _base(
            meta, str(year),
            record_id=f"aflresearch:{identity}:{year}:{idx}",
            date=f"{year}-01-01", date_precision="season",
            date_is_sort_marker=True,
            record_kind="player_match_without_date",
            entity_type="athlete",
            competitor_id=f"aflresearch:{identity}",
            competitor=name, team=team,
            competition="VFL/AFL", round=str(raw.get("round") or ""),
            career_game_number=_value(raw.get("games_played")),
            opponent=str(raw.get("opponent") or ""),
            match_result=str(raw.get("result") or ""),
            jersey_number=str(raw.get("jersey_num") or ""),
            source_url=f"{REPO_URL}/blob/main/data/players/{filename}",
        )
        for original, field in STATS.items():
            if original in raw:
                value=_value(raw[original])
                if value is not None:
                    record[field]=value
        if raw.get("result") in ("W", "L", "D"):
            record["wins"]=int(raw["result"]=="W")
            record["losses"]=int(raw["result"]=="L")
            record["draws"]=int(raw["result"]=="D")
        result.append(record)
    return result


class AFLPlayerArchiveProvider(Provider):
    meta = ProviderMeta(
        "afl_player_research", "AFL player-game archive · third-party research",
        "AFL", "individual historical player match box scores",
        "Repository MIT; original AFL Tables data rights must be verified separately",
        REPO_URL,
        "Opt-in download of a third-party public research dataset of VFL/AFL "
        "player match statistics. Contains disposals, kicks, handballs, marks, "
        "goals, tackles, contested possessions and other recorded metrics. "
        "Earliest years have substantial missing fields. Records originate "
        "from AFL Tables, so check underlying data permissions before "
        "commercial/public redistribution. Data stay in your private cache.",
        "Research compilation by Adam Kareen · AFL-Data-Analysis "
        "(https://github.com/akareen/AFL-Data-Analysis), derived from AFL Tables. "
        "Software MIT; underlying statistics have separate source rights.",
    )

    def available_seasons(self, client=None):
        return [str(y) for y in range(YEAR_FIRST, min(YEAR_LAST,date.today().year)+1)]

    def download(self, archive, seasons, client=None, cancel=None, progress=None, force=False):
        client = _client(client, cancel)
        cancel = cancel or threading.Event()
        years=set()
        for value in seasons:
            year=int(value)
            if not YEAR_FIRST <= year <= min(YEAR_LAST,date.today().year):
                raise ValueError("Requested year outside published research archive scope.")
            years.add(year)
        if not years:
            return 0
        progress = progress or (lambda done,total,message: None)
        progress(0,len(years),"Downloading third-party AFL player research archive...")
        contents = client.get_bytes(ARCHIVE_URL, max_age=30*86400,
                                    max_bytes=155_000_000,
                                    headers={"Accept":"application/zip"})
        if len(contents) > 155_000_000:
            raise ValueError("Third-party archive exceeds the safe download size.")
        records=0
        year_counts={year:0 for year in years}
        with zipfile.ZipFile(io.BytesIO(contents)) as bundle:
            members=[info for info in bundle.infolist()
                     if info.filename.endswith("_performance_details.csv")
                     and "/data/players/" in info.filename]
            if len(members)>20000:
                raise ValueError("Unusually large AFL dataset: too many player files.")
            total_size=sum(info.file_size for info in members)
            if total_size>800_000_000:
                raise ValueError("AFL dataset exceeds safe decompressed-data limits.")
            pending=[]
            for number, info in enumerate(members,1):
                client.check()
                if cancel.is_set():
                    raise Cancelled("AFL download cancelled. Saved player records remain.")
                if info.file_size>6_000_000:
                    raise ValueError("Unexpectedly large individual player CSV.")
                with bundle.open(info) as handle:
                    text = io.TextIOWrapper(handle, encoding="utf-8-sig", errors="replace", newline="")
                    # The CSV iterator is streaming; only this athlete's games
                    # are held at once, not the whole national archive.
                    player = normalize_player_rows(info.filename, list(csv.DictReader(text)))
                for row in player:
                    year=int(row["season"])
                    if year in years:
                        pending.append(row)
                        year_counts[year]+=1
                if len(pending)>=800:
                    records+=archive.upsert(pending)
                    pending.clear()
                if number%250==0:
                    progress(min(number,len(members)),len(members),
                             f"Read {number:,} players · {sum(year_counts.values()):,} game rows")
            if pending:
                records+=archive.upsert(pending)
        for year, num in year_counts.items():
            if num:
                archive.mark(self.meta.id,"AFL",str(year),"partial",
                             "Third-party player research (AFL Tables sourced); "
                             f"{num} game rows. Original data rights not verified.")
            else:
                archive.mark(self.meta.id,"AFL",str(year),"unavailable",
                             "Research archive has no player games for this requested year.")
        progress(len(years),len(years),
                 f"Imported {records:,} AFL player-game records across {sum(v>0 for v in year_counts.values())} years.")
        if not records:
            raise ValueError("No player-game rows available for selected years.")
        return records
