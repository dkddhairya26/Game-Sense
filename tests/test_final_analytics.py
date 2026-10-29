"""Small arithmetic examples independently check the final analytical features.

Fixtures here are controlled test inputs, not bundled sport results. Expected
values are written as hand calculations so tests do not merely copy algorithms.
"""
import pandas as pd
import pytest

from gamesense.analytics import is_rate, metric_summary
from gamesense.insights import performance_summary, statistical_insights
from gamesense.ratings import rating_frame, rating_history, rating_summary, rating_explanation
from gamesense.team_analytics import club_summary


def clubs(sport="Soccer"):
    # Oldest to newest: W W D L W W; current W-run2, longest W-run2.
    values=[(2,0),(1,0),(1,1),(0,3),(3,1),(1,0)]
    return pd.DataFrame([
        {"date":f"2024-01-{i+1:02d}","season":"2024","provider":"controlled-fixture",
         "entity_type":"team","record_kind":"team_match","competitor":"Test Club",
         "competitor_id":"test-club","record_id":str(i),"home_away":"home" if i%2==0 else "away",
         ("goals" if sport=="Soccer" else "points"):scored,
         ("goals_against" if sport=="Soccer" else "points_against"):conceded}
        for i,(scored,conceded) in enumerate(values)])


def test_manual_club_wdl_averages_form_home_away_and_streaks():
    result=club_summary(clubs(),"Soccer")
    assert (result["wins"],result["draws"],result["losses"])==(4,1,1)
    assert result["win_rate"]==pytest.approx(100*4/6)
    assert result["scored"]==8 and result["conceded"]==5
    assert result["avg_scored"]==pytest.approx(8/6)
    assert result["difference"]==3
    assert result["form"]=="WWDLWW"
    assert result["last5"]["matches"]==5 and result["last5"]["wins"]==3
    assert result["last10"]["matches"]==6
    assert result["home"]["wins"]==2 and result["away"]["losses"]==1
    assert result["current_winning_streak"]==2 and result["max_winning_streak"]==2
    assert result["current_losing_streak"]==0 and result["max_losing_streak"]==1


def test_undated_clubs_do_not_claim_last_five_match_chronology():
    frame=clubs().assign(date_precision="season")
    stats=club_summary(frame,"Soccer")
    assert stats["matches"]==6
    assert stats["last5"] is None and stats["form"]==""


def test_invalid_or_missing_scores_not_counted_as_zero_results():
    frame=clubs().iloc[:1].copy()
    missing=frame.assign(record_id="missing",goals=float("nan"))
    negative=frame.assign(record_id="invalid",goals=-1)
    infinity=frame.assign(record_id="infinite",goals=float("inf"))
    same_missing_id=pd.concat([frame.assign(record_id=None),frame.assign(record_id=None)])
    assert club_summary(pd.concat([frame,missing,negative,infinity]),"Soccer")["matches"]==1
    assert club_summary(same_missing_id,"Soccer")["matches"]==2


def test_afl_scoring_percentage_is_ratio_of_points_not_accuracy():
    frame=clubs("AFL").iloc[:2].copy()
    frame["points"]=[100,80]
    frame["points_against"]=[50,100]
    frame["goals"]=[15,12]
    frame["behinds"]=[10,8]
    result=club_summary(frame,"AFL")
    assert result["scoring_percentage"]==120 #180/150*100
    assert result["goals"]==27 and result["behinds"]==18
    frame.loc[frame.index[0],"behinds"]=None
    assert club_summary(frame,"AFL")["behinds"] is None
    frame["points_against"]=0
    assert club_summary(frame,"AFL")["scoring_percentage"] is None


@pytest.mark.parametrize("sport,row,expected",[
    ("NBA",dict(points=20,rebounds=7.5,assists=6),50),
    ("Soccer",dict(goals=.5,assists=.35,shots=2.5,tackles=2.5),50),
    ("AFL",dict(disposals=17.5,marks=5,tackles=5,goals=2.5),50),
    ("F1",dict(finish_position=1,grid_position=1),90),
])
def test_each_sport_manual_normalised_rating(sport,row,expected):
    frame=pd.DataFrame([{**row,"date":"2024-01-01","season":"2024","competitor_id":"a"}])
    assert rating_frame(frame,sport).iloc[0]["experimental_rating"]==pytest.approx(expected)
    assert "not an official" in rating_explanation(sport)


def test_club_rating_result_and_margin_have_declared_weights():
    # 2-0 win: 70 +30*(.5+2/8) =92.5. 1-1 draw:35+15=50.
    rated=rating_frame(clubs(),"Soccer")
    assert rated.iloc[0]["experimental_rating"]==92.5
    assert rated.iloc[2]["experimental_rating"]==50


@pytest.mark.parametrize("sport,metrics",[
    ("Soccer",dict(goals=100,goals_against=80)),
    ("AFL",dict(points=1000,points_against=800)),
])
def test_club_season_totals_never_imply_a_single_match_win(sport,metrics):
    frame=pd.DataFrame([dict(entity_type="team",record_kind="season_total",
                             games_played=38,**metrics)])
    rated=rating_frame(frame,sport)
    assert pd.isna(rated.iloc[0]["experimental_rating"])
    assert rated.iloc[0]["rating_status"]=="match-level club scores required"
    assert rating_summary(frame,sport)["score"] is None
    assert "season's total scores cannot establish" in rating_explanation(sport,"team")


def test_season_totals_and_pergame_rows_produce_same_rating():
    total=pd.DataFrame([dict(points=200,rebounds=75,assists=60,games_played=10,record_kind="season_total")])
    average=pd.DataFrame([dict(points=20,rebounds=7.5,assists=6,games=10,record_kind="season_per_game_average")])
    assert rating_frame(total,"NBA").iloc[0]["experimental_rating"]==50
    assert rating_frame(average,"NBA").iloc[0]["experimental_rating"]==50
    total["games_played"]=None
    assert pd.isna(rating_frame(total,"NBA").iloc[0]["experimental_rating"])


def test_partial_rating_never_redistributes_missing_weights_and_clamps_outlier():
    frame=pd.DataFrame([dict(points=20,rebounds=10),dict(points=100,rebounds=50,assists=50),dict(points=0,rebounds=0,assists=0)])
    rated=rating_frame(frame,"NBA")
    assert pd.isna(rated.iloc[0]["experimental_rating"])
    assert rated.iloc[1]["experimental_rating"]==100
    assert rated.iloc[2]["experimental_rating"]==0


def test_rating_period_weights_games_and_season_history_keeps_its_grain():
    frame=pd.DataFrame([
        dict(date="2023-06-30",season="2022-23",competitor_id="a",points=200,rebounds=75,assists=60,games=10,record_kind="season_total",date_precision="season"),
        dict(date="2024-06-30",season="2023-24",competitor_id="a",points=1200,rebounds=450,assists=360,games=30,record_kind="season_total",date_precision="season"),
    ])
    # Season scores50,100; games weighted(50*10+100*30)/40=87.5.
    summary=rating_summary(frame,"NBA")
    assert summary["score"]==87.5
    assert summary["recent_label"]=="last five recorded seasons"
    assert summary["recent_score"]==75
    assert sum(component["score_contribution"] for component in summary["components"])==pytest.approx(summary["score"])
    history=rating_history(frame,"NBA")
    assert history.iloc[-1]["recent_rating"]==75
    assert set(history["rating_grain"])=={"season"}


def test_recent_rating_uses_actual_last_five_window_before_missing_filter():
    # First game100; subsequent5games0,0,0,0,unknown. Recent score0,
    # not20from silently replacing the latest unknown game with the older100.
    rows=[dict(date=f"2024-01-{i+1:02d}",season="2024",competitor_id="a",
               points=40 if i==0 else 0,rebounds=15 if i==0 else 0,
               assists=12 if i==0 else None if i==5 else 0) for i in range(6)]
    frame=pd.DataFrame(rows)
    summary=rating_summary(frame,"NBA")
    assert summary["recent_score"]==0
    assert summary["recent_window_observations"]==5
    assert summary["recent_observations"]==4
    assert summary["recent_unavailable_observations"]==1
    assert rating_history(frame,"NBA").iloc[-1]["recent_rating"]==0


def test_dual_games_columns_have_a_rowwise_denominator():
    frame=pd.DataFrame(dict(points=[100,900],games=[None,30],games_played=[10,None],record_kind=["season_total"]*2))
    assert metric_summary(frame,"points")["per_game"]==25


def test_career_shooting_weights_legacy_pergame_attempts_by_real_games():
    # Season A1/1*10games; B0/9*30games. Career10/280, not1/10.
    frame=pd.DataFrame(dict(field_goals_made=[1,0],field_goal_attempts=[1,9],
                            games=[10,30],record_kind=["season_average"]*2))
    result=metric_summary(frame,"field_goal_pct")
    assert result["average"]==pytest.approx(10/280)


def test_manual_nba_totals_and_derived_shooting_efficiency():
    frame=pd.DataFrame([dict(points=200,rebounds=80,assists=40,games=10,
                            field_goals_made=70,field_goal_attempts=150,
                            three_point_makes=20,free_throw_attempts=50,record_kind="season_total")])
    stats=performance_summary(frame,"NBA")
    assert stats["points"]==200 and stats["points_per_game"]==20
    assert stats["rebounds_per_game"]==8 and stats["assists_per_game"]==4
    assert stats["effective_field_goal_pct"]==pytest.approx(80/150)
    assert stats["estimated_true_shooting_pct"]==pytest.approx(200/(2*(150+.44*50)))


def test_f1_positions_are_not_totals_missing_is_not_a_zero_finish():
    frame=pd.DataFrame([
        dict(date="2023-05-01",season="2023",event_id="1",points=25,finish_position=1,grid_position=3,qualifying_position=2),
        dict(date="2024-05-01",season="2024",event_id="2",points=15,finish_position=3,grid_position=4,qualifying_position=4),
        dict(date="2024-06-01",season="2024",event_id="3",points=0,finish_position=None,grid_position=0,qualifying_position=None),
    ])
    stats=performance_summary(frame,"F1")
    assert stats["wins"]==1 and stats["podiums"]==2
    assert stats["average_finish"]==2 and stats["average_grid"]==3.5
    assert stats["points"]==40 and stats["unrecorded_finishes"]==1
    assert stats["qualifying_to_finish_gain"]==1
    assert stats["recent_results"][0]["finish_position"] is None
    assert pd.isna(rating_frame(frame,"F1").iloc[2]["experimental_rating"])


def test_f1_constructor_averages_actual_driver_starts_and_sums_points():
    frame=pd.DataFrame([dict(event_id="one",finish_position=1,grid_position=2,points=25),
                        dict(event_id="one",finish_position=4,grid_position=3,points=12)]).assign(date="2024-01-01",season="2024")
    result=performance_summary(frame,"F1")
    assert result["races"]==1 and result["starts"]==2
    assert result["average_finish"]==2.5 and result["points"]==37
    assert result["rating"]["recent_label"]=="last five recorded driver starts"


def test_insight_claims_match_exact_sample_and_include_source_period():
    result=statistical_insights(clubs(),"Soccer")
    assert "won 3 of the last 5 dated recorded matches" in result[0]["text"]
    assert result[0]["source"]=="controlled-fixture"
    assert result[0]["period"]=="2024-01-01 to 2024-01-06"
    assert result[0]["records"]==5
    assert statistical_insights(pd.DataFrame(),"Soccer")==[]


@pytest.mark.parametrize("metric",["experimental_rating","recent_rating","offensive_rating","advanced_pace_rate","minutes_weighted_game_usage","points_game_high"])
def test_new_rates_and_highs_never_sum_into_false_career_totals(metric):
    assert is_rate(metric)
    assert metric_summary(pd.DataFrame({metric:[10,20]}),metric)["total"] is None
