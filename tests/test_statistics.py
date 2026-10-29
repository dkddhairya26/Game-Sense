"""Regression checks for denominators and non-additive sports statistics."""
import pandas as pd
import pytest
from gamesense.analytics import metric_summary, weighted_average, is_rate, lower_is_better, leaderboard, clean_data, rankings


def test_season_totals_use_games_played_not_number_of_seasons():
    rows = pd.DataFrame({'points':[100,300,None], 'games_played':[10,20,5], 'record_kind':['season_total']*3})
    result = metric_summary(rows, 'points')
    assert result['total'] == 400
    assert result['per_game'] == pytest.approx(400/30)
    assert result['count'] == 2


def test_missing_season_denominator_does_not_invent_appearances():
    rows = pd.DataFrame({'points':[100,300], 'games_played':[10,None], 'record_kind':['season_total']*2})
    assert metric_summary(rows, 'points')['per_game'] is None


def test_missing_values_and_rate_denominators():
    assert weighted_average([10,None,30],[1,8,3]) == 25
    assert metric_summary(pd.DataFrame({'points':[None,None]}),'points')['total'] is None
    rows = pd.DataFrame({'points_pg':[10,30], 'games_played':[1,3]})
    assert metric_summary(rows,'points_pg')['total'] is None
    assert metric_summary(rows,'points_pg')['average'] == 25


def test_shooting_percentage_recomputed_from_attempts():
    rows = pd.DataFrame({'field_goal_pct':[1.,0.], 'field_goals_made':[1,0], 'field_goal_attempts':[1,9]})
    result = metric_summary(rows, 'field_goal_pct')
    assert result['average'] == .1
    assert result['total'] is None


@pytest.mark.parametrize('metric',['fastest_lap_time_ms','q1_ms','championship_position','championship_points','points_pg','age','usage_rate'])
def test_non_additive_metrics_never_get_career_totals(metric):
    assert is_rate(metric)
    assert metric_summary(pd.DataFrame({metric:[10,20]}),metric)['total'] is None


def test_same_name_athletes_stay_separate_and_latest_club_is_selected():
    rows = pd.DataFrame({'competitor_id':['a','a','b'],'competitor':['Same']*3,'team':['New','Old','Other'],
                         'date':pd.to_datetime(['2026-01-01','2020-01-01','2025-01-01']), 'points':[10,20,5]})
    result = leaderboard(rows, 'points')
    assert len(result) == 2
    assert result.iloc[0]['team'] == 'New'


def test_partial_custom_rating_remains_unknown():
    rows = pd.DataFrame([{'date':'2026-01-01','season':'2026','competitor':'A','team':'T','points':100}])
    assert pd.isna(clean_data(rows,'NBA')[0]['rating'].iloc[0])
    assert lower_is_better('finish_position')
    assert not lower_is_better('points')


def test_legacy_nba_season_averages_remain_weighted_and_convert_to_totals():
    rows = pd.DataFrame({'points':[10.,30.], 'games':[10,30], 'record_type':['player season (per-game averages)']*2})
    result = metric_summary(rows, 'points')
    assert result['total'] == 1000
    assert result['average'] == 25
    assert result['per_game'] == 25


def test_average_with_no_games_does_not_masquerade_as_season_total():
    rows = pd.DataFrame({'points':[10.,30.], 'record_kind':['season_average']*2})
    result = metric_summary(rows,'points')
    assert result['total'] is None
    assert result['per_game'] is None


def test_legacy_rankings_api_retains_games_weighted_semantics():
    rows = pd.DataFrame([{'date':f'{2020+i}-06-30','season':str(2020+i),'competitor':'A','team':'T',
                          'record_type':'player season (per-game averages)','games':games,
                          'points':points,'rebounds':5,'assists':2,'steals':1,'blocks':0}
                         for i,(games,points) in enumerate([(10,10),(30,30)])])
    result = rankings(clean_data(rows,'NBA')[0], 'NBA').iloc[0]
    assert result['appearances'] == 40
    assert result['points'] == 25


def test_import_retains_nested_event_evidence_and_normalizes_mixed_dates():
    first = {'date':'2024-01-01T12:00:00+10:00','season':'2024','competitor':'A','team':'T','pit_stop_events':[{'lap':4,'duration_ms':2000}]}
    second = {**first, 'date':'2024-02-01'}
    result, report = clean_data(pd.DataFrame([first,first,second]), 'F1')
    assert len(result) == 2
    assert report['duplicates_removed'] == 1
    assert result.iloc[0]['pit_stop_events'] == [{'lap':4,'duration_ms':2000}]
    assert result['date'].dt.tz is None
