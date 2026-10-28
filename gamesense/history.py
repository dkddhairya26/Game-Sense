"""Historical archive planning: real provider coverage, resume and safe merges.

Do not mistake fictional demonstration seasons for provider-cached seasons.
Persist each successfully fetched season so partial downloads survive failure.
"""
from __future__ import annotations

from datetime import date
import pandas as pd

from .analytics import SPORTS, clean_data

EARLIEST = {"Soccer": 1963, "NBA": 1946, "AFL": 2000, "F1": 1950}
FAMILIES = {"Soccer": "OpenLigaDB", "NBA": "NBA Stats",
            "AFL": "Squiggle API", "F1": "Jolpica F1"}
GRAIN = {
    "Soccer": "Bundesliga TEAM matches, not player careers",
    "NBA": "NBA player-season averages: one row per player/team/season",
    "AFL": "AFL TEAM match scores, not individual player disposals",
    "F1": "F1 driver race results; missing historical telemetry",
}


def year_from_season(value) -> int | None:
    """Read first year of 2024, 2024-25 or 2024-2025; reject other strings."""
    text = str(value)
    if len(text) >= 4 and text[:4].isdigit():
        y = int(text[:4])
        if 1800 <= y <= 2200:
            return y
    return None


def cache_years(df: pd.DataFrame | None, sport: str) -> set[int]:
    """Count only provider-origin years, never fictional or user-entered data."""
    if sport not in SPORTS:
        raise ValueError("Unknown sport")
    if df is None or df.empty or "season" not in df or "data_source" not in df:
        return set()
    provider = FAMILIES[sport]
    mask = df["data_source"].fillna("").astype(str).str.startswith(provider)
    result = set()
    for season in df.loc[mask, "season"]:
        year = year_from_season(season)
        if year is not None:
            result.add(year)
    return result


def plan_years(sport: str, start: int | None = None, end: int | None = None,
               cached: set[int] | None = None, refresh_current: bool = True) -> list[int]:
    """Plan any range including full recorded history; skips cached completed years."""
    if sport not in SPORTS:
        raise ValueError("Unknown sport")
    first = EARLIEST[sport]
    last = date.today().year
    start = first if start is None else int(start)
    end = last if end is None else int(end)
    if start < first or end > last or end < start:
        raise ValueError(f"{sport} years must be between {first} and {last}, with start <= end.")
    existing = cached or set()
    return [y for y in range(start, end + 1)
            if y not in existing or (refresh_current and y == last)]


def merge_season(existing: pd.DataFrame | None, downloaded: pd.DataFrame,
                 sport: str, source: str) -> pd.DataFrame:
    """Add one real provider season while retaining all unrelated import records.

    Replaces only old rows for the *same provider and season* so restarting
    never duplicates the same year's players or races.
    """
    if downloaded is None or downloaded.empty:
        raise ValueError("No downloaded records")
    if sport not in SPORTS:
        raise ValueError("Unknown sport")
    clean_new, _ = clean_data(downloaded, sport)
    if clean_new.empty:
        raise ValueError("No valid downloaded records")
    family = FAMILIES[sport]
    clean_new["data_source"] = source
    if existing is None or existing.empty:
        return clean_new
    old = existing.copy()
    if "data_source" not in old:
        old["data_source"] = "User imported / previous local dataset"
    incoming_years = set(clean_new["season"].astype(str).map(year_from_season).dropna())
    old_years = old["season"].astype(str).map(year_from_season)
    same_provider = old["data_source"].fillna("").astype(str).str.startswith(family)
    old = old.loc[~(same_provider & old_years.isin(incoming_years))]
    merged, _ = clean_data(pd.concat([old, clean_new], ignore_index=True), sport)
    return merged
