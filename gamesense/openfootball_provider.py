"""OpenFootball CC0 European club match results (no key, no player-stat claims).

Files are generated from the openfootball/football.json project. Match score
records contain clubs, fixtures, and final goals; they do NOT identify match
participants, scorers or individual player statistics.

Data: https://github.com/openfootball/football.json  (CC0-1.0).
Some upstream league-season directories are incomplete or absent. A missing
file never creates fictional fixtures or an empty "complete" season.
"""
from __future__ import annotations

from datetime import date
from urllib.error import HTTPError
import re
import threading

from .archive import data_directory
from .http import Cancelled, HttpClient
from .provider_base import Provider, ProviderMeta, _base, _client
from .club_identity import club_id

REPO = "https://raw.githubusercontent.com/openfootball/football.json/master"
CATALOGUE = "https://api.github.com/repos/openfootball/football.json/contents"
# Verified filename naming conventions. Availability changes by year and
# upstream contributors; this is a catalogue, not a completeness guarantee.
LEAGUES = {
    "en.1": "English Premier League", "en.2": "EFL Championship",
    "en.3": "EFL League One", "en.4": "EFL League Two",
    "es.1": "Spanish La Liga", "es.2": "Spanish Segunda",
    "de.1": "German Bundesliga", "de.2": "German 2. Bundesliga",
    "it.1": "Italian Serie A", "it.2": "Italian Serie B",
    "fr.1": "French Ligue 1", "fr.2": "French Ligue 2",
    "pt.1": "Portuguese Primeira Liga", "nl.1": "Dutch Eredivisie",
    "tr.1": "Turkish Süper Lig",
}
# English Championship and equivalent second divisions matter: clubs can
# be relegated/promoted while preserving the same real identity.
DEFAULT_LEAGUES = (
    "en.1", "en.2", "es.1", "es.2", "de.1", "de.2",
    "it.1", "it.2", "fr.1", "fr.2", "pt.1", "nl.1")
SEASON_PATTERN = re.compile(r"^20\d{2}-\d{2}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def fixture_records(payload, season: str, code: str, today: date | None = None):
    """Convert final published match results into two team records per game.

    Supports both the score=[home,away] and score={ft:[home,away]} formats.
    No roster, player score, estimated date, expected-goals or shots are added.
    """
    if code not in LEAGUES or not SEASON_PATTERN.fullmatch(season):
        raise ValueError("Unknown league or invalid season format.")
    if not isinstance(payload, dict) or not isinstance(payload.get("matches"), list):
        raise ValueError("OpenFootball did not return a matches array.")
    today = today or date.today()
    source = f"{REPO}/{season}/{code}.json"
    meta = OpenFootballProvider.meta
    rows = []
    for index, match in enumerate(payload["matches"]):
        if not isinstance(match, dict):
            continue
        iso_date = str(match.get("date") or "")[:10]
        if not DATE_PATTERN.fullmatch(iso_date):
            continue
        try:
            played = date.fromisoformat(iso_date)
        except ValueError:
            continue
        if played > today:
            continue
        home, away = str(match.get("team1") or "").strip(), str(match.get("team2") or "").strip()
        if not home or not away or home == away:
            continue
        score = match.get("score")
        if isinstance(score, dict):
            score = score.get("ft")
        if not (isinstance(score, list) and len(score) == 2):
            continue
        if not all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in score):
            continue
        h, a = score
        competition = LEAGUES[code]
        round_name = str(match.get("round") or "")
        for side, team, opponent, scored, conceded, venue in (
            ("home", home, away, h, a, "home"),
            ("away", away, home, a, h, "away"),
        ):
            # Country-scoped canonical club IDs carry a real team through
            # divisions and minor source naming changes (Aston Villa / FC).
            # Never merge individual players with clubs.
            identity = club_id(team, code)
            rows.append(_base(
                meta, season,
                record_id=(f"openfootball:{code}:{season}:{iso_date}:" 
                           f"{re.sub(r'[^a-z0-9]+','-',home.casefold())}:"
                           f"{re.sub(r'[^a-z0-9]+','-',away.casefold())}:{side}"),
                date=iso_date, date_precision="day",
                record_kind="team_match", entity_type="team",
                competition=competition, competition_id=code,
                team_id=identity, competitor_id=identity,
                competitor=team, team=team, opponent=opponent,
                event=f"{home} vs {away}", round=round_name,
                home_away=venue,
                goals=scored, goals_against=conceded,
                goal_difference=scored-conceded,
                points=scored,
                points_against=conceded,
                wins=int(scored > conceded),
                draws=int(scored == conceded),
                losses=int(scored < conceded),
                table_points=3 if scored > conceded else 1 if scored == conceded else 0,
                source_url=source))
    return rows


class OpenFootballProvider(Provider):
    meta = ProviderMeta(
        "openfootball", "OpenFootball · European leagues (CC0, no key)",
        "Soccer", "team match results from multiple domestic leagues",
        "Creative Commons CC0-1.0 public domain dedication",
        "https://github.com/openfootball/football.json",
        "Free club fixtures, final results and league tables where recorded. "
        "Includes the Premier League, La Liga, Bundesliga, Serie A, Ligue 1 "
        "and other leagues from their published years. These are CLUB/MATCH "
        "records — no player rosters, goalscorers, assists or athlete stats. "
        "Seasons can be incomplete, especially active seasons.",
        "openfootball/football.json · CC0 1.0 · "
        "https://github.com/openfootball/football.json")

    def available_seasons(self, client=None):
        active = _client(client)
        contents = active.get_json(CATALOGUE, max_age=86400)
        seasons = [r["name"] for r in contents
                   if isinstance(r, dict) and r.get("type") == "dir"
                   and SEASON_PATTERN.fullmatch(str(r.get("name") or ""))]
        if not seasons:
            raise RuntimeError("OpenFootball season catalogue unavailable.")
        return sorted(set(seasons))

    def competitions(self, client=None):
        years = self.available_seasons(client)
        # A documented league catalogue, not a claim every league-year exists.
        return [
            dict(competition_id=code, season_id=year,
                 competition_name=name, season_name=year)
            for year in reversed(years)
            for code, name in LEAGUES.items()
        ]

    @staticmethod
    def get_league(client, code, season, force=False):
        if code not in LEAGUES or not SEASON_PATTERN.fullmatch(str(season)):
            raise ValueError("Unsupported league/season")
        url = f"{REPO}/{season}/{code}.json"
        payload = client.get_json(url, max_age=0 if force else 604800)
        return fixture_records(payload, str(season), code)

    def iter_season(self, season, client, archive=None, force=False):
        successful = 0
        for code in DEFAULT_LEAGUES:
            client.check()
            try:
                rows = self.get_league(client, code, season, force)
            except Exception as exc:
                # Only missing league-season files may be skipped. Provider 429,
                # network failure and invalid responses must remain visible.
                if "404" in str(exc) or isinstance(exc, FileNotFoundError):
                    continue
                raise
            if rows:
                successful += 1
                yield rows
        if not successful:
            raise ValueError(f"No completed OpenFootball league fixtures available in {season}.")

    def download(self, archive, seasons, client=None, cancel=None,
                 progress=None, force=False):
        """Never mark a partial set of country leagues as all-football-complete."""
        cancel = cancel or threading.Event()
        client = _client(client, cancel)
        selected = list(dict.fromkeys(str(x) for x in seasons))
        progress = progress or (lambda done, total, message: None)
        count = 0
        for index, season in enumerate(selected, 1):
            if cancel.is_set():
                raise Cancelled("Stopped; previously saved seasons remain available.")
            progress(index-1, len(selected), f"OpenFootball {season}: downloading leagues")
            found = False
            try:
                for batch in self.iter_season(season, client, archive, force):
                    count += archive.upsert(batch)
                    found = True
                archive.mark(self.meta.id, "Soccer", season, "partial",
                             "Several supported club leagues; no player-level data. "
                             "Only matches with final scores are included.")
                if not found:
                    raise ValueError(f"No final match results for {season}")
            except Exception as exc:
                archive.mark(self.meta.id, "Soccer", season, "failed", str(exc))
                raise
            progress(index, len(selected), f"OpenFootball {season}: {count:,} club match records saved")
        return count

    def download_competition(self, archive, competition_id, season_id,
                             client=None, cancel=None, progress=None):
        code, season = str(competition_id), str(season_id)
        if code not in LEAGUES:
            raise ValueError("Choose a supported league")
        if not SEASON_PATTERN.fullmatch(season):
            raise ValueError("Choose a valid season")
        client = _client(client, cancel)
        rows = self.get_league(client, code, season)
        if not rows:
            raise ValueError(f"No completed matches found for {LEAGUES[code]} {season}")
        count = archive.upsert(rows)
        archive.mark(self.meta.id, "Soccer", f"{season} / {code}", "partial",
                     f"{LEAGUES[code]} scores only; not player statistics. "
                     f"{len(rows)//2} final games.")
        if progress:
            progress(1, 1, f"{LEAGUES[code]} {season}: saved {len(rows)//2} matches")
        return count
