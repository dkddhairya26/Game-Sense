"""Historical library can span whole coverage and safely resume a partial archive."""
import pandas as pd
from datetime import date

from gamesense.history import EARLIEST, cache_years, merge_season, plan_years
from gamesense.analytics import clean_data


def _nba(year, source="NBA Stats · example season"):
    return pd.DataFrame([{
        "date": f"{year+1}-06-30", "season": f"{year}-{str(year+1)[-2:]}",
        "competitor": "Test Athlete", "team": "TEAM", "games": 20,
        "points": 25.1, "rebounds": 7, "assists": 5, "steals": None, "blocks": None,
        "data_source": source, "record_type": "player season (per-game averages)",
    }])


def test_full_nba_history_now_starts_1946():
    years=plan_years("NBA")
    assert years[0]==1946
    assert years[-1]==date.today().year
    assert len(years)==date.today().year-1946+1
    assert EARLIEST["NBA"]==1946


def test_demo_seasons_never_count_as_cached():
    fake=_nba(2023,source="FICTIONAL DEMO DATA")
    assert not cache_years(fake,"NBA")
    assert 2023 in plan_years("NBA",2020,2024,cached=cache_years(fake,"NBA"))


def test_real_cached_years_are_skipped_but_current_refreshes():
    curr=date.today().year
    assert plan_years("F1",curr-2,curr,
                      cached={curr-2,curr-1,curr})==[curr]
    assert plan_years("F1",curr-2,curr-1,
                      cached={curr-2,curr-1})==[]


def test_merge_preserves_unrelated_imports_and_updates_same_year():
    custom=_nba(2024,"Student licensed dataset")
    old=_nba(2024,"NBA Stats · older")
    old["points"]=17
    existing,_=clean_data(pd.concat([custom,old],ignore_index=True),"NBA")
    newer=_nba(2024,"NBA Stats · 2024-25")
    merged=merge_season(existing,newer,"NBA","NBA Stats · 2024-25")
    assert len(merged)==2
    assert (merged["points"]==25.1).sum()==2
    assert len(cache_years(merged,"NBA"))==1
    assert any(merged["data_source"]=="Student licensed dataset")


def test_one_season_at_a_time_keeps_past_years():
    first=merge_season(None,_nba(2000),"NBA","NBA Stats · 2000-01")
    second=merge_season(first,_nba(2001),"NBA","NBA Stats · 2001-02")
    assert cache_years(second,"NBA")=={2000,2001}


def test_provider_range_validation():
    import pytest
    with pytest.raises(ValueError):
        plan_years("NBA",1945,1947)
    with pytest.raises(ValueError):
        plan_years("F1",2024,2020)
