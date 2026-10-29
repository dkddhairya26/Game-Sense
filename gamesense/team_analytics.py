"""Observed club-match analytics for football and AFL, never inferred athlete stats.

One OpenFootball row is one club in one *finished match*. Do not add up
league standings snapshots, duplicate opponent rows, or unspecified player
goals. Group by competition AND season to avoid merging divisions or cups.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def _number_column(frame: pd.DataFrame, key: str) -> pd.Series:
    return pd.to_numeric(
        frame[key] if key in frame else pd.Series(float('nan'), index=frame.index),
        errors="coerce")


def club_matches(frame: pd.DataFrame, sport: str) -> pd.DataFrame:
    """Return only real team match records and the measured scoring fields."""
    if frame is None or frame.empty or "entity_type" not in frame:
        return pd.DataFrame()
    work = frame[frame["entity_type"].eq("team")].copy()
    if "record_kind" in work:
        accepted = work["record_kind"].isin(["team_match","event","match"])
        work = work.loc[accepted]
    if work.empty:
        return work
    # Missing real scores are not treated as 0-0 games.
    scored = "goals" if sport == "Soccer" else "points"
    conceded = "goals_against" if sport == "Soccer" else "points_against"
    if scored not in work or conceded not in work:
        return work.iloc[:0]
    work["_for"] = _number_column(work, scored)
    work["_against"] = _number_column(work, conceded)
    work = work.loc[np.isfinite(work["_for"]) & np.isfinite(work["_against"])
                    & work["_for"].ge(0) & work["_against"].ge(0)].copy()
    if "record_id" in work:
        # A missing ID does not mean two different matches are duplicates.
        duplicate = work["record_id"].notna() & work["record_id"].duplicated()
        work = work.loc[~duplicate]
    work["_win"] = (work["_for"] > work["_against"]).astype(int)
    work["_draw"] = (work["_for"] == work["_against"]).astype(int)
    work["_loss"] = (work["_for"] < work["_against"]).astype(int)
    return work.reset_index(drop=True)


def _result_run(results, target):
    """Return current and longest consecutive W/L runs in observed order."""
    longest = run = 0
    for result in results:
        run = run + 1 if result == target else 0
        longest = max(longest, run)
    return run, longest


def _sample_summary(work: pd.DataFrame) -> dict:
    n = len(work)
    return {"matches": n, "wins": int(work["_win"].sum()),
            "draws": int(work["_draw"].sum()), "losses": int(work["_loss"].sum()),
            "scored": float(work["_for"].sum()) if n else None,
            "conceded": float(work["_against"].sum()) if n else None,
            "win_rate": 100 * float(work["_win"].mean()) if n else None}


def club_summary(frame: pd.DataFrame, sport: str) -> dict:
    """Describe observed matches, preserving score and date completeness.

    Last-five/ten and streaks use dated matches only, oldest to newest. They
    describe the selected archive, not unobserved fixtures between those dates.
    AFL's scoring percentage is 100*points_for/points_against (not goal accuracy).
    A zero denominator leaves this undefined rather than displaying infinity.
    """
    work = club_matches(frame, sport)
    if work.empty:
        return {"matches":0,"wins":0,"draws":0,"losses":0,
                "scored":None,"conceded":None,"difference":None,
                "league_points":None,"win_rate":None,"leagues":0,"seasons":0,
                "avg_scored":None,"avg_conceded":None,"scoring_percentage":None,
                "goals":None,"behinds":None,"form":"","last5":None,"last10":None,
                "home":None,"away":None,"current_winning_streak":0,
                "current_losing_streak":0,"max_winning_streak":0,
                "max_losing_streak":0,"dated_matches":0}
    scored = float(work["_for"].sum())
    conceded = float(work["_against"].sum())
    wins = int(work["_win"].sum())
    draws = int(work["_draw"].sum())
    games = len(work)
    # Do not manufacture match chronology from a season sort marker.
    dates = pd.to_datetime(work.get("date", pd.Series(pd.NaT, index=work.index)),
                           errors="coerce", utc=True, format="mixed")
    precise = ~work.get("date_precision", pd.Series("day", index=work.index)).eq("season")
    dated = work.loc[dates.notna() & precise].copy()
    dated["_date"] = dates.loc[dated.index]
    dated = dated.sort_values("_date", kind="stable")
    results = ["W" if w else "D" if d else "L"
               for w, d in zip(dated["_win"], dated["_draw"])]
    current_w, max_w = _result_run(results, "W")
    current_l, max_l = _result_run(results, "L")
    venues = work.get("home_away", pd.Series("", index=work.index)).fillna("").str.lower()
    result = {
        "matches": games, "wins":wins, "draws":draws,
        "losses": int(work["_loss"].sum()),
        "scored":scored, "conceded":conceded,
        "difference":scored-conceded,
        # 3/1/0 is domestic football, not a universal historical convention;
        # supplied table_points is preferred when present. Older seasons
        # could have different governing rules.
        "league_points": (
            float(_number_column(work,"table_points").sum())
            if sport=="Soccer" and "table_points" in work
            and _number_column(work,"table_points").notna().all() else None
        ),
        "win_rate": 100*wins/games,
        "avg_scored": scored/games,
        "avg_conceded": conceded/games,
        "scoring_percentage": 100*scored/conceded if sport=="AFL" and conceded>0 else None,
        "form": "".join(results[-10:]),
        "last5": _sample_summary(dated.tail(5)) if len(dated) else None,
        "last10": _sample_summary(dated.tail(10)) if len(dated) else None,
        "home": _sample_summary(work.loc[venues.isin(["home", "h"])]) if venues.isin(["home", "h"]).any() else None,
        "away": _sample_summary(work.loc[venues.isin(["away", "a"])]) if venues.isin(["away", "a"]).any() else None,
        "current_winning_streak":current_w, "current_losing_streak":current_l,
        "max_winning_streak":max_w, "max_losing_streak":max_l,
        "dated_matches":len(dated),
        "leagues":work.get("competition",pd.Series(dtype=str)).dropna().nunique(),
        "seasons":work.get("season",pd.Series(dtype=str)).dropna().nunique(),
    }
    for key in ("goals", "behinds"):
        values = _number_column(work,key)
        # A partially measured statistic is not a complete selected-period total.
        result[key] = float(values.sum()) if values.notna().all() and len(values) else None
    return result


def club_season_table(frame: pd.DataFrame, sport: str) -> pd.DataFrame:
    work = club_matches(frame,sport)
    if work.empty or "season" not in work:
        return pd.DataFrame(columns=["season","competition","matches","W","D",
                                     "L","for","against","difference","league_points"])
    records = []
    keys = ["season"] + (["competition"] if "competition" in work else [])
    for identity, group in work.groupby(keys, dropna=False, sort=True):
        if not isinstance(identity,tuple):
            identity = (identity,)
        summary = club_summary(group,sport)
        records.append({
            "season":str(identity[0]),
            "competition":str(identity[1]) if len(identity)>1 else "",
            "matches":summary["matches"], "W":summary["wins"],
            "D":summary["draws"], "L":summary["losses"],
            "for":summary["scored"], "against":summary["conceded"],
            "difference":summary["difference"],
            "league_points":summary["league_points"],
            "win_rate_pct":round(summary["win_rate"],1),
        })
    return pd.DataFrame(records).sort_values(
        ["season","competition"],ascending=[False,True]).reset_index(drop=True)


def club_match_table(frame: pd.DataFrame, sport: str) -> pd.DataFrame:
    """Show human-readable observed fixtures with W/D/L and source provenance."""
    work = club_matches(frame,sport)
    columns = ["date","season","competition","home_away","opponent",
               "scored","conceded","result","round","source_url"]
    if work.empty:
        return pd.DataFrame(columns=columns)
    work = work.copy()
    work["scored"]=work["_for"]
    work["conceded"]=work["_against"]
    work["result"]=work["_win"].map({1:"W"})
    work.loc[work["_draw"].eq(1),"result"]="D"
    work.loc[work["_loss"].eq(1),"result"]="L"
    for key in columns:
        if key not in work:
            work[key] = None
    return work[columns].sort_values("date",ascending=False).reset_index(drop=True)
