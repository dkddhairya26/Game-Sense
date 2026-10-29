"""Explainable, experimental GameSense scores; never official league rankings.

Fixed reference scales make the calculation reproducible without selecting an
arbitrary comparison population. They are design choices, not claims that a
40-point NBA game or a 35-disposal AFL game is a universal maximum. Saturation
at 100 prevents one extraordinary statistic dominating the other components.
Missing inputs invalidate a score; weights are never silently redistributed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


PLAYER_COMPONENTS = {
    "Soccer": [("goals", .45, 1.), ("assists", .30, .7),
               ("shots", .15, 5.), ("tackles", .10, 5.)],
    "NBA": [("points", .50, 40.), ("rebounds", .25, 15.),
            ("assists", .25, 12.)],
    "AFL": [("disposals", .45, 35.), ("marks", .20, 10.),
            ("tackles", .20, 10.), ("goals", .15, 5.)],
}
LIMITATIONS = {
    "Soccer": "Heuristic only: player score favours attacking volume, not goalkeeper or defensive quality; club margin ignores opponent strength and historical scoring conditions.",
    "NBA": "Heuristic box-score production only; no defence, pace, role, minutes or era adjustment. Historical missing rebounds/assists prevent a score.",
    "AFL": "Heuristic production or club result score; no role, opponent, playing-time or era adjustment. Player totals do not imply club results.",
    "F1": "Fixed 20-position reference, not field-size or era adjusted. Car quality, reliability and penalties affect results. Unrecorded/DNF finish positions are not invented; points systems differ across eras.",
}


def _numbers(frame, key):
    return pd.to_numeric(frame.get(key, pd.Series(np.nan, index=frame.index)), errors="coerce").replace([np.inf, -np.inf], np.nan)


def _grain(frame):
    kinds = frame.get("record_kind", pd.Series("", index=frame.index)).fillna("").astype(str)
    kinds = kinds + " " + frame.get("record_type", pd.Series("", index=frame.index)).fillna("").astype(str)
    season = kinds.str.contains("season|career", case=False, regex=True)
    average = season & kinds.str.contains(r"per.?game|average", case=False, regex=True)
    # A dated event is one observed appearance. Aggregate rows need actual games.
    games = _numbers(frame, "games")
    games = games.where(games.notna(), _numbers(frame, "games_played"))
    denominator = games.where(season, 1.).where(lambda x: x.gt(0))
    return season, average, denominator


def _per_game(frame, key):
    season, average, games = _grain(frame)
    values = _numbers(frame, key)
    derived = values.where(~(season & ~average), values / games)
    # Explicit provider per-game metrics are a legitimate alternative; no
    # denominator is inferred from the number of season rows in the archive.
    return derived.where(derived.notna(),_numbers(frame, key + "_pg"))


def rating_explanation(sport: str, entity_type: str = "athlete") -> str:
    """Return the full formula and missing-data rules for an in-app explanation."""
    if sport not in LIMITATIONS:
        raise ValueError("Unknown sport: " + str(sport))
    intro = "Experimental GameSense metric (0–100), not an official league statistic. clip(x)=min(1,max(0,x)). "
    if entity_type == "team" and sport in {"Soccer", "AFL"}:
        scale = 4 if sport == "Soccer" else 60
        formula = (f"Score = 100 × [0.70 × result + 0.30 × clip(0.5 + margin/{2*scale})]. "
                   "Result is 1 for a win, 0.5 for a draw, 0 for a loss. Margin is recorded score for minus score against. "
                   "Each input must be an actual match result: a season's total scores cannot establish its wins or losses and receive no club rating. "
                   f"A ±{scale} {'goal' if sport=='Soccer' else 'point'} margin saturates the margin component. "
                   "The 70% result weight prioritises winning; 30% rewards the recorded scoring margin. ")
    elif sport == "F1":
        formula = ("Score = 100 × [0.80 × clip((21 − finish)/20) + 0.20 × clip((grid − finish + 10)/20)]. "
                   "80% rewards finishing position and 20% rewards positions gained relative to the recorded grid. "
                   "Constructor scores average the actual recorded driver starts, not an invented team finish. ")
    else:
        terms = [f"{weight:.2f} × clip({key}/game ÷ {reference:g})" for key,weight,reference in PLAYER_COMPONENTS[sport]]
        formula = "Score = 100 × [" + " + ".join(terms) + "]. "
        formula += "Weights emphasise scoring/production while retaining supporting contributions. Reference scales are fixed design benchmarks, not official maximums. "
    return (intro + formula + "All required components must be recorded; missing is not zero. Season totals are divided by observed games, source per-game rows are used directly. "
            "Selected-period scores weight eligible aggregate rows by observed games. Recent form takes the last five recorded games or season rows first, then averages their eligible scores; missing inputs remain unknown and coverage is shown. "
            + LIMITATIONS[sport])


def rating_frame(frame: pd.DataFrame, sport: str) -> pd.DataFrame:
    """Return a copy with per-record scores and explicit eligibility status.

    A club and an athlete never share a formula. Historical player-match rows
    lacking dates remain eligible for a season score, but not dated recent form.
    """
    if sport not in LIMITATIONS:
        raise ValueError("Unknown sport: " + str(sport))
    out = frame.copy().reset_index(drop=True)
    season, _, games = _grain(out)
    out["experimental_rating"] = np.nan
    out["rating_weight"] = games
    out["rating_grain"] = np.where(season, "season", "game")
    marker = out.get("date_precision", pd.Series("day", index=out.index)).eq("season")
    out.loc[marker, "rating_grain"] = "season"
    entities = out.get("entity_type", pd.Series("athlete", index=out.index)).fillna("athlete")
    clubs = entities.eq("team") & (sport in {"Soccer", "AFL"})
    kinds = out.get("record_kind",pd.Series("event",index=out.index)).fillna("").astype(str)
    club_match_grain = kinds.isin(["event","team_match","match","matchday"]) & ~season
    if clubs.any():
        key = "goals" if sport == "Soccer" else "points"
        scored, against = _numbers(out,key), _numbers(out,key + "_against")
        # Season totals cannot establish a match result: 100 goals for and 80
        # against over 38 games does not mean one 100–80 win. Require the
        # recorded score of one real match before applying result/margin terms.
        valid = clubs & club_match_grain & scored.ge(0) & against.ge(0)
        result = pd.Series(np.where(scored > against, 1., np.where(scored == against,.5,0.)),index=out.index)
        margin = (.5 + (scored-against)/(8 if sport=="Soccer" else 120)).clip(0,1)
        out.loc[valid,"experimental_rating"] = (100*(.7*result+.3*margin))[valid]
    if sport == "F1":
        finish, grid = _numbers(out,"finish_position"), _numbers(out,"grid_position")
        # Grid 0 denotes a pit-lane/unspecified start in some sources, not
        # pole position or an ordered grid slot suitable for this formula.
        valid = finish.ge(1) & grid.ge(1)
        value = 100*(.8*((21-finish)/20).clip(0,1) + .2*((grid-finish+10)/20).clip(0,1))
        out.loc[valid,"experimental_rating"] = value[valid]
    else:
        value = pd.Series(0.,index=out.index)
        valid = ~clubs & entities.isin(["athlete", "player", "driver"])
        for key, weight, reference in PLAYER_COMPONENTS[sport]:
            metric = _per_game(out,key)
            valid &= metric.ge(0)
            value += weight*(metric/reference).clip(0,1)
        out.loc[valid,"experimental_rating"] = (100*value)[valid]
    out["rating_status"] = np.where(out["experimental_rating"].notna(), "eligible", "required statistics unavailable")
    out.loc[clubs & ~club_match_grain,"rating_status"] = "match-level club scores required"
    return out


def rating_history(frame: pd.DataFrame, sport: str) -> pd.DataFrame:
    """Provide a dated/season timeline with a five-observation rolling mean.

    Undated AFL match records are grouped by season. Labelled season markers
    never become claimed match dates. NaNs remain gaps instead of joining an
    incomplete observation to a zero score.
    """
    rated = rating_frame(frame,sport)
    columns = ["date","season","competitor_id","experimental_rating","recent_rating","rating_grain","eligible_records"]
    if rated.empty:
        return pd.DataFrame(columns=columns)
    rated["date"] = pd.to_datetime(rated.get("date"),errors="coerce",utc=True,format="mixed")
    rated["competitor_id"] = rated.get("competitor_id",rated.get("competitor", "selection"))
    rated["season"] = rated.get("season", "unknown")
    rows = []
    for identity, group in rated.groupby("competitor_id",dropna=False,sort=False):
        events = group.loc[group["rating_grain"].eq("game")].sort_values("date",kind="stable")
        for _, row in events.iterrows():
            if pd.notna(row["date"]):
                rows.append({"date":row["date"],"season":row["season"],"competitor_id":identity,
                             "experimental_rating":row["experimental_rating"],"rating_grain":"game",
                             "eligible_records":int(pd.notna(row["experimental_rating"]))})
        for season, batch in group.loc[group["rating_grain"].eq("season")].groupby("season",sort=True):
            valid = batch["experimental_rating"].notna() & batch["rating_weight"].gt(0)
            score = float(np.average(batch.loc[valid,"experimental_rating"],weights=batch.loc[valid,"rating_weight"])) if valid.any() else np.nan
            rows.append({"date":batch["date"].max(),"season":season,"competitor_id":identity,
                         "experimental_rating":score,"rating_grain":"season","eligible_records":int(valid.sum())})
    result = pd.DataFrame(rows)
    if result.empty:
        return pd.DataFrame(columns=columns)
    result = result.sort_values(["competitor_id","date","season"],kind="stable").reset_index(drop=True)
    # Roll within identity AND grain; a season is not one game in a form streak.
    result["recent_rating"] = result.groupby(["competitor_id","rating_grain"],dropna=False)["experimental_rating"].transform(lambda s:s.rolling(5,min_periods=1).mean())
    return result[columns]


def rating_summary(frame: pd.DataFrame, sport: str) -> dict:
    """Return an explainable selected-period score and coverage denominator."""
    rated = rating_frame(frame,sport)
    valid = rated["experimental_rating"].notna() & rated["rating_weight"].gt(0)
    score = float(np.average(rated.loc[valid,"experimental_rating"],weights=rated.loc[valid,"rating_weight"])) if valid.any() else None
    entity = str(frame["entity_type"].iloc[0]) if len(frame) and "entity_type" in frame else "athlete"
    history = rating_history(frame,sport)
    # Select the actual recent window BEFORE excluding unavailable scores.
    # Otherwise a missing latest game would silently pull in an older game.
    recent_window = history["experimental_rating"].tail(5) if len(history) else pd.Series(dtype=float)
    recent = recent_window.dropna()
    grains = history["rating_grain"].unique().tolist() if len(history) else []
    recent_label = ("last five recorded seasons" if grains == ["season"] else
                    "last five recorded driver starts" if grains == ["game"] and sport=="F1" else
                    "last five recorded games" if grains == ["game"] else
                    "mixed grain: recent form unavailable")
    components = []
    if entity == "team" and sport in {"Soccer","AFL"}:
        components = [{"metric":"match result","weight":.70},{"metric":"scoring margin","weight":.30}]
    elif sport == "F1":
        components = [{"metric":"finishing position","weight":.80},{"metric":"positions gained","weight":.20}]
    else:
        components = [{"metric":k,"weight":w,"reference_per_game":r} for k,w,r in PLAYER_COMPONENTS[sport]]
    if entity == "team" and sport in {"Soccer","AFL"}:
        key = "goals" if sport=="Soccer" else "points"
        scored,against = _numbers(rated,key),_numbers(rated,key+"_against")
        normalised = [pd.Series(np.where(scored>against,1.,np.where(scored==against,.5,0.)),index=rated.index),
                      (.5+(scored-against)/(8 if sport=="Soccer" else 120)).clip(0,1)]
    elif sport=="F1":
        finish,grid = _numbers(rated,"finish_position"),_numbers(rated,"grid_position")
        normalised = [((21-finish)/20).clip(0,1),((grid-finish+10)/20).clip(0,1)]
    else:
        normalised = [(_per_game(rated,k)/r).clip(0,1) for k,_,r in PLAYER_COMPONENTS[sport]]
    # Contributions sum to the reported score. This lets the UI show why a
    # competitor obtained it, including the effects of component saturation.
    for component, values in zip(components,normalised):
        component["score_contribution"] = (float(100*component["weight"]*np.average(values[valid],weights=rated.loc[valid,"rating_weight"]))
                                           if valid.any() else None)
    return {"score":score,"recent_score":float(recent.mean()) if len(recent) and len(grains)==1 else None,
            "recent_label":recent_label,"recent_observations":len(recent),
            "recent_window_observations":len(recent_window),
            "recent_unavailable_observations":len(recent_window)-len(recent),
            "eligible_records":int(valid.sum()),"total_records":len(rated),
            "components":components,"explanation":rating_explanation(sport,entity),
            "limitation":LIMITATIONS[sport],"experimental":True}
