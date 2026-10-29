"""Controlled, hand-checkable evidence for the complete local import pipeline.

These are generated test fixtures, not historical sports statistics. They verify
row accounting, missing-value semantics and persistence without network access.
"""
import json

import pandas as pd
import pytest

from gamesense.archive import Archive, _seed_coverage
from gamesense.importers import (
    export_quality_report, import_dataset, read_import_file, validate_import,
)


def sample(**extra):
    row = {'Player': 'Example A', 'Club': 'Example Club', 'Year': '2024-25',
           'Match Date': '2024-11-01', 'PTS': '20', 'REB': None,
           'FGM': '8', 'FGA': '15', 'FG_PCT': '0.5333333333'}
    row.update(extra)
    return row


def test_partial_validation_has_exact_row_accounting_and_preserves_missing():
    raw = pd.DataFrame([
        sample(), sample(),  # one exact duplicate
        sample(Player='Bad date', **{'Match Date': 'impossible'}),
        sample(Player='Negative score', PTS=-1),
        sample(Player='Impossible attempts', FGM=16),
        sample(Player='Missing optional', PTS=None, FGM=None, FGA=None, FG_PCT=None),
    ])
    clean, report = validate_import(raw, 'NBA')
    assert (report['input_rows'], report['duplicates_removed'],
            report['invalid_rows_removed'], report['valid_rows']) == (6, 1, 3, 2)
    assert report['invalid_dates'] == 1
    assert report['invalid_scores'] == 2
    assert report['numeric_conversions']['points'] == 4
    assert report['missing_values']['rebounds'] == 2
    optional = clean.loc[clean.competitor.eq('Missing optional')].iloc[0]
    assert pd.isna(optional.points)
    assert pd.isna(optional.rating)
    assert len(report['rejected_examples']) == 3
    # The caller's source data remains unchanged and uses original headers.
    assert raw.loc[0, 'PTS'] == '20'
    assert 'competitor' not in raw


@pytest.mark.parametrize('suffix', ['.csv', '.json', '.xlsx'])
def test_actual_supported_files_validate_persist_and_export(tmp_path, suffix):
    path = tmp_path / ('records' + suffix)
    raw = pd.DataFrame([sample()])
    if suffix == '.csv':
        raw.to_csv(path, index=False)
    elif suffix == '.json':
        path.write_text(json.dumps({'records': raw.to_dict('records')}), encoding='utf-8')
    else:
        raw.to_excel(path, index=False, engine='openpyxl')
    archive = Archive(tmp_path / 'archive.sqlite3')
    report = import_dataset(archive, 'NBA', read_import_file(path), 'User import: ' + path.name)
    assert report['inserted_rows'] == 1
    assert report['updated_rows'] == report['unchanged_rows'] == 0
    assert archive.count('NBA') == 1
    record = archive.query('NBA').iloc[0]
    assert record.points == 20
    assert record.provider == 'User import: ' + path.name
    assert record.import_source == record.provider
    assert archive.coverage('NBA')[0]['status'] == 'imported'
    assert not archive.completed(record.provider, '2024-25', 'NBA')
    destination = export_quality_report(report, tmp_path / 'quality.json')
    exported = json.loads(destination.read_text(encoding='utf-8'))
    assert exported == report
    assert archive.setting('last_import_report') == report
    # Persistence survives a fresh connection / application session.
    assert Archive(archive.path).query('NBA').iloc[0].points == 20


def test_repeat_import_reports_unchanged_and_correction_updates_only_that_event(tmp_path):
    archive = Archive(tmp_path / 'archive.sqlite3')
    raw = pd.DataFrame([sample(), sample(Player='Example B')])
    first = import_dataset(archive, 'NBA', raw, 'controlled.csv')
    second = import_dataset(archive, 'NBA', raw, 'controlled.csv')
    assert first['inserted_rows'] == 2
    assert second['inserted_rows'] == second['updated_rows'] == 0
    assert second['unchanged_rows'] == 2
    raw.loc[0, 'PTS'] = '21'
    corrected = import_dataset(archive, 'NBA', raw, 'controlled.csv')
    assert corrected['updated_rows'] == 1
    assert corrected['unchanged_rows'] == 1
    assert archive.count('NBA') == 2
    assert archive.query('NBA')['points'].sum() == 41


def test_fraction_units_and_malformed_numeric_values_are_explained():
    raw = pd.DataFrame([sample(FG_PCT=53.3), sample(Player='Malformed rebound', REB='not measured')])
    clean, report = validate_import(raw, 'NBA')
    assert len(clean) == 1
    assert report['invalid_scores'] == 1
    assert report['malformed_numeric_values'] == {'rebounds': 1}
    assert pd.isna(clean.iloc[0].rebounds)
    assert 'fraction from 0 to 1' in report['rejected_examples'][0]['reasons'][0]


def test_all_invalid_file_reports_rejections_without_database_mutation(tmp_path):
    archive = Archive(tmp_path / 'archive.sqlite3')
    report = import_dataset(archive, 'NBA', pd.DataFrame([sample(PTS=-20)]), 'bad.csv')
    assert report['valid_rows'] == 0
    assert report['invalid_rows_removed'] == 1
    assert report['inserted_rows'] == report['updated_rows'] == 0
    assert archive.count('NBA') == 0


def test_season_marker_is_explicit_and_not_a_claimed_match_date():
    raw = pd.DataFrame([{'Player': 'Season example', 'Year': '1995-96', 'PTS': '100', 'GP': 10}])
    clean, report = validate_import(raw, 'NBA')
    assert clean.iloc[0].date == pd.Timestamp('1995-01-01')
    assert clean.iloc[0].date_precision == 'season'
    assert clean.iloc[0].record_kind == 'season_total'
    assert any('SORTING MARKER' in note for note in report['notes'])


def test_f1_pit_lane_zero_is_valid_but_zero_finish_is_rejected():
    raw = pd.DataFrame([
        {'Driver': 'Example A', 'Year': 2020, 'date': '2020-01-01', 'grid': 0, 'finish': 5},
        {'Driver': 'Example B', 'Year': 2020, 'date': '2020-01-01', 'grid': 4, 'finish': 0},
    ])
    clean, report = validate_import(raw, 'F1')
    assert len(clean) == 1
    assert clean.iloc[0].grid_position == 0
    assert report['invalid_scores'] == 1


def test_afl_negative_goals_rejected_and_scoring_percent_can_exceed_100():
    raw = pd.DataFrame([
        {'Player': 'Example A', 'Year': 2020, 'G': 2, 'points': 80, 'scoring_percentage': 140},
        {'Player': 'Example B', 'Year': 2020, 'G': -1, 'points': 60},
    ])
    clean, report = validate_import(raw, 'AFL')
    assert len(clean) == 1
    assert clean.iloc[0].scoring_percentage == 140
    assert report['invalid_scores'] == 1


def test_json_error_and_unknown_file_type_are_clear(tmp_path):
    path = tmp_path / 'invalid.json'
    path.write_text('[1, 2]', encoding='utf-8')
    with pytest.raises(ValueError, match='Each JSON record'):
        read_import_file(path)
    with pytest.raises(ValueError, match='Supported import formats'):
        read_import_file(tmp_path / 'spreadsheet.xlsm')


def test_actual_archive_facets_are_derived_from_rows(tmp_path):
    archive = Archive(tmp_path / 'archive.sqlite3')
    raw = pd.DataFrame([sample()])
    import_dataset(archive, 'NBA', raw, 'test.csv')
    assert archive.sources('NBA') == ['test.csv']
    assert archive.entity_types('NBA') == ['athlete']
    assert archive.sources('F1') == []


def test_conflicting_unkeyed_games_do_not_silently_overwrite_and_distinct_ids_work():
    raw = pd.DataFrame([sample(PTS=-1), sample(), sample(PTS=21)])
    clean, report = validate_import(raw, 'NBA')
    assert len(clean) == 1
    assert clean.iloc[0].points == 20
    assert report['invalid_scores'] == 1
    assert report['conflicting_event_rows'] == 1
    assert report['invalid_rows_removed'] == 2
    keyed = pd.DataFrame([sample(event_id='morning'), sample(PTS=21, event_id='evening')])
    clean, report = validate_import(keyed, 'NBA')
    assert len(clean) == 2
    assert report['conflicting_event_rows'] == 0


def test_effective_field_goal_percentage_is_allowed_above_one():
    # A made three from one FGA has effective FG=(1+.5*1)/1=1.5.
    raw = pd.DataFrame([sample(FGM=1, FGA=1, effective_field_goal_pct=1.5,
                               true_shooting_pct=1.5)])
    clean, report = validate_import(raw, 'NBA')
    assert len(clean) == 1
    assert report['invalid_scores'] == 0
    assert clean.iloc[0].effective_field_goal_pct == 1.5


def test_search_source_and_entity_filters_do_not_mix_populations(tmp_path):
    archive = Archive(tmp_path / 'archive.sqlite3')
    import_dataset(archive, 'NBA', pd.DataFrame([sample()]), 'first.csv')
    import_dataset(archive, 'NBA', pd.DataFrame([sample(Player='Other')]), 'second.csv')
    results = archive.search('NBA', provider='first.csv', entity_type='athlete')
    assert results.competitor.tolist() == ['Example A']
    assert archive.search('NBA', provider='first.csv', entity_type='team').empty


def test_ambiguous_numeric_dates_are_not_read_as_1970_nanoseconds():
    raw = pd.DataFrame([sample(**{'Match Date': 20241101}),
                        sample(Player='Excel serial', **{'Match Date': 45597})])
    clean, report = validate_import(raw, 'NBA')
    assert clean.empty
    assert report['invalid_dates'] == report['invalid_rows_removed'] == 2


def test_bundled_snapshot_completion_uses_capture_date_not_time_passing():
    captured = '2026-10-28T04:02:00+00:00'
    assert _seed_coverage({'provider': 'boxscorelab', 'sport': 'NBA',
                           'season': '2026-27', 'fetched_at': captured})[0] == 'ongoing_partial'
    assert _seed_coverage({'provider': 'boxscorelab', 'sport': 'NBA',
                           'season': '2025-26', 'fetched_at': captured})[0] == 'complete'
    assert _seed_coverage({'provider': 'f1db', 'sport': 'F1',
                           'season': '2026', 'fetched_at': captured})[0] == 'ongoing_partial'
    assert _seed_coverage({'provider': 'f1db', 'sport': 'F1',
                           'season': '2025', 'fetched_at': captured})[0] == 'complete'
    assert _seed_coverage({'provider': 'f1db', 'sport': 'F1', 'season': '2025'})[0] == 'partial'


def test_existing_completed_inseason_seed_labels_are_repaired_without_record_changes(tmp_path):
    archive = Archive(tmp_path / 'archive.sqlite3')
    row = {'sport': 'NBA', 'provider': 'boxscorelab', 'season': '2026-27',
           'date': '2027-06-30', 'competitor_id': 'qa:1', 'competitor': 'CONTROLLED',
           'team': 'QA', 'points': 20, 'fetched_at': '2026-10-28T04:02:00+00:00'}
    archive.upsert([row])
    archive.mark('boxscorelab', 'NBA', '2026-27', 'complete')
    archive._repair_bundled_coverage()
    assert archive.coverage('NBA')[0]['status'] == 'ongoing_partial'
    assert archive.query('NBA').iloc[0].points == 20
    assert archive.count('NBA') == 1


def test_search_display_metadata_belongs_to_selected_season_source_and_entity(tmp_path):
    archive = Archive(tmp_path / 'archive.sqlite3')
    for provider, season, name, team, entity in (
            ('first', '2024-25', 'Recorded 2024 Name', 'LAL', 'athlete'),
            ('first', '2026-27', 'Later Source Name', 'PHI', 'athlete'),
            ('second', '2024-25', 'Other Provider Name', 'BOS', 'athlete'),
            ('third', '2024-25', 'Club Identity', 'CLUB', 'team')):
        archive.upsert([{'provider': provider, 'sport': 'NBA', 'season': season,
                         'date': season[:4] + '-12-01', 'competitor_id': 'nba:controlled',
                         'competitor': name, 'team': team, 'entity_type': entity}])
    selected = archive.search('NBA', provider='first', season='2024-25', entity_type='athlete')
    assert len(selected) == 1
    assert selected.iloc[0].competitor == 'Recorded 2024 Name'
    assert selected.iloc[0].team == 'LAL'
    assert selected.iloc[0].records == 1
    assert selected.iloc[0].first_season == selected.iloc[0].last_season == '2024-25'
    second = archive.search('NBA', provider='second', season='2024-25', entity_type='athlete')
    assert second.iloc[0].team == 'BOS'


def test_query_exposes_incomplete_snapshot_status_without_overwriting_source_payload(tmp_path):
    archive = Archive(tmp_path / 'archive.sqlite3')
    row = {'sport': 'NBA', 'provider': 'boxscorelab', 'season': '2026-27',
           'date': '2027-06-30', 'competitor_id': 'qa:1', 'competitor': 'CONTROLLED',
           'team': 'QA', 'points': 20, 'season_status': 'source supplied label'}
    archive.upsert([row])
    archive.mark('boxscorelab', 'NBA', '2026-27', 'ongoing_partial')
    observed = archive.query('NBA').iloc[0]
    assert observed.archive_status == 'ongoing_partial'
    assert observed.season_status == 'ongoing_partial'
    assert observed.source_season_status == 'source supplied label'
    with archive.connect() as con:
        payload = json.loads(con.execute('SELECT payload FROM records').fetchone()[0])
    assert payload['season_status'] == 'source supplied label'
    assert 'archive_status' not in payload
