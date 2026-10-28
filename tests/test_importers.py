import pandas as pd
import pytest
from gamesense.importers import prepare_import
from gamesense.analytics import clean_data


def test_nba_historical_season_stats_import():
    raw = pd.DataFrame([{"Player": "Sample Athlete", "Team": "EX", "Year": "2015-16",
                         "PTS": 18.5, "REB": 6.2, "AST": 4.4, "USG_PCT": 27.1}])
    standard, notes = prepare_import(raw, "NBA")
    cleaned, info = clean_data(standard, "NBA")
    assert len(cleaned)==1
    assert cleaned.loc[0,"competitor"]=="Sample Athlete"
    assert cleaned.loc[0,"points"]==18.5
    assert cleaned.loc[0,"rebounds"]==6.2
    assert cleaned.loc[0,"usg_pct"]==27.1
    assert cleaned.loc[0,"date_is_marker"]
    assert any("SORTING MARKER" in note for note in notes)


def test_afl_player_game_header_mapping():
    raw=pd.DataFrame([{"Player":"Example","Club":"Northern",
                       "Year":2021,"Match Date":"2021-05-01",
                       "D":30,"M":8,"T":6,"G":2}])
    standard,_=prepare_import(raw,"AFL")
    cleaned,_=clean_data(standard,"AFL")
    assert cleaned.iloc[0]["disposals"]==30
    assert cleaned.iloc[0]["marks"]==8
    assert cleaned.iloc[0]["tackles"]==6
    assert cleaned.iloc[0]["goals"]==2


def test_import_requires_player_and_season():
    with pytest.raises(ValueError,match="competitor"):
        prepare_import(pd.DataFrame({"Year":[2020]}),"NBA")
    with pytest.raises(ValueError,match="season"):
        prepare_import(pd.DataFrame({"Player":["A"]}),"Soccer")
