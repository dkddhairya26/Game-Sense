"""Deterministic statistics and factual insights from the selected archive.

There is no generative model, prediction or invented causal explanation here.
Each sentence is tied to its observed period, source and record count. Public
claims such as a 'career total' are deliberately called selected-record totals:
an archive may omit a season, competition or metric.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .analytics import metric_summary
from .ratings import rating_summary
from .team_analytics import club_matches, club_summary


def _numbers(frame, key):
    return pd.to_numeric(frame.get(key,pd.Series(np.nan,index=frame.index)),errors="coerce").replace([np.inf,-np.inf],np.nan)


def _period(frame):
    if frame.empty:
        return "No records"
    marker = frame.get("date_precision",pd.Series("day",index=frame.index)).eq("season")
    if marker.any():
        seasons = sorted(frame.get("season",pd.Series(dtype=str)).dropna().astype(str).unique())
        return (seasons[0]+(" to "+seasons[-1] if len(seasons)>1 else "")+" (recorded seasons)") if seasons else "Undated records"
    dates = pd.to_datetime(frame.get("date",pd.Series(pd.NaT,index=frame.index)),errors="coerce",utc=True,format="mixed").dropna()
    return dates.min().strftime("%Y-%m-%d")+" to "+dates.max().strftime("%Y-%m-%d") if len(dates) else "Dates unavailable"


def _source(frame):
    for key in ("source_name","provider","source"):
        if key in frame:
            names = frame[key].dropna().astype(str)
            names = names.loc[names.ne("")].unique()
            if len(names):
                return "; ".join(sorted(names))
    return "User-supplied records (source not specified)"


def _total(frame,key):
    return metric_summary(frame,key)["total"]


def _games(frame):
    kinds = frame.get("record_kind",pd.Series("",index=frame.index)).fillna("").astype(str)
    kinds += " "+frame.get("record_type",pd.Series("",index=frame.index)).fillna("").astype(str)
    aggregate = kinds.str.contains("season|career",case=False,regex=True)
    games = _numbers(frame,"games")
    games = games.where(games.notna(),_numbers(frame,"games_played")).where(aggregate,1.)
    return float(games.sum()) if len(games) and games.notna().all() and games.gt(0).all() else None


def performance_summary(frame: pd.DataFrame, sport: str) -> dict:
    """Return comparable measured statistics plus coverage for one selection.

    F1 constructor inputs may contain two driver rows per race. Points/wins are
    sums across actual starts; finishing position averages actual classified
    starts, and races counts unique event IDs. This does not invent a team
    placing or treat an unclassified finish as zero.
    """
    base = {"records":len(frame),"period":_period(frame),"source":_source(frame),
            "scope":"selected recorded data", "sport":sport}
    if frame.empty:
        return base
    entities = set(frame.get("entity_type",pd.Series("athlete",index=frame.index)).dropna().astype(str))
    if entities == {"team"} and sport in {"Soccer","AFL"}:
        base.update(club_summary(frame,sport))
        if sport=="Soccer":
            base.update({"goals_scored":base["scored"],"goals_conceded":base["conceded"],
                         "goal_difference":base["difference"],"goals_per_match":base["avg_scored"]})
        else:
            base.update({"points_scored":base["scored"],"points_conceded":base["conceded"]})
    elif sport=="F1":
        finish, grid = _numbers(frame,"finish_position"), _numbers(frame,"grid_position")
        qualifying = _numbers(frame,"qualifying_position")
        paired = finish.notna() & qualifying.notna() & finish.ge(1) & qualifying.ge(1)
        valid_finish = finish.loc[finish.ge(1)]
        base.update({"starts":len(frame),
                     "races":int(frame["event_id"].nunique()) if "event_id" in frame else len(frame),
                     "wins":int(valid_finish.eq(1).sum()) if len(valid_finish) else None,
                     "podiums":int(valid_finish.between(1,3).sum()) if len(valid_finish) else None,
                     "classified_finishes":len(valid_finish),
                     "unrecorded_finishes":int(finish.isna().sum()),
                     "points":_total(frame,"points"),
                     "average_finish":float(valid_finish.mean()) if len(valid_finish) else None,
                     "average_grid":float(grid.loc[grid.ge(1)].mean()) if grid.ge(1).any() else None,
                     "average_qualifying":float(qualifying.loc[qualifying.ge(1)].mean()) if qualifying.ge(1).any() else None,
                     "qualifying_to_finish_gain":float((qualifying[paired]-finish[paired]).mean()) if paired.any() else None,
                     "paired_qualifying_races":int(paired.sum())})
        dates = pd.to_datetime(frame.get("date",pd.Series(pd.NaT,index=frame.index)),errors="coerce",utc=True,format="mixed")
        ordered = frame.loc[dates.notna()].copy()
        ordered["_date"] = dates.loc[ordered.index]
        ordered = ordered.sort_values("_date",ascending=False,kind="stable").head(5)
        base["recent_results"] = [
            {"date":row["_date"].strftime("%Y-%m-%d"),
             "finish_position":float(row["finish_position"]) if pd.notna(row.get("finish_position")) else None,
             "points":float(row["points"]) if pd.notna(row.get("points")) else None}
            for _,row in ordered.iterrows()]
    else:
        base["games"] = _games(frame)
        metrics = {"NBA":["points","rebounds","assists","steals","blocks","turnovers"],
                   "Soccer":["goals","assists","shots","passes","tackles"],
                   "AFL":["disposals","kicks","handballs","marks","tackles","goals","behinds"]}[sport]
        for key in metrics:
            stats = metric_summary(frame,key)
            base[key] = stats["total"]
            base[key+"_per_game"] = stats["per_game"]
            base[key+"_observed_records"] = stats["count"]
        if sport=="NBA":
            for key in ("field_goal_pct","three_point_pct","free_throw_pct"):
                base[key] = metric_summary(frame,key)["average"]
            # NBA convention for eFG% counts the extra point of a made 3PT.
            # TS% uses the conventional .44 free-throw multiplier and is named
            # an estimate: it is not an observed possession-level calculation.
            fgm, fga = _total(frame,"field_goals_made"), _total(frame,"field_goal_attempts")
            threes, fta = _total(frame,"three_point_makes"), _total(frame,"free_throw_attempts")
            complete = lambda key: key in frame and _numbers(frame,key).notna().all()
            base["effective_field_goal_pct"] = (fgm+.5*threes)/fga if fga and fga>0 and fgm is not None and threes is not None and all(complete(k) for k in ("field_goals_made","field_goal_attempts","three_point_makes")) else None
            points = base["points"]
            denominator = 2*(fga+.44*fta) if fga is not None and fta is not None else None
            base["estimated_true_shooting_pct"] = points/denominator if denominator and denominator>0 and points is not None and all(complete(k) for k in ("points","field_goal_attempts","free_throw_attempts")) else None
    base["rating"] = rating_summary(frame,sport)
    return base


def statistical_insights(frame: pd.DataFrame, sport: str) -> list[dict]:
    """Produce bounded, source-qualified statements without speculative causes."""
    if frame is None or frame.empty:
        return []
    stats = performance_summary(frame,sport)
    names = frame.get("competitor",pd.Series(dtype=str)).dropna().astype(str).unique()
    name = str(names[0]) if len(names)==1 else "This selection"
    period, source = stats["period"],stats["source"]
    output=[]
    def add(text, records=None):
        output.append({"text":text,"period":period,"source":source,
                       "records":len(frame) if records is None else int(records)})
    if "matches" in stats:
        last = stats.get("last5")
        if last:
            add(f"{name} won {last['wins']} of the last {last['matches']} dated recorded matches ({last['draws']} draws, {last['losses']} losses).",last["matches"])
        if stats["matches"]:
            unit = "goals" if sport=="Soccer" else "points"
            add(f"{name} averaged {stats['avg_scored']:.2f} {unit} scored and {stats['avg_conceded']:.2f} conceded per recorded match.",stats["matches"])
        if stats.get("scoring_percentage") is not None:
            add(f"Recorded AFL scoring percentage is {stats['scoring_percentage']:.2f}% (points for ÷ points against × 100).",stats["matches"])
        if stats.get("current_winning_streak",0)>=2:
            add(f"The selected dated record ends with {stats['current_winning_streak']} consecutive recorded wins.")
    elif sport=="F1":
        if stats["average_finish"] is not None:
            add(f"{name} averaged finishing position {stats['average_finish']:.2f} across {stats['classified_finishes']} recorded classified starts; {stats['unrecorded_finishes']} finish positions are unavailable.")
        if stats["paired_qualifying_races"]:
            gain=stats["qualifying_to_finish_gain"]
            add(f"Across {stats['paired_qualifying_races']} starts with both qualifying and race positions, mean qualifying-to-finish gain was {gain:+.2f} places.",stats["paired_qualifying_races"])
        if "season" in frame:
            means=[]
            for season, group in frame.groupby("season",sort=True):
                values=_numbers(group,"finish_position").dropna()
                values=values.loc[values.ge(1)]
                if len(values): means.append((str(season),float(values.mean()),len(values)))
            if len(means)>=2:
                first,last=means[0],means[-1]
                direction="improved" if last[1]<first[1] else "worsened" if last[1]>first[1] else "was unchanged"
                add(f"Mean recorded finish {direction}: {first[0]} {first[1]:.2f} ({first[2]} starts) versus {last[0]} {last[1]:.2f} ({last[2]} starts). Different race samples and cars limit interpretation.")
    else:
        metric = {"NBA":"points","Soccer":"goals","AFL":"disposals"}[sport]
        value=stats.get(metric+"_per_game")
        if value is not None:
            add(f"{name} recorded {value:.2f} {metric} per observed game in the selected records.",stats.get(metric+"_observed_records"))
        if sport=="NBA" and stats.get("field_goal_pct") is not None:
            add(f"Combined recorded field-goal percentage is {100*stats['field_goal_pct']:.2f}%; makes and attempts determine the combined rate.")
    rating=stats.get("rating",{})
    if rating.get("score") is not None:
        add(f"Experimental GameSense score: {rating['score']:.1f}/100 from {rating['eligible_records']} of {rating['total_records']} eligible records. This is a heuristic, not an official ranking.")
    return output[:5]
