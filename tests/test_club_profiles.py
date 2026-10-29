"""Real club-career QA: English Premier League, Championship and AFL team scoring.

Records are fixture-shaped samples. They test parsing and aggregation, not
claims that future results, lineups, player goals or xG have been sourced.
"""
from __future__ import annotations

from datetime import date
import pandas as pd

from gamesense.archive import Archive
from gamesense.club_identity import club_id
from gamesense.openfootball_provider import DEFAULT_LEAGUES, fixture_records
from gamesense.team_analytics import (
    club_summary, club_season_table, club_match_table)


def source_fixture(season, competition, home, away, score, when):
    return fixture_records(
        {"matches":[{"date":when,"team1":home,"team2":away,
                     "score":{"ft":list(score)},"round":"Matchday 1"}]},
        season,competition,today=date(2026,10,29))


def test_aston_villa_aliases_unify_and_country_names_are_scoped():
    assert club_id("Aston Villa", "en.2") == club_id("Aston Villa FC", "en.1")
    assert club_id("Arsenal FC", "en.1") == club_id("Arsenal", "en.2")
    assert club_id("Manchester United", "en.1") == club_id("Manchester United FC", "en.1")
    assert club_id("FC Barcelona", "es.1") == club_id("Barcelona", "es.2")
    assert club_id("Aston Villa", "en.1") != club_id("Aston Villa", "es.1")
    assert club_id("Aston Villa", "en.1") != "openfootball:en.1:aston-villa"
    assert "en.2" in DEFAULT_LEAGUES


def test_team_career_spans_premier_league_and_championship(tmp_path):
    archive=Archive(tmp_path/"clubs.sqlite")
    club_champ=source_fixture(
        "2018-19","en.2","Aston Villa","Hull City",[3,1],"2018-08-04")
    club_epl=source_fixture(
        "2025-26","en.1","Aston Villa FC","Newcastle United FC",[0,0],"2025-08-16")
    archive.upsert(club_champ+club_epl)
    identity=club_id("Aston Villa FC","en.1")
    matches=archive.query("Soccer",competitor_id=identity,limit=None)
    assert len(matches)==2
    assert set(matches["competition"])=={"English Premier League","EFL Championship"}
    stats=club_summary(matches,"Soccer")
    assert stats["matches"]==2
    assert stats["wins"]==1 and stats["draws"]==1 and stats["losses"]==0
    assert stats["scored"]==3 and stats["conceded"]==1
    assert stats["difference"]==2
    assert stats["league_points"]==4
    assert stats["seasons"]==2 and stats["leagues"]==2
    seasons=club_season_table(matches,"Soccer")
    assert len(seasons)==2
    assert "EFL Championship" in seasons["competition"].tolist()
    match_log=club_match_table(matches,"Soccer")
    assert len(match_log)==2
    assert set(match_log["result"])=={"D","W"}
    assert all("assists" not in row for row in club_champ+club_epl)


def test_selected_league_season_only_presents_clubs_with_real_data(tmp_path):
    archive=Archive(tmp_path/"filtered.sqlite")
    archive.upsert(source_fixture(
        "2018-19","en.2","Aston Villa","Hull City",[3,1],"2018-08-04"))
    archive.upsert(source_fixture(
        "2025-26","en.1","Aston Villa FC","Newcastle United FC",[0,0],"2025-08-16"))
    res=archive.search("Soccer",text="Aston Villa",
                       season="2025-26",competition="English Premier League")
    assert len(res)==1
    cid=club_id("Aston Villa FC","en.1")
    assert res.iloc[0]["competitor_id"]==cid
    # Full club profile may intentionally ignore the currently selected league.
    assert len(archive.query("Soccer",competitor_id=cid))==2
    assert archive.search(
        "Soccer",text="Aston Villa",season="2018-19",
        competition="English Premier League").empty
    assert len(archive.search(
        "Soccer",text="Aston Villa",season="2018-19",
        competition="EFL Championship"))==1


def test_upgrading_from_v08_preserves_real_games_and_repairs_id(tmp_path):
    archive=Archive(tmp_path/"legacy.sqlite")
    old=source_fixture(
        "2018-19","en.2","Aston Villa","Hull City",[3,1],"2018-08-04")
    new=source_fixture(
        "2025-26","en.1","Aston Villa FC","Newcastle United FC",[0,0],"2025-08-16")
    for row in old+new:
        old_code=row["competition_id"]
        row["competitor_id"]="openfootball:"+old_code+":"+(
            row["competitor"].lower().replace(" ","-"))
        row["team_id"]=row["competitor_id"]
    archive.upsert(old+new)
    assert archive.stats("Soccer")["competitors"]==4
    before=archive.count("Soccer")
    assert archive.reconcile_openfootball_clubs()==4
    assert archive.count("Soccer")==before
    assert archive.stats("Soccer")["competitors"]==4-1
    cid=club_id("Aston Villa","en.1")
    assert len(archive.query("Soccer",competitor_id=cid))==2
    assert archive.reconcile_openfootball_clubs()==0


def test_team_stats_skip_missing_scores_and_do_not_fabricate_player_statistics():
    data=pd.DataFrame([
        {"entity_type":"team","record_kind":"team_match","record_id":"a",
         "season":"2025-26","competition":"English Premier League",
         "competitor":"Aston Villa FC","goals":2,"goals_against":1},
        {"entity_type":"team","record_kind":"team_match","record_id":"b",
         "season":"2025-26","competition":"English Premier League",
         "competitor":"Aston Villa FC","goals":None,"goals_against":0},
        {"entity_type":"athlete","record_kind":"player_match","record_id":"c",
         "season":"2025-26","competition":"English Premier League",
         "competitor":"Example Player","goals":8,"goals_against":0},
        {"entity_type":"team","record_kind":"team_match","record_id":"a",
         "season":"2025-26","competition":"English Premier League",
         "competitor":"Aston Villa FC","goals":2,"goals_against":1},
    ])
    stats=club_summary(data,"Soccer")
    assert stats["matches"]==1
    assert stats["scored"]==2 and stats["conceded"]==1
    assert stats["wins"]==1
    assert stats["league_points"] is None
    assert "assists" not in club_season_table(data,"Soccer")


def test_afl_team_scores_and_wdl_are_not_mislabeled_as_disposals():
    frame=pd.DataFrame([
        {"record_id":"afl:1","entity_type":"team","record_kind":"event",
         "season":"2024","competition":"AFL","date":"2024-04-01",
         "competitor":"Collingwood","points":101,"points_against":98},
        {"record_id":"afl:2","entity_type":"team","record_kind":"event",
         "season":"2024","competition":"AFL","date":"2024-04-08",
         "competitor":"Collingwood","points":77,"points_against":84},
    ])
    totals=club_summary(frame,"AFL")
    assert totals["matches"]==2
    assert totals["wins"]==1 and totals["losses"]==1
    assert totals["scored"]==178 and totals["conceded"]==182
    assert totals["league_points"] is None
    assert club_season_table(frame,"AFL").iloc[0]["W"]==1
