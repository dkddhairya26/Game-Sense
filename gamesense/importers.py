"""Normalise common sports dataset headers without inventing real match records.

Every user-supplied column is retained; only recognised field names are mapped.
Season-only rows use a clearly flagged chronological marker, never a claimed match date.
"""
from __future__ import annotations
import re
import pandas as pd

# Aliases are applied after standardising whitespace and punctuation.
ALIASES = {
    "player": "competitor", "player_name": "competitor",
    "playername": "competitor", "athlete": "competitor",
    "driver": "competitor", "driver_name": "competitor",
    "name": "competitor", "footballer": "competitor",
    "club": "team", "club_name": "team", "team_name": "team",
    "squad": "team", "constructor": "team", "constructor_name": "team",
    "year": "season", "season_year": "season", "seasonyear": "season",
    "match_date": "date", "game_date": "date", "race_date": "date",
    "matchdate": "date", "gamedate": "date",
    "pts": "points", "reb": "rebounds", "ast": "assists", "stl": "steals",
    "blk": "blocks", "tov": "turnovers", "fgm": "field_goals_made",
    "fga": "field_goals_attempted", "fg_pct": "field_goal_percentage",
    "fg3m": "three_point_made", "fg3a": "three_point_attempted",
    "fg3_pct": "three_point_percentage", "ftm": "free_throws_made",
    "fta": "free_throws_attempted", "ft_pct": "free_throw_percentage",
    "gp": "games_played", "min": "minutes", "mp": "minutes",
    "kick": "kicks", "k": "kicks", "hb": "handballs", "d": "disposals",
    "m": "marks", "t": "tackles", "g": "goals",
    "cl": "clearances", "clangers_total": "clangers",
    "finish": "finish_position", "position_finish": "finish_position",
    "grid": "grid_position", "start_position": "grid_position",
}
# Single-letter stat abbreviations are ambiguous across sports and are only
# accepted for sport-specific AFL exports when we can identify the context.
AFL_ONLY = {"k": "kicks", "hb": "handballs", "d": "disposals",
            "m": "marks", "t": "tackles", "g": "goals", "cl": "clearances"}


def prepare_import(df: pd.DataFrame, sport: str) -> tuple[pd.DataFrame, list[str]]:
    """Produce a GameSense-compatible dataframe plus plain-English notes."""
    out = df.copy()
    out.columns = [
        re.sub(r"[^a-z0-9]+", "_", str(col).strip().lower()).strip("_")
        for col in out.columns
    ]
    notes = []
    mapping = {}
    for col in out.columns:
        if col in ("date", "season", "team", "competitor"):
            continue
        if sport != "AFL" and col in AFL_ONLY and len(col) <= 2:
            continue
        target = ALIASES.get(col)
        if target and target not in out.columns:
            mapping[col] = target
    if mapping:
        out.rename(columns=mapping, inplace=True)
        notes.append("Mapped headers: " + ", ".join(f"{old} → {new}" for old,new in mapping.items()))
    if "competitor" not in out:
        raise ValueError("No competitor/player/driver name column was found. Rename it to 'competitor'.")
    if "season" not in out:
        raise ValueError("No season/year column was found. Rename it to 'season'.")
    if "team" not in out:
        out["team"] = "Team not provided"
        notes.append("Team/club column absent; shown as 'Team not provided'.")
    if "date" not in out:
        years = out["season"].astype(str).str.extract(r"((?:19|20)\d{2})")[0]
        out["date"] = pd.to_datetime(years + "-01-01", errors="coerce")
        out["date_is_marker"] = True
        if "record_type" not in out:
            out["record_type"] = "player/team season aggregate (NO MATCH DATE)"
        notes.append("No actual match date was supplied. Used Jan 1 of the season as a "
                     "SORTING MARKER ONLY, not a claimed game date.")
    if "record_type" not in out:
        out["record_type"] = "user-imported record"
    return out, notes
