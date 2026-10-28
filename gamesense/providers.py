"""On-demand historical data connectors with honest coverage labels.

Source data is not bundled or redistributed. Users initiate a specific
season download; network failures are reported rather than hidden.
"""
from __future__ import annotations

import json
import re
from datetime import date
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import pandas as pd

COVERAGE = {
    "Soccer": ("OpenLigaDB · Bundesliga match/team results", "Team-level only. Volunteer-maintained; no complete player statistics."),
    "NBA": ("NBA Stats · season player averages", "NBA player-season aggregates where the NBA endpoint responds; older/advanced fields vary."),
    "AFL": ("Squiggle API · team match results since approximately 2000", "Team match scores only. For disposals, tackles and player history, import a permitted dataset. A contact email is required by Squiggle."),
    "F1": ("Jolpica F1 · driver race results", "Race results back to 1950 where recorded; historical telemetry/lap data not complete."),
}
SOURCE_URLS = {
    "Soccer": "https://www.openligadb.de/lizenz",
    "NBA": "https://github.com/swar/nba_api",
    "AFL": "https://api.squiggle.com.au/",
    "F1": "https://github.com/jolpica/jolpica-f1",
}


def _get_json(url: str, user_agent: str = "GameSenseDesktop/0.4 (+historical statistics explorer)") -> object:
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=25) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code == 429:
            raise RuntimeError("Provider rate limit reached. Try again later.") from exc
        raise RuntimeError(f"Data provider returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"Cannot reach data provider: {exc}") from exc


def fetch_f1_season(year: int, reader=None) -> pd.DataFrame:
    """Fetch every paginated driver race result from Jolpica for one season."""
    if not 1950 <= int(year) <= date.today().year:
        raise ValueError("F1 season must be between 1950 and the current year.")
    reader = reader or _get_json
    offset = 0
    rows = []
    total = None
    while total is None or offset < total:
        url = f"https://api.jolpi.ca/ergast/f1/{year}/results.json?limit=100&offset={offset}"
        payload = reader(url)
        mr = payload.get("MRData", {})
        reported_limit = int(mr.get("limit", 0))
        reported_offset = int(mr.get("offset", offset))
        total = int(mr.get("total", 0))
        races = mr.get("RaceTable", {}).get("Races", [])
        if total and not reported_limit:
            raise RuntimeError("F1 provider returned invalid pagination metadata.")
        for race in races:
            for result in race.get("Results", []):
                driver = result.get("Driver", {})
                constructor = result.get("Constructor", {})
                fastest = result.get("FastestLap", {})
                rows.append({
                    "date": race.get("date"), "season": str(year),
                    "competitor": " ".join(filter(None, [driver.get("givenName"), driver.get("familyName")])),
                    "team": constructor.get("name", "Unknown"),
                    "driver_id": driver.get("driverId"), "round": race.get("round"),
                    "event": race.get("raceName"),
                    "points": result.get("points"), "finish_position": result.get("position"),
                    "grid_position": result.get("grid"), "laps": result.get("laps"),
                    "fastest_lap": (int(fastest.get("rank") == "1") if fastest.get("rank") is not None else None),
                    "status": result.get("status"), "record_type": "race",
                })
        if total == 0:
            break
        next_offset = reported_offset + reported_limit
        if next_offset <= offset:
            raise RuntimeError("F1 provider pagination did not advance.")
        offset = next_offset
    if not rows:
        raise ValueError(f"No F1 race results found for {year}.")
    frame = pd.DataFrame(rows)
    # Qualifying data are not complete for the entire 1950-onward archive.
    # For supported seasons, add Q1/Q2/Q3 and classification position where
    # Jolpica exposes them; otherwise retain real race results unchanged.
    if reader is None and year >= 1994:
        try:
            qual_rows = []
            offset = 0
            total_qual = None
            while total_qual is None or offset < total_qual:
                response = _get_json(
                    f"https://api.jolpi.ca/ergast/f1/{year}/qualifying.json?limit=100&offset={offset}")
                mr = response.get("MRData", {})
                limit = int(mr.get("limit", 0))
                total_qual = int(mr.get("total", 0))
                for race in mr.get("RaceTable", {}).get("Races", []):
                    for result in race.get("QualifyingResults", []):
                        qual_rows.append({
                            "round": str(race.get("round")),
                            "driver_id": result.get("Driver", {}).get("driverId"),
                            "qualifying_position": result.get("position"),
                            "q1_time": result.get("Q1"),
                            "q2_time": result.get("Q2"),
                            "q3_time": result.get("Q3"),
                        })
                if not total_qual:
                    break
                if limit <= 0:
                    break
                offset += limit
            if qual_rows:
                qualifying = pd.DataFrame(qual_rows).drop_duplicates(["round","driver_id"])
                frame["round"] = frame["round"].astype(str)
                frame = frame.merge(qualifying, on=["round","driver_id"], how="left")
        except (RuntimeError, ValueError, KeyError):
            # Missing/blocked qualifying feed is different from zero qualifying laps.
            pass
    return frame


def fetch_soccer_season(year: int, league: str = "bl1", reader=None) -> pd.DataFrame:
    """Fetch community-recorded Bundesliga *team match* data, not player stats."""
    if not 1963 <= int(year) <= date.today().year:
        raise ValueError("Bundesliga season must start between 1963 and the current year.")
    if league not in {"bl1", "bl2"}:
        raise ValueError("Only Bundesliga bl1 and bl2 are enabled.")
    reader = reader or _get_json
    matches = reader(f"https://api.openligadb.de/getmatchdata/{league}/{year}")
    if not isinstance(matches, list):
        raise RuntimeError("Unexpected OpenLigaDB response.")
    rows = []
    for match in matches:
        if not match.get("matchIsFinished"):
            continue
        final = next((r for r in match.get("matchResults", [])
                      if r.get("resultName") == "Endergebnis"), None)
        if final is None:
            results = match.get("matchResults", [])
            final = max(results, key=lambda r: r.get("resultOrderID", 0)) if results else None
        if not final:
            continue
        home, away = match.get("team1") or {}, match.get("team2") or {}
        h, a = final.get("pointsTeam1"), final.get("pointsTeam2")
        if h is None or a is None:
            continue
        for team, opponent, scored, conceded in [(home, away, h, a), (away, home, a, h)]:
            name = team.get("teamName", "Unknown club")
            rows.append({
                "date": (match.get("matchDateTimeUTC") or match.get("matchDateTime") or "")[:10],
                "season": f"{year}-{str(year + 1)[-2:]}",
                "competitor": name, "team": name, "opponent": opponent.get("teamName", ""),
                "goals": scored, "goals_against": conceded,
                "goal_difference": scored - conceded,
                "wins": int(scored > conceded), "draws": int(scored == conceded),
                "losses": int(scored < conceded),
                "points_table": 3 if scored > conceded else 1 if scored == conceded else 0,
                "event": f"{name} vs {opponent.get('teamName', '')}",
                "record_type": "team match",
            })
    if not rows:
        raise ValueError(f"No completed league results available for {year}.")
    return pd.DataFrame(rows)


def fetch_nba_season(year: int) -> pd.DataFrame:
    """NBA season player-level per-game stats; endpoint access may be restricted."""
    if not 1996 <= int(year) < date.today().year + 1:
        raise ValueError("NBA player dashboard supports seasons starting in 1996 or later.")
    try:
        from nba_api.stats.endpoints import leaguedashplayerstats
    except ImportError as exc:
        raise RuntimeError("NBA connector unavailable: install the optional nba_api package.") from exc
    season = f"{year}-{str(year + 1)[-2:]}"
    try:
        raw = leaguedashplayerstats.LeagueDashPlayerStats(
            season=season, per_mode_detailed="PerGame", timeout=30
        ).get_data_frames()[0]
    except Exception as exc:
        raise RuntimeError(f"NBA Stats request failed or was blocked: {exc}") from exc
    if raw.empty:
        raise ValueError(f"NBA Stats returned no player rows for {season}.")
    # These are one row per player/season, NOT one row per game.
    fields = {
        "PLAYER_ID": "player_id", "GP": "games", "MIN": "minutes", "PTS": "points",
        "REB": "rebounds", "AST": "assists", "STL": "steals", "BLK": "blocks",
        "TOV": "turnovers", "FG_PCT": "fg_pct", "FG3_PCT": "three_pt_pct",
        "FT_PCT": "ft_pct", "FGM": "fgm", "FGA": "fga", "FG3M": "three_pt_made",
        "FG3A": "three_pt_attempted", "FTM": "ftm", "FTA": "fta",
        "OREB": "offensive_rebounds", "DREB": "defensive_rebounds",
        "PLUS_MINUS": "plus_minus", "W": "wins", "L": "losses",
    }
    # Preserve the entire numeric NBA base stat line, not just the five
    # headline metrics. Unknown provider columns remain visible in Data Studio.
    columns = {a: b for a, b in fields.items() if a in raw}
    reserved = {"PLAYER_NAME", "TEAM_ABBREVIATION", "TEAM_ID"}
    for col in raw.columns:
        if col not in columns and col not in reserved:
            columns[col] = col.lower()
    df = raw.rename(columns=columns).copy()

    # Advanced measures (usage, true shooting, efficiency, ratings etc.) are
    # best-effort; NBA Stats may block calls or omit older historical seasons.
    try:
        advanced = leaguedashplayerstats.LeagueDashPlayerStats(
            season=season, per_mode_detailed="PerGame",
            measure_type_detailed_defense="Advanced", timeout=30
        ).get_data_frames()[0]
        if not advanced.empty and "PLAYER_ID" in advanced and "player_id" in df:
            names = [col for col in advanced.columns
                     if col not in {"PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION"}
                     and pd.api.types.is_numeric_dtype(advanced[col])]
            adv = advanced[["PLAYER_ID", *names]].rename(
                columns={"PLAYER_ID": "player_id",
                         **{col: "advanced_" + col.lower() for col in names}})
            df = df.merge(adv.drop_duplicates("player_id"), how="left", on="player_id")
            df["advanced_data_status"] = "available where recorded"
        else:
            df["advanced_data_status"] = "not returned by provider"
    except Exception:
        df["advanced_data_status"] = "NBA advanced endpoint unavailable"
    # The date below is ONLY a chronological season marker. NBA season-level
    # averages are not recorded as if they occurred in a single match.
    df["date"] = f"{year + 1}-06-30"
    df["date_is_marker"] = True
    df["season"] = season
    df["competitor"] = raw["PLAYER_NAME"]
    df["team"] = raw["TEAM_ABBREVIATION"]
    df["record_type"] = "player season (per-game averages)"
    leading = ["date", "season", "competitor", "team", "record_type"]
    return df[leading + [col for col in df.columns if col not in leading and col not in reserved]]


def fetch_afl_season(year: int, contact_email: str | None = None, reader=None) -> pd.DataFrame:
    """Squiggle AFL team-game scores; never pretends this is player-level data.

    The Squiggle API mandates an identifying contact email in User-Agent.
    This address is sent only to the Squiggle provider and is not persisted.
    """
    if not 2000 <= int(year) <= date.today().year:
        raise ValueError("Squiggle match coverage is approximately 2000 onward.")
    email = (contact_email or "").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Squiggle requires a real contact email to identify API users.")
    user_agent = f"GameSenseDesktop/0.4 contact={email}"
    read = reader or (lambda url: _get_json(url, user_agent=user_agent))
    games_payload = read(f"https://api.squiggle.com.au/?q=games;year={year}")
    teams_payload = read(f"https://api.squiggle.com.au/?q=teams;year={year}")
    if not isinstance(games_payload, dict) or not isinstance(teams_payload, dict):
        raise RuntimeError("Unexpected Squiggle API response.")
    clubs = {str(t["id"]): t.get("name", str(t["id"]))
             for t in teams_payload.get("teams", []) if t.get("id") is not None}
    def team_name(value):
        return clubs.get(str(value), str(value or "Unknown"))
    rows = []
    for game in games_payload.get("games", []):
        try:
            complete = float(game.get("complete") or 0)
        except (TypeError, ValueError):
            continue
        if complete < 100 or game.get("hscore") is None or game.get("ascore") is None:
            continue
        home = team_name(game.get("hteam"))
        away = team_name(game.get("ateam"))
        hscore, ascore = game["hscore"], game["ascore"]
        for name, opponent, score, conceded, goals, behinds in [
            (home, away, hscore, ascore, game.get("hgoals"), game.get("hbehinds")),
            (away, home, ascore, hscore, game.get("agoals"), game.get("abehinds"))
        ]:
            rows.append({
                "date": str(game.get("date") or "")[:10], "season": str(year),
                "competitor": name, "team": name, "opponent": opponent,
                "goals": goals, "behinds": behinds, "points_scored": score,
                "points_against": conceded, "margin": score - conceded,
                "wins": int(score > conceded), "draws": int(score == conceded),
                "losses": int(score < conceded), "round": game.get("round"),
                "venue": game.get("venue"), "event": f"{home} vs {away}",
                "record_type": "team match",
            })
    if not rows:
        raise ValueError(f"No completed Squiggle AFL matches for {year}.")
    return pd.DataFrame(rows)


def fetch_season(sport: str, year: int, contact_email: str | None = None) -> tuple[pd.DataFrame, str]:
    """Return records and an accurate provenance label for one season."""
    if sport == "F1":
        return fetch_f1_season(year), f"Jolpica F1 · {year} race results"
    if sport == "NBA":
        return fetch_nba_season(year), f"NBA Stats · {year}-{str(year+1)[-2:]} per-game player season averages"
    if sport == "Soccer":
        return fetch_soccer_season(year), f"OpenLigaDB · Bundesliga {year}/{year+1} TEAM match results"
    if sport == "AFL":
        return fetch_afl_season(year, contact_email), f"Squiggle API · {year} AFL TEAM match results"
    raise ValueError(f"Unsupported sport: {sport}")
