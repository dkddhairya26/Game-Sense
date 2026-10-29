"""Normalize permitted user datasets while retaining their source columns.

Ported from the 0.5 importer. Date-free rows carry an explicit season-grain
marker; that date is a sort key, never a claimed match. Ambiguous headers are
rejected before any data is changed.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
from numbers import Number
from pathlib import Path
import re

import numpy as np
import pandas as pd


ALIASES = {
    'player':'competitor', 'player_name':'competitor', 'playername':'competitor',
    'athlete':'competitor', 'driver':'competitor', 'driver_name':'competitor',
    'name':'competitor', 'footballer':'competitor',
    'club':'team', 'club_name':'team', 'team_name':'team', 'squad':'team',
    'constructor':'team', 'constructor_name':'team',
    'year':'season', 'season_year':'season', 'seasonyear':'season',
    'match_date':'date', 'game_date':'date', 'race_date':'date',
    'matchdate':'date', 'gamedate':'date',
    'pts':'points', 'reb':'rebounds', 'ast':'assists', 'stl':'steals',
    'blk':'blocks', 'tov':'turnovers', 'gp':'games_played', 'min':'minutes', 'mp':'minutes',
    'fgm':'field_goals_made', 'fg':'field_goals_made', 'fga':'field_goal_attempts',
    'field_goals_attempted':'field_goal_attempts', 'fg_pct':'field_goal_pct',
    'field_goal_percentage':'field_goal_pct',
    'fg3m':'three_point_makes', '3p':'three_point_makes', 'three_point_made':'three_point_makes',
    'fg3a':'three_point_attempts', '3pa':'three_point_attempts', 'three_point_attempted':'three_point_attempts',
    'fg3_pct':'three_point_pct', '3p_pct':'three_point_pct', 'three_point_percentage':'three_point_pct',
    'ftm':'free_throws_made', 'ft':'free_throws_made', 'fta':'free_throw_attempts',
    'free_throws_attempted':'free_throw_attempts', 'ft_pct':'free_throw_pct',
    'free_throw_percentage':'free_throw_pct',
    'kick':'kicks', 'k':'kicks', 'hb':'handballs', 'd':'disposals',
    'm':'marks', 't':'tackles', 'g':'goals', 'cl':'clearances',
    'clangers_total':'clangers', 'finish':'finish_position',
    'position_finish':'finish_position', 'grid':'grid_position',
    'start_position':'grid_position',
}
AFL_ONLY = {'k','hb','d','m','t','g','cl'}


def prepare_import(df: pd.DataFrame, sport: str) -> tuple[pd.DataFrame,list[str]]:
    """Return normalized data and notes; never mutate the caller's dataframe.

    A canonical column takes precedence over an alias, whose original column
    is retained. Two aliases without a canonical field require the user to
    choose one rather than silently select or overwrite a column.
    """
    if sport not in {'Soccer','NBA','AFL','F1'}:
        raise ValueError('Unknown sport: '+str(sport))
    out=df.copy()
    columns=[re.sub(r'[^a-z0-9]+','_',str(c).strip().lower().replace('%',' pct ')).strip('_') for c in out.columns]
    if any(not c for c in columns):
        raise ValueError('Every imported column needs a non-empty name.')
    duplicates=sorted({c for c in columns if columns.count(c)>1})
    if duplicates:
        raise ValueError('Duplicate column names after normalization: '+', '.join(duplicates)+'. Rename these columns before importing.')
    out.columns=columns
    notes=[]
    candidates=defaultdict(list)
    for column in columns:
        if sport!='AFL' and column in AFL_ONLY:
            continue
        target=ALIASES.get(column)
        if target and target not in columns:
            candidates[target].append(column)
    for target,sources in candidates.items():
        if len(sources)>1:
            raise ValueError('Ambiguous '+target+' columns: '+', '.join(sources)+'. Rename the chosen column to '+target+'.')
    mapping={sources[0]:target for target,sources in candidates.items()}
    if mapping:
        out.rename(columns=mapping,inplace=True)
        notes.append('Mapped headers: '+', '.join(f'{old} → {new}' for old,new in mapping.items()))
    if 'competitor' not in out:
        raise ValueError("No competitor/player/driver name column was found. Rename it to 'competitor'.")
    if 'season' not in out:
        raise ValueError("No season/year column was found. Rename it to 'season'.")
    if 'team' not in out:
        out['team']='Team not provided'
        notes.append("Team/club column absent; shown as 'Team not provided'.")
    if 'date' not in out:
        years=out['season'].astype(str).str.extract(r'((?:18|19|20|21)\d{2})')[0]
        out['date']=pd.to_datetime(years+'-01-01',errors='coerce')
        out['date_is_marker']=True
        out['date_precision']='season'
        descriptions=out.get('record_type',pd.Series('',index=out.index)).fillna('').astype(str)
        averages=descriptions.str.contains(r'per[ -]?game.*averag|season.*averag',case=False,regex=True)
        inferred=pd.Series('season_total',index=out.index).where(~averages,'season_average')
        if 'record_kind' in out:
            missing=out['record_kind'].isna() | out['record_kind'].astype(str).str.strip().eq('')
            out.loc[missing,'record_kind']=inferred[missing]
        else:
            out['record_kind']=inferred
        if 'record_type' not in out:
            out['record_type']='player/team season aggregate (NO MATCH DATE)'
        notes.append('No actual match date was supplied. Used Jan 1 of the season as a SORTING MARKER ONLY, not a claimed game date. Season values are treated as totals unless explicitly labelled season/per-game averages.')
    if 'record_type' not in out:
        out['record_type']='user-imported record'
    if 'record_kind' not in out:
        out['record_kind']='event'
    if 'date_precision' not in out:
        out['date_precision']='day'
    return out,notes


# Only fields with a documented numeric meaning are converted. Arbitrary source
# columns remain intact: converting every object column would destroy team names,
# event identifiers and nested shot arrays needed for later analysis.
COUNT_FIELDS = {
    'goals', 'goals_against', 'assists', 'shots', 'shots_on_target', 'passes',
    'passes_completed', 'tackles', 'interceptions', 'clearances', 'starts',
    'yellow_cards', 'red_cards', 'appearances', 'games', 'games_played',
    'points_against', 'rebounds', 'offensive_rebounds', 'defensive_rebounds',
    'steals', 'blocks', 'turnovers', 'field_goals_made', 'field_goal_attempts',
    'three_point_makes', 'three_point_attempts', 'free_throws_made',
    'free_throw_attempts', 'disposals', 'kicks', 'handballs', 'marks', 'behinds',
    'laps', 'pit_stops', 'minutes', 'wins', 'draws', 'losses', 'podiums',
}
FRACTION_FIELDS = {'field_goal_pct', 'three_point_pct', 'free_throw_pct',
                   'pass_accuracy', 'shooting_accuracy'}
NUMERIC_FIELDS = COUNT_FIELDS | FRACTION_FIELDS | {
    'points', 'finish_position', 'grid_position', 'qualifying_position',
    'championship_points', 'fastest_lap', 'q1_ms', 'q2_ms', 'q3_ms',
    'xg', 'xa', 'margin', 'goal_difference', 'scoring_percentage', 'table_points',
    'effective_field_goal_pct', 'true_shooting_pct',
}


def read_import_file(path) -> pd.DataFrame:
    """Read a supported local dataset without changing the source file.

    JSON accepts a records list, a column-oriented pandas object, or a records
    list wrapped in ``records``/``data``. Explicit wrappers are common in exports;
    unsupported nested API responses fail clearly instead of becoming fake rows.
    XLSX uses openpyxl through pandas; no executable spreadsheet macros are run.
    """
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == '.csv':
        return pd.read_csv(source, encoding='utf-8-sig')
    if suffix == '.xlsx':
        return pd.read_excel(source, engine='openpyxl')
    if suffix == '.json':
        with source.open('r', encoding='utf-8-sig') as stream:
            payload = json.load(stream)
        if isinstance(payload, dict):
            wrappers = [key for key in ('records', 'data') if key in payload]
            if wrappers:
                payload = payload[wrappers[0]]
        if not isinstance(payload, (list, dict)):
            raise ValueError('JSON must contain a records list or a column-oriented object.')
        if isinstance(payload, list) and any(not isinstance(row, dict) for row in payload):
            raise ValueError('Each JSON record must be an object with named columns.')
        try:
            return pd.DataFrame(payload)
        except (TypeError, ValueError) as exc:
            raise ValueError('JSON does not contain a rectangular sporting dataset.') from exc
    raise ValueError('Supported import formats are CSV, JSON and XLSX.')


def _comparison_keys(frame: pd.DataFrame) -> pd.DataFrame:
    """Make nested values hashable without removing the original observations."""
    keys = frame.copy()
    for column in keys.select_dtypes(include=['object']).columns:
        keys[column] = keys[column].map(
            lambda value: json.dumps(value, sort_keys=True, default=str)
            if isinstance(value, (list, dict)) else value)
    return keys


def validate_import(raw: pd.DataFrame, sport: str) -> tuple[pd.DataFrame, dict]:
    """Normalize, validate and clean an import, returning auditable row counts.

    Validation is deliberately row-local: a bad date or impossible count rejects
    that row, while valid records still reach SQLite. Blank optional measurements
    remain missing. Malformed optional numbers become missing and are counted;
    negative count values, fractional probabilities outside [0,1], and made/attempt
    contradictions are rejected. F1 points may include a source penalty, so the
    universal nonnegative-score rule is restricted to Soccer, NBA and AFL.

    Rejection reason counts can overlap. The accounting identity is always
    input_rows = duplicates_removed + invalid_rows_removed + valid_rows.
    """
    from .analytics import clean_data

    if not isinstance(raw, pd.DataFrame):
        raise TypeError('Import data must be a pandas DataFrame.')
    prepared, notes = prepare_import(raw, sport)
    prepared = prepared.reset_index(drop=True)
    # Retain source row numbers in the report only, so provenance does not stop
    # otherwise identical rows being detected as duplicates.
    for key in ('competitor', 'season', 'team'):
        prepared[key] = prepared[key].astype('string').str.strip().replace('', pd.NA)
    numeric_conversions, malformed_numbers = {}, {}
    changed_rows = pd.Series(False, index=prepared.index)
    for key in prepared.columns:
        if key not in NUMERIC_FIELDS and not key.endswith(('_pg', '_per_game', '_per_90', '_per_36')):
            continue
        values = prepared[key]
        converted = pd.to_numeric(values, errors='coerce').replace([np.inf, -np.inf], np.nan)
        nonblank = values.notna() & values.astype('string').str.strip().ne('').fillna(False)
        malformed = nonblank & converted.isna()
        strings = values.map(lambda value: isinstance(value, str)) & converted.notna()
        numeric_conversions[key] = int(strings.sum())
        malformed_numbers[key] = int(malformed.sum())
        changed_rows |= strings | malformed
        prepared[key] = converted

    duplicate = _comparison_keys(prepared).duplicated(keep='first')
    candidates = prepared.loc[~duplicate].copy()
    dates = pd.to_datetime(candidates['date'], errors='coerce', utc=True, format='mixed')
    # pandas interprets bare numeric dates as nanoseconds since 1970. An Excel
    # serial or YYYYMMDD integer must not silently become a valid 1970 fixture.
    numeric_date = candidates['date'].map(lambda value: isinstance(value, Number))
    bad_date = dates.isna() | numeric_date
    bad_identity = (candidates['competitor'].isna() | candidates['season'].isna())
    reasons = {index: [] for index in candidates.index}
    for index in candidates.index[bad_date]:
        reasons[index].append('Invalid or missing date / season sorting marker')
    for index in candidates.index[bad_identity]:
        reasons[index].append('Missing competitor or season')

    # Two different observations with the same fallback event identity would
    # overwrite each other in SQLite. Keep the first and explicitly reject later
    # conflicts. Supply event_id for genuine same-day doubleheaders, or record_id
    # for a provider's own unambiguous row key. This is distinct from exact-row
    # duplicates, which were removed above.
    def identity_text(value):
        return '' if value is None or pd.isna(value) else str(value)

    invalid_score = pd.Series(False, index=candidates.index)
    score_fields = COUNT_FIELDS | ({'points'} if sport != 'F1' else set())
    for key in score_fields & set(candidates.columns):
        negative = candidates[key].notna() & candidates[key].lt(0)
        invalid_score |= negative
        for index in candidates.index[negative]:
            reasons[index].append(f'{key} cannot be negative')
    for key in FRACTION_FIELDS & set(candidates.columns):
        outside = candidates[key].notna() & ~candidates[key].between(0, 1)
        invalid_score |= outside
        for index in candidates.index[outside]:
            reasons[index].append(f'{key} must be a fraction from 0 to 1; convert percent values before import')
    pairs = [('field_goals_made', 'field_goal_attempts'),
             ('three_point_makes', 'three_point_attempts'),
             ('free_throws_made', 'free_throw_attempts'),
             ('passes_completed', 'passes'), ('shots_on_target', 'shots')]
    for made_key, attempts_key in pairs:
        if made_key not in candidates or attempts_key not in candidates:
            continue
        impossible = candidates[made_key].notna() & candidates[attempts_key].notna() & candidates[made_key].gt(candidates[attempts_key])
        invalid_score |= impossible
        for index in candidates.index[impossible]:
            reasons[index].append(f'{made_key} exceeds {attempts_key}')
    # Grid=0 is an actual pit-lane start; finishing position=0 is not a valid
    # classified place. Unknown/DNF positions should be blank, never zero-filled.
    for key in ('finish_position', 'qualifying_position'):
        if key in candidates:
            invalid = candidates[key].notna() & candidates[key].lt(1)
            invalid_score |= invalid
            for index in candidates.index[invalid]:
                reasons[index].append(f'{key} must be positive or missing')

    # Effective FG and true shooting measure scoring value, not a Bernoulli
    # success fraction: a made three on one FGA gives eFG=1.5, legitimately >1.
    for key in ('effective_field_goal_pct', 'true_shooting_pct'):
        if key in candidates:
            invalid = candidates[key].notna() & ~candidates[key].between(0, 1.5)
            invalid_score |= invalid
            for index in candidates.index[invalid]:
                reasons[index].append(f'{key} must be between 0 and 1.5')
    if 'grid_position' in candidates:
        invalid = candidates['grid_position'].notna() & candidates['grid_position'].lt(0)
        invalid_score |= invalid
        for index in candidates.index[invalid]:
            reasons[index].append('grid_position cannot be negative; 0 is a pit-lane start')

    seen_events, identity_conflict = set(), pd.Series(False, index=candidates.index)
    for index, row in candidates.iterrows():
        # An already rejected row must not reserve an identity and cause a later
        # valid correction in the same file to be discarded.
        if bad_date.loc[index] or bad_identity.loc[index] or invalid_score.loc[index]:
            continue
        explicit = identity_text(row.get('record_id'))
        if explicit:
            identity = ('record_id', explicit)
        else:
            athlete = identity_text(row.get('competitor_id')) or identity_text(row.get('competitor')).casefold()
            date = dates.loc[index].isoformat()
            identity = (athlete, identity_text(row.get('season')),
                        identity_text(row.get('team')), identity_text(row.get('event_id')), date)
        if identity in seen_events:
            identity_conflict.loc[index] = True
            reasons[index].append('Conflicting rows share one event identity; supply distinct event_id or record_id for separate games')
        seen_events.add(identity)

    rejected = bad_date | bad_identity | invalid_score | identity_conflict
    accepted = candidates.loc[~rejected].copy()
    clean, _ = clean_data(accepted, sport)
    missing = {key: int(clean[key].isna().sum()) for key in clean.columns
               if clean[key].isna().any()}
    report = {
        'schema_version': 1, 'sport': sport,
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'input_rows': len(raw), 'duplicates_removed': int(duplicate.sum()),
        'invalid_rows_removed': int(rejected.sum()), 'valid_rows': len(clean),
        'invalid_dates': int(bad_date.sum()),
        'missing_identity_rows': int(bad_identity.sum()),
        'conflicting_event_rows': int(identity_conflict.sum()),
        'invalid_scores': int(invalid_score.sum()),
        'cleaned_rows': int(changed_rows.loc[accepted.index].sum()),
        'missing_values': missing,
        'numeric_conversions': {key: count for key, count in numeric_conversions.items() if count},
        'malformed_numeric_values': {key: count for key, count in malformed_numbers.items() if count},
        'notes': notes,
        'rejected_examples': [{'source_row': int(index) + 2, 'reasons': reasons[index]}
                              for index in candidates.index[rejected][:20]],
        'limitations': [
            'Optional missing measurements remain missing and are excluded from calculations.',
            'Fraction fields such as field_goal_pct use 0–1; no ambiguous automatic rescaling.',
            'Matching names do not establish a verified identity. Supply stable competitor_id and event_id where available.',
            'A completed import is not evidence that a source covers a complete season.',
        ],
    }
    assert report['input_rows'] == report['duplicates_removed'] + report['invalid_rows_removed'] + report['valid_rows']
    return clean, report


def import_dataset(archive, sport: str, raw: pd.DataFrame, source='User import') -> dict:
    """Run the observable pipeline and persist its latest report for offline review."""
    clean, report = validate_import(raw, sport)
    counts = archive.import_frame_report(sport, clean, source)
    report.update(counts)
    report['source'] = str(source)
    report['stages'] = ['Collect', 'Validate', 'Clean', 'Process', 'Calculate', 'Analyse', 'Visualise']
    report['notes'].append('The accepted records are stored locally. Analysis and charts use the selected sport, competition and season filters.')
    archive.set_setting('last_import_report', report)
    return report


def export_quality_report(report: dict, path) -> Path:
    """Write a readable JSON evidence artifact without exporting local credentials."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    return destination
