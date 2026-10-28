"""Coverage and weighted historical statistics regression tests."""
import pandas as pd
from gamesense.analytics import clean_data, rankings
from gamesense import providers


def test_nba_multi_season_stats_weight_by_games():
    rows=[
        {"date":"2021-06-30","season":"2020-21","competitor":"A","team":"X",
         "record_type":"player season (per-game averages)","games":10,
         "points":10,"rebounds":5,"assists":2,"steals":1,"blocks":0},
        {"date":"2022-06-30","season":"2021-22","competitor":"A","team":"X",
         "record_type":"player season (per-game averages)","games":30,
         "points":30,"rebounds":5,"assists":2,"steals":1,"blocks":0},
    ]
    clean,_=clean_data(pd.DataFrame(rows),"NBA")
    result=rankings(clean,"NBA").iloc[0]
    assert result["appearances"]==40
    assert result["points"]==25.0


def test_nba_preserves_base_and_advanced_stats(monkeypatch):
    from nba_api.stats.endpoints import leaguedashplayerstats
    base=pd.DataFrame([{"PLAYER_ID":7,"PLAYER_NAME":"Test Player",
                       "TEAM_ABBREVIATION":"TST","GP":15,"MIN":30.1,
                       "PTS":22,"REB":9,"AST":6,"STL":1,"BLK":2,
                       "TS_PCT":.58,"W":9,"L":6}])
    advanced=pd.DataFrame([{"PLAYER_ID":7,"PLAYER_NAME":"Test Player",
                           "TEAM_ABBREVIATION":"TST","USG_PCT":.29,
                           "NET_RATING":6.5}])
    class Fake:
        def __init__(self,**kwargs):
            self.is_advanced=kwargs.get("measure_type_detailed_defense")=="Advanced"
        def get_data_frames(self):
            return [advanced if self.is_advanced else base]
    monkeypatch.setattr(leaguedashplayerstats,"LeagueDashPlayerStats",Fake)
    df=providers.fetch_nba_season(2024)
    assert df.loc[0,"competitor"]=="Test Player"
    assert df.loc[0,"points"]==22
    assert df.loc[0,"ts_pct"]==.58
    assert df.loc[0,"advanced_usg_pct"]==.29
    assert df.loc[0,"advanced_net_rating"]==6.5
