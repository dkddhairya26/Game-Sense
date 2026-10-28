"""Tests use fixed mock data and do not contact live sports APIs."""
import pandas as pd
from gamesense import providers, storage
from gamesense.analytics import clean_data


def test_f1_all_paginated_driver_results():
    calls = []
    def read(url):
        calls.append(url)
        offset = int(url.split("offset=")[1])
        results = [
            {"Driver":{"givenName":"Ada","familyName":"Racer","driverId":"ada"},
             "Constructor":{"name":"Example GP"},"points":"25","position":"1",
             "grid":"3","laps":"57","FastestLap":{"rank":"1"}}
        ]
        return {"MRData":{"limit":"1","offset":str(offset),"total":"2",
                          "RaceTable":{"Races":[{"date":"2024-03-02","round":str(offset+1),
                                                  "raceName":"Example GP","Results":results}]}}}
    df=providers.fetch_f1_season(2024,read)
    assert len(df)==2
    assert df["competitor"].tolist()==["Ada Racer","Ada Racer"]
    assert df["fastest_lap"].tolist()==[1,1]
    assert len(calls)==2
    clean,_=clean_data(df,"F1")
    assert len(clean)==2


def test_soccer_reads_final_score_not_half_time():
    matches=[{"matchIsFinished":True,"matchDateTimeUTC":"2024-09-01T12:00:00Z",
              "team1":{"teamName":"Home"},"team2":{"teamName":"Away"},
              "matchResults":[{"resultName":"Halbzeit","resultOrderID":1,
                               "pointsTeam1":0,"pointsTeam2":1},
                              {"resultName":"Endergebnis","resultOrderID":2,
                               "pointsTeam1":3,"pointsTeam2":2}]}]
    df=providers.fetch_soccer_season(2024,reader=lambda _:matches)
    assert len(df)==2
    home=df[df["competitor"]=="Home"].iloc[0]
    assert home["goals"]==3 and home["goals_against"]==2
    assert home["wins"]==1
    assert all(df["record_type"]=="team match")


def test_local_storage_keeps_source_attribution(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,"db_path",lambda:tmp_path/"gamesense.sqlite3")
    data=pd.DataFrame([{"season":"2024","competitor":"Player"}])
    storage.save("NBA",data,"NBA Stats · 2024-25")
    assert len(storage.load("NBA"))==1
    assert storage.load_source("NBA")=="NBA Stats · 2024-25"
    assert storage.load_source("F1") is None


def test_coverage_declares_every_sport():
    assert set(providers.COVERAGE)=={"Soccer","NBA","AFL","F1"}
    assert "player" in providers.COVERAGE["Soccer"][1].lower()


def test_afl_squiggle_only_completed_team_matches():
    def fake(url):
        if "q=teams" in url:
            return {"teams": [{"id": 1, "name": "Red Lions"}, {"id": 2, "name": "Blue Sharks"}]}
        return {"games": [
            {"date": "2024-06-01T04:00:00Z", "complete": 100, "hteam": 1, "ateam": 2,
             "hscore": 90, "ascore": 80, "hgoals": 14, "agoals": 12,
             "hbehinds": 6, "abehinds": 8, "round": 5, "venue": "Test Oval"},
            {"date": "2024-06-02", "complete": 50, "hteam": 1, "ateam": 2,
             "hscore": 30, "ascore": 40}
        ]}
    df = providers.fetch_afl_season(2024, contact_email="tester@example.org", reader=fake)
    assert len(df) == 2
    home = df[df["competitor"] == "Red Lions"].iloc[0]
    assert home["points_scored"] == 90
    assert home["wins"] == 1
    assert home["margin"] == 10
    assert all(df["record_type"] == "team match")
    cleaned, _ = clean_data(df, "AFL")
    assert cleaned["rating"].notna().all()


def test_afl_requires_contact_email():
    import pytest
    with pytest.raises(ValueError, match="contact email"):
        providers.fetch_afl_season(2024, contact_email="")
