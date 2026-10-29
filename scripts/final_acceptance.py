"""Reproduce final acceptance in the real native Qt application, offline.

This deliberately complements unit tests: it opens source-backed profiles,
changes the same selectors a user operates, checks calculated chart datasets,
and captures actual widgets. Controlled import/guard fixtures are explicitly
labelled and are never presented as historical sporting evidence.

Run from the repository root:
    python scripts/final_acceptance.py --with-local-afl

The optional AFL check reads *records only* from the existing user archive in
SQLite read-only mode. It copies those into an isolated .qa database, never
settings, credentials or the production database itself. No network is used.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sqlite3
import sys
import time
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'evidence' / 'final_acceptance')
    parser.add_argument('--with-local-afl', action='store_true',
                        help='Read real AFL records from an existing archive for a separate, isolated acceptance scenario')
    parser.add_argument('--local-archive', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    runtime = ROOT / '.qa' / ('final-acceptance-' + str(time.time_ns()))
    runtime.mkdir(parents=True, exist_ok=True)
    os.environ['GAMESENSE_DATA_DIR'] = str(runtime)
    os.environ['GAMESENSE_OFFLINE'] = '1'
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

    import pandas as pd
    from PySide6.QtCore import qVersion
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication, QFileDialog
    from gamesense.club_identity import club_id
    from gamesense.images import PortraitWidget
    from gamesense.team_analytics import club_summary
    from gamesense.window import GameSenseWindow

    app = QApplication.instance() or QApplication([])
    if not QFontDatabase.families() and sys.platform == 'win32':
        fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
        for name in ('segoeui.ttf', 'segoeuib.ttf', 'arial.ttf'):
            if (fonts / name).exists():
                QFontDatabase.addApplicationFont(str(fonts / name))
    cases, unhandled = [], []
    previous_hook = sys.excepthook
    sys.excepthook = lambda kind, value, tb: unhandled.append(
        ''.join(traceback.format_exception_only(kind, value)).strip())

    def settle(predicate=None, timeout=60):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            app.processEvents()
            if predicate is None or predicate():
                app.processEvents()
                return
            time.sleep(.01)
        raise AssertionError('Native operation exceeded its acceptance timeout.')

    window = GameSenseWindow()
    window.show()
    settle(lambda: not window.initializing, timeout=120)

    def capture(name, route=None, full_page=False):
        if route:
            window.navigate(route)
        settle()
        target = window.pages[window.route].widget() if full_page else window
        path = output / (name + '.png')
        if not target.grab().save(str(path)):
            raise AssertionError('Screenshot could not be saved: ' + name)
        return path.name

    def case(name, expected, operation, fixture=False, required=True):
        entry = {'case': name, 'expected': expected,
                 'dataset': 'CONTROLLED FICTIONAL QA FIXTURE' if fixture else 'ACTUAL SOURCE-BACKED RECORDS',
                 'required': required}
        try:
            actual = operation()
            entry.update(status='pass', actual=actual)
        except Exception as exc:
            entry.update(status='fail', actual=str(exc), error_type=type(exc).__name__)
        cases.append(entry)
        print(name + ': ' + entry['status'], flush=True)
        return entry

    def select(sport, provider=None, entity=None, season=None, competition=None, query=''):
        window.sport.setCurrentText(sport)
        combos = [(window.source_filter, provider, True),
                  (window.entity_filter, entity, True),
                  (window.season, season, False),
                  (window.competition_filter, competition, False)]
        for combo, value, is_data in combos:
            combo.blockSignals(True)
            if value is None:
                combo.setCurrentIndex(0)
            else:
                index = combo.findData(value) if is_data else combo.findText(str(value))
                if index < 0:
                    combo.blockSignals(False)
                    raise AssertionError(f'{sport}: requested recorded selector value is missing: {value}')
                combo.setCurrentIndex(index)
            combo.blockSignals(False)
        window.search.blockSignals(True)
        window.search.setText(query)
        window.search.blockSignals(False)
        window.search_timer.stop()
        window._update_identities()
        window.refresh()
        settle()

    def open_identity(identity):
        index = window.athlete.findData(identity)
        if index < 0:
            raise AssertionError('Stable competitor identity is missing from the selected population: ' + identity)
        window.athlete.setCurrentIndex(index)
        window.navigate('profiles')
        window._load_profile()
        settle()
        if window.profile_frame.empty:
            raise AssertionError('The profile contains no actual records.')

    def startup():
        stats = {sport: window.archive.stats(sport) for sport in ('Soccer', 'NBA', 'AFL', 'F1')}
        for sport in ('Soccer', 'NBA', 'F1'):
            assert stats[sport]['records'] > 0, sport + ' bundled history is absent.'
        assert not window._online(), 'Offline mode was not applied.'
        return {'coverage': stats, 'screenshot': capture('01-offline-startup', 'home')}
    case('Offline first startup', 'Fresh isolated archive loads the real licensed starter without network requests.', startup)

    def fresh_afl():
        select('AFL')
        window.navigate('dashboard')
        assert window.archive.count('AFL') == 0
        assert all(chart.plotted_data.empty for _, chart in window.dash_visuals)
        assert 'No records' in window.coverage_note.text()
        return {'records': 0, 'state': 'AFL is an on-demand archive; a fresh install explains the absence.',
                'screenshot': capture('02-afl-fresh-archive-empty')}
    case('Honest fresh-install AFL state', 'No invented AFL player or club statistics before a permitted source is downloaded.', fresh_afl)

    copied_afl = 0
    local_afl_issue = ''
    if args.with_local_afl:
        source = args.local_archive
        if source is None and sys.platform == 'win32':
            source = Path(os.environ.get('LOCALAPPDATA', '')) / 'GameSense' / 'archive.sqlite3'
        try:
            if not source or not source.is_file():
                raise FileNotFoundError('No existing local AFL archive is available.')
            con = sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)
            try:
                # Selecting payloads only excludes the settings table, where
                # contacts and provider credentials belong. Bound memory use.
                records = [json.loads(row[0]) for row in con.execute(
                    "SELECT payload FROM records WHERE sport='AFL' ORDER BY date DESC LIMIT 20000")]
            finally:
                con.close()
            if records:
                copied_afl = window.archive.upsert(records, overwrite=False)
            else:
                local_afl_issue = 'The existing archive contains no AFL records.'
        except Exception as exc:
            local_afl_issue = str(exc)

    def aston_villa():
        select('Soccer', 'openfootball', 'team', '2025-26', 'English Premier League', 'Aston Villa')
        identity = club_id('Aston Villa FC', 'en.1')
        window.profile_full_history.setChecked(True)
        open_identity(identity)
        full = window.profile_frame.copy()
        assert {'English Premier League', 'EFL Championship'}.issubset(set(full.competition))
        assert {'2018-19', '2025-26'}.issubset(set(full.season.astype(str)))
        assert club_summary(full, 'Soccer')['matches'] >= 20
        assert window.profile_match_table.model().rowCount() >= 20
        screenshots = [capture('03-aston-villa-full-history')]
        window.profile_full_history.setChecked(False)
        select('Soccer', 'openfootball', 'team', '2018-19', 'EFL Championship', 'Aston Villa')
        open_identity(identity)
        selected = window.profile_frame
        assert set(selected.competition) == {'EFL Championship'}
        assert set(selected.season.astype(str)) == {'2018-19'}
        assert club_summary(selected, 'Soccer')['matches'] > 0
        screenshots.append(capture('04-aston-villa-championship'))
        window.profile_full_history.setChecked(True)
        return {'stable_id': identity, 'full_history_matches': len(full),
                'championship_selected_matches': len(selected),
                'competitions': sorted(set(full.competition)), 'screenshots': screenshots}
    case('Aston Villa cross-league identity and filters', 'One stable club profile has actual EPL and Championship results; disabling full history applies league and season filters.', aston_villa)

    def nba_navigation():
        select('NBA', 'boxscorelab', 'athlete')
        identity = 'nba:2544'
        seasons = window.archive.query('NBA', competitor_id=identity, provider='boxscorelab', limit=None).season.astype(str).unique()
        actual = []
        for season in ('2023-24', '2024-25', '2025-26'):
            assert season in seasons, 'Source does not contain LeBron James in ' + season
            select('NBA', 'boxscorelab', 'athlete', season, query='LeBron James')
            open_identity(identity)
            assert set(window.profile_frame.season.astype(str)) == {season}
            assert window.history_table.model().rowCount() == 1
            actual.append({'season': season, 'records': len(window.profile_frame)})
        return {'stable_id': identity, 'seasons': actual,
                'screenshot': capture('05-nba-real-player-season')}
    case('NBA real player search and recent season switching', 'LeBron James has actual selected 2023-24, 2024-25 and 2025-26 rows, with a season history table.', nba_navigation)

    def historical_f1():
        select('F1', 'f1db', 'athlete', query='Fangio')
        results = window.archive.search('F1', 'Fangio', provider='f1db')
        assert not results.empty
        identity = str(results.iloc[0].competitor_id)
        open_identity(identity)
        frame = window.profile_frame
        assert pd.to_numeric(frame.season).min() <= 1951
        assert not window.profile_chart.plotted_data.empty
        return {'stable_id': identity, 'observed_records': len(frame),
                'seasons': sorted(frame.season.astype(str).unique()),
                'screenshot': capture('06-historical-f1-driver')}
    case('Historical F1 driver profile', 'Source-backed early championship driver history opens with an actual chart.', historical_f1)

    def dashboard(sport, provider, entity, season):
        select(sport, provider, entity, season)
        window.navigate('dashboard')
        settle()
        assert len(window.dash_visuals) == 6
        plotted = []
        for heading, chart in window.dash_visuals:
            chart.canvas.draw()
            assert not chart.plotted_data.empty, heading.text() + ': ' + chart.explanation.text()
            plotted.append({'title': heading.text(), 'plotted_rows': len(chart.plotted_data),
                            'explanation': chart.explanation.text()})
        if sport == 'NBA':
            career = window.dash_visuals[0][1].plotted_data
            distribution = window.dash_visuals[2][1].plotted_data
            radar = window.dash_visuals[3][1].plotted_data
            scatter = window.dash_visuals[4][1].plotted_data
            assert career.season.astype(str).nunique() > 1, 'NBA career panel collapsed to one selected-season dot.'
            assert distribution.competitor_id.nunique() > 6, 'NBA distribution omitted most of the selected cohort.'
            assert scatter.competitor_id.nunique() > 6, 'NBA scatter omitted most of the selected cohort.'
            assert str(window.dashboard_focus.currentData()) in set(radar.competitor_id.astype(str)), 'Selected focus is absent from the radar context.'
        window.resize(1440, 960)
        settle()
        screenshots = [capture('07-' + sport.lower() + '-dashboard'),
                       capture('08-' + sport.lower() + '-six-chart-studio', full_page=True)]
        window.resize(1040, 760)
        settle()
        screenshots.append(capture('09-' + sport.lower() + '-compact'))
        window.resize(1440, 960)
        return {'selection_records': len(window.frame), 'source': provider,
                'entity_type': entity, 'season': season, 'six_components': plotted,
                'screenshots': screenshots}
    for sport, provider, entity, season in (
            ('Soccer', 'openfootball', 'team', '2025-26'),
            ('NBA', 'boxscorelab', 'athlete', '2024-25'),
            ('F1', 'f1db', 'athlete', '2024')):
        case(sport + ' simultaneous dashboard and compact view', 'Six distinct panels have recorded chart data, exported as real full-window and full-page screenshots.',
             lambda s=sport, p=provider, e=entity, y=season: dashboard(s, p, e, y))

    if copied_afl:
        def afl_dashboard():
            window.sport.setCurrentText('AFL')
            window._change_sport()
            frame = window.archive.query('AFL', entity_type='team', provider='squiggle', limit=1)
            assert not frame.empty, 'No Squiggle club match records were available.'
            season = str(frame.iloc[0].season)
            result = dashboard('AFL', 'squiggle', 'team', season)
            result['qa_only_rows_copied'] = copied_afl
            result['scope'] = 'Existing locally downloaded results copied into isolated QA; not bundled in a fresh installer.'
            return result
        case('AFL recorded club dashboard and compact view', 'Real club scores, goals, behinds and margins produce six actual charts; player-only fields are not invented.', afl_dashboard)
    else:
        cases.append({'case': 'AFL recorded club dashboard and compact view', 'expected': 'Actual locally downloaded AFL club results.',
                      'actual': local_afl_issue or 'Run --with-local-afl after downloading a permitted AFL archive.',
                      'dataset': 'ACTUAL SOURCE-BACKED RECORDS', 'status': 'not_available', 'required': False})

    def comparison():
        select('NBA', 'boxscorelab', 'athlete', '2024-25')
        for combo, identity in ((window.compare_a, 'nba:2544'), (window.compare_b, 'nba:201939')):
            index = combo.findData(identity)
            assert index >= 0, identity + ' is absent from this source season.'
            combo.setCurrentIndex(index)
        window.navigate('compare')
        assert 'Compatible' in window.comparison_note.text()
        assert window.comparison_stats.model().rowCount() >= 5
        for chart in (window.compare_trend, window.compare_radar, window.compare_recent, window.compare_ratings):
            assert not chart.plotted_data.empty
        screenshots = [capture('10-nba-head-to-head'), capture('11-nba-head-to-head-full', full_page=True)]
        return {'competitors': ['nba:2544', 'nba:201939'],
                'summary_rows': window.comparison_stats.model().rowCount(), 'screenshots': screenshots}
    case('Recorded head-to-head comparison', 'Two NBA players under one source and season show calculated differences plus simultaneous trend, radar, form and rating charts.', comparison)

    def constructor_comparison():
        select('F1', 'f1db', 'athlete', '2024')
        window.compare_kind.setCurrentIndex(1)
        window.navigate('compare')
        assert window.compare_a.count() >= 2
        window.compare_a.setCurrentIndex(0)
        window.compare_b.setCurrentIndex(1)
        window._load_comparison()
        data = window.comparison_frame
        assert set(data.entity_type) == {'constructor'}
        assert data.competitor_id.nunique() == 2
        measured = {}
        for identity, group in data.groupby('team_id'):
            raw = window.archive.query('F1', provider='f1db', season='2024', limit=None)
            raw = raw.loc[raw.team_id.eq(identity)]
            assert len(raw) == len(group)
            assert float(raw.points.sum()) == float(group.points.sum())
            measured[str(identity)] = {'driver_starts': len(group), 'observed_driver_points': float(group.points.sum())}
        assert 'official constructor standings' in window.comparison_note.text()
        assert window.comparison_stats.model().rowCount() >= 5
        assert not window.compare_trend.plotted_data.empty
        screenshot = capture('14-f1-constructor-comparison')
        full = capture('15-f1-constructor-comparison-full', full_page=True)
        window.compare_kind.setCurrentIndex(0)
        return {'constructors': measured, 'screenshots': [screenshot, full],
                'scope': 'Sum of actual driver points, not an asserted official constructor championship table.'}
    case('F1 recorded constructor comparison', 'Two actual constructor IDs aggregate their recorded driver starts, matching stored point totals with explicit limitations.', constructor_comparison)

    def rating_tab():
        select('Soccer', 'openfootball', 'team', '2025-26', 'English Premier League', 'Aston Villa')
        open_identity(club_id('Aston Villa FC', 'en.1'))
        panel = window.profile_analysis
        window.profile_tabs.setCurrentIndex(window.profile_tabs.indexOf(panel))
        panel.explain_button.setChecked(True)
        settle()
        assert panel.summary['score'] is not None
        assert panel.observations
        assert not panel.chart.plotted_data.empty
        assert panel.formula.isVisible()
        assert all(item.get('period') and item.get('source') for item in panel.observations)
        return {'rating': panel.summary, 'insights': panel.observations,
                'screenshots': [capture('12-experimental-rating-and-insights'),
                                capture('12-experimental-rating-and-insights-full', full_page=True)]}
    case('Explainable experimental rating and deterministic insights', 'A real club profile exposes its formula, recorded trend, score limitations and source/period-qualified factual insights.', rating_tab)

    def portraits():
        observed = []
        for identity, name, sport in (('nba:2544', 'LeBron James', 'NBA'),
                                     ('f1db:lewis-hamilton', 'Lewis Hamilton', 'F1'),
                                     ('statsbomb:5503', 'Lionel Messi', 'Soccer')):
            portrait = PortraitWidget(size=168)
            portrait.set_athlete(identity, name, sport, online=False)
            settle(lambda: not portrait._jobs)
            assert not portrait.pixmap.isNull(), name + ': bundled licensed image did not decode.'
            assert portrait.metadata.get('competitor_id') == identity
            assert portrait.metadata.get('artist') and portrait.metadata.get('license')
            assert portrait.attribution_text
            observed.append({'identity': identity, 'license': portrait.metadata['license'],
                             'artist': portrait.metadata['artist'], 'source_url': portrait.metadata['source_url']})
            portrait.close()
        return observed
    case('Real licensed portraits offline', 'Three real bundled player/driver portraits decode with matching stable identities and attribution.', portraits)

    def guard():
        controlled = pd.DataFrame([
            {'competitor_id': 'qa:a', 'entity_type': 'athlete', 'provider': 'CONTROLLED QA', 'points': 12},
            {'competitor_id': 'qa:b', 'entity_type': 'team', 'provider': 'CONTROLLED QA', 'points': 15},
        ])
        window.comparison_frame = controlled
        window._plot_comparison()
        assert 'different units' in window.comparison_note.text()
        assert window.comparison_stats.model().rowCount() == 0
        assert window.compare_trend.plotted_data.empty
        return {'state': window.comparison_note.text()}
    case('Incompatible comparison guard', 'Athlete and club units are rejected and previous comparison charts are cleared.', guard, fixture=True)

    def import_flow():
        window.sport.setCurrentText('NBA')
        source = runtime / 'CONTROLLED-QA-import.csv'
        fixture = pd.DataFrame([
            {'date': '2024-01-01', 'season': '2024', 'competitor': 'CONTROLLED QA EXAMPLE', 'team': 'QA', 'points': 20},
            {'date': '2024-01-01', 'season': '2024', 'competitor': 'CONTROLLED QA EXAMPLE', 'team': 'QA', 'points': 20},
            {'date': 'invalid-date', 'season': '2024', 'competitor': 'CONTROLLED INVALID DATE', 'team': 'QA', 'points': 20},
            {'date': '2024-01-01', 'season': '2024', 'competitor': 'CONTROLLED INVALID SCORE', 'team': 'QA', 'points': -1},
        ])
        fixture.to_csv(source, index=False)
        with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(source), '')):
            window._import_file()
            settle(lambda: 'import' not in window.jobs)
            first = window.archive.setting('last_import_report')
            assert first['inserted_rows'] == 1 and first['duplicates_removed'] == 1 and first['invalid_rows_removed'] == 2
            window._import_file()
            settle(lambda: 'import' not in window.jobs)
            repeated = window.archive.setting('last_import_report')
            assert repeated['unchanged_rows'] == 1 and repeated['inserted_rows'] == 0
        destination = output / 'controlled-import-quality-report.json'
        with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(destination), '')):
            window._export_quality_report()
        assert destination.is_file()
        assert window.route == 'explorer'
        assert window._selected_provider() == repeated['source'], 'The records view did not switch to the newly imported dataset.'
        assert set(window.raw_table.model().frame.provider) == {repeated['source']}
        return {'first_counts': {key: first[key] for key in ('input_rows', 'valid_rows', 'duplicates_removed', 'invalid_rows_removed', 'inserted_rows')},
                'repeat_unchanged_rows': repeated['unchanged_rows'],
                'report': destination.name, 'screenshot': capture('13-data-quality-controlled-fixture')}
    case('Native import, quality report, persistence and export', 'The actual UI background worker imports valid rows, reports duplicate/bad-date/negative-score rows, preserves missing metrics, and detects unchanged repeat imports.', import_flow, fixture=True)

    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'platform': platform.system() + ' ' + platform.release(),
        'python': platform.python_version(), 'qt': qVersion(),
        'native_qt': True, 'qt_platform': app.platformName(), 'offline': True,
        'production_database_modified': False,
        'actual_afl_rows_copied_into_qa': copied_afl,
        'cases': cases, 'unhandled_errors': unhandled,
        'success': not unhandled and all(item['status'] == 'pass' for item in cases if item.get('required')),
        'limitations': [
            'Screenshots are actual Qt widget renders; they do not prove manual interactive installation or macOS execution.',
            'AFL source-backed screenshots, when present, use a separate previously downloaded local archive. AFL is on demand in a fresh install.',
            'The bundled NBA starter covers recent seasons only. Older NBA seasons require a successful permitted provider download and are not claimed by this report.',
            'CSV/JSON/XLSX format and calculation unit tests are reported separately by pytest.',
            'Visual screenshots require human inspection; nonempty chart data alone is not a visual-quality verdict.',
        ],
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')
    lines = ['# Actual native desktop acceptance evidence', '',
             f"Generated {report['generated_at']}; {report['platform']}; Python {report['python']}; Qt {report['qt']} ({report['qt_platform']}).", '',
             '| Test case | Expected | Actual result | Status |', '|---|---|---|---|']
    for item in cases:
        actual = json.dumps(item['actual'], ensure_ascii=False, default=str)
        lines.append('| ' + ' | '.join(str(value).replace('|', '\\|').replace('\n', ' ') for value in (
            item['case'], item['expected'], actual, item['status'].upper())) + ' |')
    lines += ['', '## Limits', '', *['- ' + value for value in report['limitations']], '']
    (output / 'RESULTS.md').write_text('\n'.join(lines), encoding='utf-8')
    window.close()
    window.pool.waitForDone(10000)
    app.processEvents()
    sys.excepthook = previous_hook
    print('Acceptance success:', report['success'], flush=True)
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
