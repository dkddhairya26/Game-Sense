"""Retained 0.5 import behavior plus explicit grains and ambiguity protection."""
import sqlite3

import pandas as pd
import pytest

from gamesense.importers import prepare_import
from gamesense.analytics import clean_data
from gamesense import storage


def test_nba_historical_season_stats_import():
    raw=pd.DataFrame([{'Player':'Sample Athlete','Team':'EX','Year':'2015-16',
        'PTS':18.5,'REB':6.2,'AST':4.4,'USG_PCT':27.1}])
    standard,notes=prepare_import(raw,'NBA')
    cleaned,_=clean_data(standard,'NBA')
    assert len(cleaned)==1
    assert cleaned.loc[0,'competitor']=='Sample Athlete'
    assert cleaned.loc[0,'points']==18.5
    assert cleaned.loc[0,'rebounds']==6.2
    assert cleaned.loc[0,'usg_pct']==27.1
    assert cleaned.loc[0,'date_is_marker']
    assert cleaned.loc[0,'date_precision']=='season'
    assert cleaned.loc[0,'record_kind']=='season_total'
    assert any('SORTING MARKER' in note for note in notes)


def test_afl_player_game_header_mapping():
    raw=pd.DataFrame([{'Player':'Example','Club':'Northern','Year':2021,
        'Match Date':'2021-05-01','D':30,'M':8,'T':6,'G':2}])
    standard,_=prepare_import(raw,'AFL')
    cleaned,_=clean_data(standard,'AFL')
    assert cleaned.iloc[0]['disposals']==30
    assert cleaned.iloc[0]['marks']==8
    assert cleaned.iloc[0]['tackles']==6
    assert cleaned.iloc[0]['goals']==2
    assert standard.iloc[0]['record_kind']=='event'


def test_import_requires_player_and_season():
    with pytest.raises(ValueError,match='competitor'):
        prepare_import(pd.DataFrame({'Year':[2020]}),'NBA')
    with pytest.raises(ValueError,match='season'):
        prepare_import(pd.DataFrame({'Player':['A']}),'Soccer')


def test_per_game_season_rows_are_explicitly_averages():
    raw=pd.DataFrame([{'Player':'A','Year':'2024-25','PTS':20,'GP':60,
        'record_type':'player season (per-game averages)'}])
    out,_=prepare_import(raw,'NBA')
    assert out.iloc[0]['record_kind']=='season_average'
    assert out.iloc[0]['games_played']==60
    assert out.iloc[0]['points']==20


def test_mixed_grains_and_existing_explicit_kind_are_preserved():
    raw=pd.DataFrame([
        {'Player':'A','Year':2024,'record_type':'season per game averages','record_kind':pd.NA},
        {'Player':'B','Year':2024,'record_type':'career research aggregate','record_kind':'career_total'}])
    out,_=prepare_import(raw,'NBA')
    assert out['record_kind'].tolist()==['season_average','career_total']


def test_shooting_aliases_match_canonical_archive_fields():
    raw=pd.DataFrame([{'Player':'A','Year':2024,'FGM':9,'FGA':20,'FG_PCT':.45,
        'FG3M':3,'FG3A':8,'FG3_PCT':.375,'FTM':5,'FTA':6,'FT_PCT':5/6}])
    out,_=prepare_import(raw,'NBA')
    assert out.iloc[0]['field_goals_made']==9
    assert out.iloc[0]['field_goal_attempts']==20
    assert out.iloc[0]['field_goal_pct']==.45
    assert out.iloc[0]['three_point_makes']==3
    assert out.iloc[0]['three_point_attempts']==8
    assert out.iloc[0]['three_point_pct']==.375
    assert out.iloc[0]['free_throw_attempts']==6
    assert out.iloc[0]['free_throw_pct']==5/6


def test_percent_header_is_distinct_from_made_field():
    raw=pd.DataFrame([{'Player':'A','Year':2024,'FG':9,'FG%':.45,'3P':3,'3P%':.375}])
    out,_=prepare_import(raw,'NBA')
    assert out.iloc[0]['field_goals_made']==9
    assert out.iloc[0]['field_goal_pct']==.45
    assert out.iloc[0]['three_point_pct']==.375


def test_ambiguous_aliases_are_rejected_without_mutating_input():
    raw=pd.DataFrame([{'Player':'A','Athlete':'B','Year':2024}])
    original=raw.copy(deep=True)
    with pytest.raises(ValueError,match='Ambiguous competitor'):
        prepare_import(raw,'NBA')
    pd.testing.assert_frame_equal(raw,original)


def test_canonical_column_wins_and_other_source_column_is_retained():
    raw=pd.DataFrame([{'competitor':'A','Player':'Source description','Year':2024,'points':20,'PTS':19}])
    out,_=prepare_import(raw,'NBA')
    assert out.iloc[0]['competitor']=='A'
    assert out.iloc[0]['player']=='Source description'
    assert out.iloc[0]['points']==20
    assert out.iloc[0]['pts']==19


def test_duplicate_normalized_headers_are_rejected():
    raw=pd.DataFrame([['A','B',2024]],columns=['Player name','player_name','Year'])
    with pytest.raises(ValueError,match='Duplicate column'):
        prepare_import(raw,'NBA')


def test_afl_short_aliases_not_applied_to_other_sports():
    raw=pd.DataFrame([{'Player':'A','Year':2024,'D':7,'G':2}])
    out,_=prepare_import(raw,'Soccer')
    assert 'd' in out and 'g' in out
    assert 'disposals' not in out and 'goals' not in out


def test_pre_1900_history_and_missing_team_are_supported():
    raw=pd.DataFrame([{'Player':'A','Year':1897}])
    out,notes=prepare_import(raw,'AFL')
    assert out.iloc[0]['date']==pd.Timestamp('1897-01-01')
    assert out.iloc[0]['team']=='Team not provided'
    assert len(notes)>=2


def test_legacy_storage_keeps_source_attribution(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'db_path',lambda:tmp_path/'legacy.sqlite3')
    frame=pd.DataFrame([{'season':'2024','competitor':'A'}])
    storage.save('NBA',frame,'Historical licensed import')
    assert len(storage.load('NBA'))==1
    assert storage.load_source('NBA')=='Historical licensed import'
    assert storage.load_source('F1') is None
