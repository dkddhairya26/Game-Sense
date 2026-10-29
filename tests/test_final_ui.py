"""Native Qt regression tests using explicitly controlled, fictional QA records.

Historical acceptance and real screenshots are generated separately by
scripts/final_acceptance.py. These fixtures test behavior, never sports claims.
"""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog

from gamesense.archive import Archive
from gamesense.images import PortraitWidget
from gamesense.window import GameSenseWindow


def wait_for(app, predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            app.processEvents()
            return
        time.sleep(.01)
    raise AssertionError('Native UI operation did not finish within the timeout.')


@pytest.fixture
def native_window(tmp_path, monkeypatch):
    monkeypatch.setenv('GAMESENSE_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('GAMESENSE_OFFLINE', '1')
    monkeypatch.setattr(Archive, 'seed_bundled', lambda self: 0)
    app = QApplication.instance() or QApplication([])
    window = GameSenseWindow()
    window.show()
    wait_for(app, lambda: not window.initializing)
    yield window, app
    window.close()
    window.pool.waitForDone(10000)
    app.processEvents()


def controlled_nba():
    return pd.DataFrame([
        {'date': f'2024-01-0{day}', 'season': '2024', 'competitor': name,
         'competitor_id': identity, 'team': 'CONTROLLED QA TEAM',
         'event_id': f'qa-{day}', 'entity_type': 'athlete',
         'points': 20 + day, 'rebounds': 8, 'assists': 6, 'steals': 1,
         'blocks': 1, 'turnovers': 2, 'field_goals_made': 8,
         'field_goal_attempts': 16, 'field_goal_pct': .5,
         'three_point_makes': 2, 'three_point_attempts': 5,
         'free_throws_made': 4, 'free_throw_attempts': 5}
        for identity, name in [('qa:a', 'CONTROLLED Example A'), ('qa:b', 'CONTROLLED Example B')]
        for day in range(1, 4)
    ])


def populate(window):
    window.archive.import_frame('NBA', controlled_nba(), 'CONTROLLED QA FIXTURE')
    window.sport.setCurrentText('NBA')
    window._change_sport()


def test_empty_archive_is_offline_and_every_sport_has_clear_empty_charts(native_window):
    window, app = native_window
    assert not window._online()
    for sport in ('Soccer', 'NBA', 'AFL', 'F1'):
        window.sport.setCurrentText(sport)
        window.navigate('dashboard')
        app.processEvents()
        assert window.frame.empty
        assert len(window.dash_visuals) == 6
        assert all(chart.plotted_data.empty for _, chart in window.dash_visuals)
        assert 'No records' in window.coverage_note.text()


def test_real_import_ui_background_worker_report_and_export(native_window, tmp_path, monkeypatch):
    window, app = native_window
    # A previously populated library must not hide the file just imported by
    # silently restoring another provider in the global source selector.
    populate(window)
    window.sport.setCurrentText('NBA')
    path = tmp_path / 'controlled-fixture.csv'
    rows = controlled_nba().iloc[:1].to_dict('records')
    rows += [rows[0].copy(), {**rows[0], 'competitor': 'REJECTED QA', 'points': -2}]
    pd.DataFrame(rows).to_csv(path, index=False)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (str(path), ''))
    window._import_file()
    wait_for(app, lambda: 'import' not in window.jobs)
    report = window.archive.setting('last_import_report')
    assert report['input_rows'] == 3
    assert report['duplicates_removed'] == 1
    assert report['invalid_rows_removed'] == 1
    assert report['inserted_rows'] == 1
    assert window.route == 'explorer'
    assert window._selected_provider() == report['source']
    assert set(window.raw_table.model().frame.provider) == {report['source']}
    assert window.quality_table.model().rowCount() > 8
    assert '1 inserted' in window.quality_note.text()
    window._import_file()
    wait_for(app, lambda: 'import' not in window.jobs)
    repeated = window.archive.setting('last_import_report')
    assert repeated['unchanged_rows'] == 1
    assert repeated['inserted_rows'] == 0
    destination = tmp_path / 'quality.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args, **kwargs: (str(destination), ''))
    window._export_quality_report()
    assert destination.is_file()
    assert 'unchanged_rows' in destination.read_text(encoding='utf-8')


def test_profile_rating_insights_and_explanation_are_visible(native_window):
    window, app = native_window
    populate(window)
    window.athlete.setCurrentIndex(window.athlete.findData('qa:a'))
    window.navigate('profiles')
    panel = window.profile_analysis
    assert panel.summary['score'] is not None
    assert panel.observations
    assert not panel.chart.plotted_data.empty
    index = window.profile_tabs.indexOf(panel)
    window.profile_tabs.setCurrentIndex(index)
    panel.explain_button.setChecked(True)
    app.processEvents()
    assert panel.formula.isVisible()
    assert 'EXPERIMENTAL' in panel.scope.text()
    assert '100' in panel.formula.text()


def test_comparison_compatible_values_and_incompatible_guard_clear_charts(native_window):
    window, app = native_window
    populate(window)
    window.compare_a.setCurrentIndex(window.compare_a.findData('qa:a'))
    window.compare_b.setCurrentIndex(window.compare_b.findData('qa:b'))
    window.navigate('compare')
    assert window.comparison_stats.model().rowCount() > 5
    assert 'Compatible' in window.comparison_note.text()
    assert not window.compare_trend.plotted_data.empty
    assert not window.compare_ratings.plotted_data.empty
    incompatible = window.comparison_frame.copy()
    incompatible.loc[incompatible.competitor_id.eq('qa:b'), 'entity_type'] = 'team'
    window.comparison_frame = incompatible
    window._plot_comparison()
    app.processEvents()
    assert 'different units' in window.comparison_note.text()
    assert window.comparison_stats.model().rowCount() == 0
    assert window.compare_trend.plotted_data.empty
    assert window.compare_radar.plotted_data.empty
    assert window.compare_recent.plotted_data.empty
    assert window.compare_ratings.plotted_data.empty


def test_local_search_reveals_record_hidden_by_wrong_source_filter(native_window):
    window, app = native_window
    populate(window)
    extra = controlled_nba().iloc[:1].copy()
    extra['competitor'] = 'CONTROLLED Hidden Athlete'
    extra['competitor_id'] = 'qa:hidden'
    window.archive.import_frame('NBA', extra, 'OTHER CONTROLLED SOURCE')
    window._change_sport()
    window.search.setText('Hidden Athlete')
    window.search_timer.stop()
    window._search_changed()
    assert window.athlete.findData('qa:hidden') >= 0
    assert window._selected_provider() == 'OTHER CONTROLLED SOURCE'
    assert 'found' in window.search_context.text()
    assert len(window.profile_frame) == 1


def test_unavailable_photo_is_an_explicit_neutral_fallback(native_window, tmp_path):
    window, app = native_window
    portrait = PortraitWidget(size=168, cache_dir=tmp_path / 'empty-portraits')
    portrait.set_athlete('qa:missing', 'CONTROLLED Unknown Identity', 'NBA', online=False)
    wait_for(app, lambda: not portrait._jobs)
    assert portrait.pixmap.isNull()
    assert not portrait.metadata
    assert portrait.status == 'No verified licensed portrait available'
    portrait.close()


def test_constructor_comparison_aggregates_recorded_driver_starts(native_window):
    window, app = native_window
    rows = []
    for team_id, team, points, finishes in (
            ('qa:constructor:a', 'CONTROLLED Constructor A', [10, 6], [1, 3]),
            ('qa:constructor:b', 'CONTROLLED Constructor B', [8, 2], [2, 7])):
        for index in range(2):
            rows.append({'date': f'2024-01-0{index + 1}', 'season': '2024',
                         'competitor': f'CONTROLLED Driver {team_id} {index}',
                         'competitor_id': f'{team_id}:driver:{index}',
                         'team': team, 'team_id': team_id, 'event_id': f'qa-race-{index}',
                         'entity_type': 'athlete', 'points': points[index],
                         'finish_position': finishes[index], 'grid_position': 5})
    window.archive.import_frame('F1', pd.DataFrame(rows), 'CONTROLLED CONSTRUCTOR FIXTURE')
    window.sport.setCurrentText('F1')
    window._change_sport()
    window.compare_kind.setCurrentIndex(1)
    window.navigate('compare')
    frame = window.comparison_frame
    assert set(frame.entity_type) == {'constructor'}
    assert frame.competitor_id.nunique() == 2
    assert frame.groupby('team_id').points.sum().to_dict() == {
        'qa:constructor:a': 16, 'qa:constructor:b': 10}
    assert 'driver starts' in window.comparison_note.text()
    assert 'official constructor standings' in window.comparison_note.text()
    table = window.comparison_stats.model().frame
    assert 'Points' in set(table.statistic)
    assert not window.compare_trend.plotted_data.empty
