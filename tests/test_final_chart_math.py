"""Verify the numbers exported by native charts, independently of screenshots."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from gamesense.charts import AnalyticsChart


@pytest.fixture
def chart():
    app=QApplication.instance() or QApplication([])
    widget=AnalyticsChart()
    yield widget
    widget.close()


def frame(kind="season_total"):
    return pd.DataFrame([
        dict(competitor_id="test:a",competitor="Controlled test athlete",team="A",
             season="2020",date="2020-06-30",date_precision="season",record_kind=kind,
             points=100.,games_played=10.),
        dict(competitor_id="test:a",competitor="Controlled test athlete",team="B",
             season="2021",date="2021-06-30",date_precision="season",record_kind=kind,
             points=900.,games_played=30.),
    ])


def test_season_line_is_per_game_and_transfer_stints_weight_games(chart):
    source=frame()
    chart.plot(source,"NBA",["test:a"],"points",mode="Season trend")
    assert chart.plotted_data["mean_points"].tolist()==[10.,30.]
    # Two stints in the same season: (100+900)/(10+30)=25PPG.
    chart.plot(source.assign(season="2020"),"NBA",["test:a"],"points",mode="Season trend")
    assert chart.plotted_data["mean_points"].tolist()==[25.]


def test_rolling_form_does_not_average_raw_season_totals(chart):
    chart.plot(frame(),"NBA",["test:a"],"points",mode="Rolling average")
    assert chart.plotted_data["points"].tolist()==[10.,25.]


def test_cumulative_reconstructs_pergame_rows_using_observed_games(chart):
    source=frame("season_average").assign(points=[10.,30.])
    chart.plot(source,"NBA",["test:a"],"points",mode="Cumulative total")
    assert chart.plotted_data["points"].tolist()==[100.,1000.]
    assert "approximate" in chart.explanation.text()


def test_cumulative_uses_record_kind_even_when_generic_type_exists(chart):
    source=frame("season_average").assign(points=[10.,30.],record_type="user-imported record")
    chart.plot(source,"NBA",["test:a"],"points",mode="Cumulative total")
    assert chart.plotted_data["points"].tolist()==[100.,1000.]


def test_season_without_games_never_claims_pergame_values(chart):
    chart.plot(frame().assign(games_played=None),"NBA",["test:a"],"points",mode="Season trend")
    assert chart.plotted_data.empty or chart.plotted_data["mean_points"].isna().all()


def test_both_game_aliases_remain_available_row_by_row(chart):
    source=frame().assign(games=[None,30.],games_played=[10.,None])
    chart.plot(source,"NBA",["test:a"],"points",mode="Season trend")
    assert chart.plotted_data["mean_points"].tolist()==[10.,30.]


@pytest.mark.parametrize("metric",["experimental_rating","advanced_pace","offensive_rating"])
def test_new_scores_and_advanced_rates_do_not_form_cumulative_totals(chart,metric):
    chart.plot(frame().assign(**{metric:[50.,60.]}),"NBA",["test:a"],metric,mode="Cumulative total")
    assert chart.plotted_data.empty
