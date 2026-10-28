"""On-demand historical data connectors with honest coverage labels.

Source data is not bundled or redistributed. Users initiate a specific
season download; network failures are reported rather than hidden.
"""
from __future__ import annotations

import json
from datetime import date
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import pandas as pd

COVERAGE = {
    "Soccer": ("OpenLigaDB · Bundesliga match/team results", "Team-level only. Volunteer-maintained; no complete player statistics."),
    "NBA": ("NBA Stats · season player averages", "NBA player-season aggregates where the NBA endpoint responds; older/advanced fields vary."),
    "AFL": ("Imported licensed datasets", "No bundled historical player feed. Import a permitted AFL dataset to analyse it."),
    "F1": ("Jolpica F1 · driver race results", "Race results back to 1950 where recorded; historical telemetry/lap data not complete."),
}
SOURCE_URLS = {
    "Soccer": "https://www.openligadb.de/lizenz",
    "NBA": "https://github.com/swar/nba_api",
    "AFL": "https://www.afl.com.au/stats",
    "F1": "https://github.com/jolpica/jolpica-f1",
}


def _get_json(url: str) -> object:
    request = Request(url, headers={"User-Agent": "GameSenseDesktop/0.3 (+historical statistics explorer)", "Accept": "application/json"})
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
    return pd.DataFrame(rows)


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
    columns = {a: b for a, b in fields.items() if a in raw}
    df = raw.rename(columns=columns).copy()
    df["date"] = f"{year + 1}-06-30"
    df["season"] = season
    df["competitor"] = raw["PLAYER_NAME"]
    df["team"] = raw["TEAM_ABBREVIATION"]
    df["record_type"] = "player season (per-game averages)"
    return df[["date", "season", "competitor", "team", "record_type", *columns.values()]]


def fetch_season(sport: str, year: int) -> tuple[pd.DataFrame, str]:
    """Return records and an accurate provenance label for one season."""
    if sport == "F1":
        return fetch_f1_season(year), f"Jolpica F1 · {year} race results"
    if sport == "NBA":
        return fetch_nba_season(year), f"NBA Stats · {year}-{str(year+1)[-2:]} per-game player season averages"
    if sport == "Soccer":
        return fetch_soccer_season(year), f"OpenLigaDB · Bundesliga {year}/{year+1} TEAM match results"
    if sport == "AFL":
        raise ValueError("No approved AFL historical feed configured. Import a licensed CSV/Excel dataset.")
    raise ValueError(f"Unsupported sport: {sport}")
