"""Source-shaped regression tests distinguish explicit zero from missing data.

The pinned F1DB v2026.18.0 primary archive contains 8,592 non-null points and
19,095 null points (no explicit zeros). Every bundled value matched that input
in the live audit. Controlled zero fixtures here ensure future provider releases
can legitimately supply zero without a truthiness conversion discarding it.
"""
import csv
import io
import json
import zipfile

import pytest

from gamesense.provider_base import _number
from gamesense.providers import F1DBProvider, NBAProvider


@pytest.mark.parametrize("value",[0,0.0,"0","0.000"," 0 "])
def test_provider_number_preserves_explicit_zero(value):
    assert _number(value)==0


@pytest.mark.parametrize("value",[None,"","not recorded"])
def test_provider_number_leaves_missing_and_invalid_unknown(value):
    assert _number(value) is None


def f1_source_archive():
    """Construct actual F1DB split-file schemas with three points states."""
    race_results=[]
    for race,points in [(1,0),(2,None),(3,"omitted")]:
        result=dict(raceId=race,year=2024,driverId="test-driver",
                    constructorId="test-team",positionDisplayOrder=11,
                    positionNumber=11,positionText="11",gridPositionNumber=12,
                    qualificationPositionNumber=12,fastestLap=False,polePosition=False,
                    positionsGained=1,laps=50)
        if points!="omitted":
            result["points"]=points
        race_results.append(result)
    files={
        "drivers":[dict(id="test-driver",name="Controlled Driver")],
        "constructors":[dict(id="test-team",name="Controlled Constructor")],
        "races":[dict(id=i,date=f"2024-01-{i:02d}") for i in range(1,4)],
        "races-race-results":race_results,
        "races-qualifying-results":[],"races-fastest-laps":[],
        "races-driver-standings":[dict(raceId=1,driverId="test-driver",points=0,positionNumber=11)],
        "races-pit-stops":[],
    }
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,"w") as archive:
        for name,rows in files.items():
            archive.writestr("f1db-"+name+".json",json.dumps(rows))
    return zipfile.ZipFile(io.BytesIO(buffer.getvalue()))


def test_f1_mapping_preserves_zero_null_and_absent_points_separately():
    with f1_source_archive() as source:
        records=list(F1DBProvider.normalize_zip(source,release="controlled-schema-fixture"))
    assert len(records)==3
    assert records[0]["points"]==0
    assert records[1]["points"] is None
    assert records[2]["points"] is None
    assert records[0]["championship_points"]==0
    assert records[0]["fastest_lap"]==0
    assert records[0]["pole_positions"]==0
    assert records[0]["source_version"]=="controlled-schema-fixture"


def test_nba_csv_mapping_preserves_real_zero_and_blank_statistics():
    columns=["season","player_name","team","position","games_played",
             "points","rebounds","assists","field_goals_made",
             "field_goal_attempts","field_goal_pct"]
    text=io.StringIO()
    writer=csv.DictWriter(text,fieldnames=columns)
    writer.writeheader()
    writer.writerow(dict.fromkeys(columns,"0") | dict(season="2024-25",player_name="Source Zero",team="T",position="G",games_played="1"))
    writer.writerow(dict.fromkeys(columns,"") | dict(season="2024-25",player_name="Source Missing",team="T",position="G",games_played="1"))
    class SourceClient:
        def get_bytes(self,url,**kwargs):
            assert url=="https://boxscorelab.com/downloads/2024-25-player-season-totals.csv"
            return text.getvalue().encode("utf8")
    provider=NBAProvider()
    provider._ids={"sourcezero":"1","sourcemissing":"2"}
    records=list(provider.iter_season("2024-25",SourceClient()))[0]
    for metric in ("points","rebounds","assists","field_goals_made","field_goal_attempts","field_goal_pct"):
        assert records[0][metric]==0
        assert records[1][metric] is None
