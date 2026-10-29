"""No-network tests for new real club matches and AFL player-game import."""
from __future__ import annotations

from datetime import date
import csv
import io
import json
import zipfile

import pytest

from gamesense.archive import Archive
from gamesense.openfootball_provider import (
    OpenFootballProvider, LEAGUES, fixture_records
)
from gamesense.afl_player_provider import (
    AFLPlayerArchiveProvider, normalize_player_rows
)


def test_openfootball_score_array_or_final_score():
    payload={"name":"Premier League","matches":[
        {"date":"2025-09-01","team1":"Liverpool FC","team2":"Arsenal FC",
         "round":"Matchday 1","score":{"ft":[3,1],"ht":[1,1]}},
        {"date":"2025-10-03","team1":"Chelsea FC","team2":"Newcastle FC",
         "score":[2,2]},
        {"date":"2026-12-01","team1":"Team Future","team2":"Team Next",
         "score":None},
        {"date":"2025-11-01","team1":"Unplayed","team2":"Another",
         "score":None},
    ]}
    rows=fixture_records(payload,"2025-26","en.1",today=date(2026,10,29))
    assert len(rows)==4
    liverpool=next(r for r in rows if r["competitor"]=="Liverpool FC")
    arsenal=next(r for r in rows if r["competitor"]=="Arsenal FC")
    assert liverpool["goals"]==3 and liverpool["goals_against"]==1
    assert liverpool["wins"]==1 and liverpool["table_points"]==3
    assert arsenal["losses"]==1 and arsenal["table_points"]==0
    chelsea=next(r for r in rows if r["competitor"]=="Chelsea FC")
    assert chelsea["draws"]==1 and chelsea["table_points"]==1
    assert all(r["record_kind"]=="team_match" for r in rows)
    assert all(r["entity_type"]=="team" for r in rows)
    assert all("player" not in r for r in rows)
    assert all(r["license"].startswith("Creative Commons CC0") for r in rows)


def test_openfootball_source_preserves_real_team_identity_across_seasons():
    team = [{"date":"2023-09-01","team1":"Arsenal FC","team2":"Chelsea FC","score":[1,0]}]
    a=fixture_records({"matches":team},"2023-24","en.1")
    b=fixture_records({"matches":team},"2024-25","en.1")
    assert a[0]["competitor_id"]==b[0]["competitor_id"]
    assert a[0]["record_id"]!=b[0]["record_id"]


def test_openfootball_download_competition_does_not_claim_all_leagues(tmp_path,monkeypatch):
    provider=OpenFootballProvider()
    archive=Archive(tmp_path/"teams.sqlite")
    source={"matches":[
        {"date":"2025-09-01","team1":"Real Madrid","team2":"Barcelona",
         "score":{"ft":[2,2]}}
    ]}
    monkeypatch.setattr(provider,"get_league",lambda client,code,season,force=False:
                        fixture_records(source,season,code))
    class DummyClient:
        def check(self): pass
    assert provider.download_competition(archive,"es.1","2025-26",client=DummyClient())==2
    assert archive.stats("Soccer")["competitors"]==2
    coverage=archive.coverage("Soccer")
    assert coverage[0]["status"]=="partial"
    assert "not player statistics" in coverage[0]["error"].lower()


def test_afl_player_columns_are_real_not_zero_filled():
    source={
        "team":"Western Bulldogs","year":"2023","games_played":"115",
        "opponent":"Richmond","round":"3","result":"W",
        "kicks":"17","marks":"5","handballs":"18",
        "disposals":"35","goals":"2","behinds":"",
        "tackles":"8","contested_possessions":"14",
    }
    rows=normalize_player_rows(
        "AFL-Data-Analysis-main/data/players/bontempelli_marcus_24111995_performance_details.csv",
        [source])
    assert len(rows)==1
    row=rows[0]
    assert row["competitor"]=="Marcus Bontempelli"
    assert row["competitor_id"]=="aflresearch:bontempelli_marcus_24111995"
    assert row["record_kind"]=="player_match_without_date"
    assert row["date_is_sort_marker"] is True
    assert row["disposals"]==35 and row["tackles"]==8
    assert row["wins"]==1
    assert "behinds" not in row
    assert row["record_kind"] != "player_season_aggregate"


def test_afl_research_zip_reads_only_selected_year(tmp_path):
    archive=Archive(tmp_path/"afl.sqlite")
    source_rows=[
        {"team":"Richmond","year":"2020","games_played":"1",
         "opponent":"Sydney","round":"1","result":"W","kicks":"8",
         "handballs":"9","disposals":"17","marks":"3","tackles":"5"},
        {"team":"Richmond","year":"2021","games_played":"2",
         "opponent":"Essendon","round":"2","result":"L","kicks":"11",
         "handballs":"6","disposals":"17","marks":"","tackles":"2"},
    ]
    io_stream=io.BytesIO()
    with zipfile.ZipFile(io_stream,"w") as z:
        writer=io.StringIO()
        csvw=csv.DictWriter(writer,fieldnames=list(source_rows[0]))
        csvw.writeheader()
        csvw.writerows(source_rows)
        z.writestr("AFL-Data-Analysis-main/data/players/aarts_jake_08121994_performance_details.csv",
                   writer.getvalue())
    class Client:
        def check(self):pass
        def get_bytes(self,*a,**kw):return io_stream.getvalue()
    provider=AFLPlayerArchiveProvider()
    count=provider.download(archive,["2020"],client=Client())
    assert count==1
    data=archive.query("AFL")
    assert len(data)==1
    assert data.loc[0,"competitor"]=="Jake Aarts"
    assert data.loc[0,"kicks"]==8
    assert data.loc[0,"disposals"]==17
    assert archive.coverage("AFL")[0]["status"]=="partial"


def test_afl_research_project_unverified_source_rights():
    p=AFLPlayerArchiveProvider()
    assert "rights" in p.meta.license.lower()
    assert p.meta.sport=="AFL"
    assert "afltables" not in p.meta.id


def test_openfootball_major_leagues_are_present():
    assert {"en.1","es.1","de.1","it.1","fr.1"} <= set(LEAGUES)
    assert len(LEAGUES)>=12
