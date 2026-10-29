"""Sport-specific data validation and analytics for GameSense.

Design: raw records are cleaned once, then all UI views reuse the same calculations.
The scoring formulas are illustrative indicators, not official sport rankings.
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd

SPORTS = {
    'Soccer': {'metrics': ['goals', 'assists', 'shots', 'passes', 'tackles']},
    'NBA': {'metrics': ['points', 'rebounds', 'assists', 'steals', 'blocks']},
    'AFL': {'metrics': ['disposals', 'marks', 'tackles', 'goals', 'clearances']},
    'F1': {'metrics': ['points', 'finish_position', 'grid_position', 'laps', 'fastest_lap']},
}
REQUIRED = ['date', 'season', 'competitor', 'team']

def clean_data(df: pd.DataFrame, sport: str) -> tuple[pd.DataFrame, dict]:
    if sport not in SPORTS:
        raise ValueError(f'Unknown sport: {sport}')
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError('Missing required columns: ' + ', '.join(missing))
    original = len(df)
    # Event exports can contain genuine shot/pit-stop arrays. Build comparison
    # keys without discarding those nested observations from the stored rows.
    keys = df.copy()
    for column in keys.select_dtypes(include=['object']).columns:
        keys[column] = keys[column].map(lambda value: json.dumps(value, sort_keys=True, default=str) if isinstance(value, (list, dict)) else value)
    df = df.loc[~keys.duplicated()].copy()
    duplicates = original - len(df)
    df['date'] = pd.to_datetime(df['date'], errors='coerce', utc=True, format='mixed').dt.tz_localize(None)
    df['season'] = df['season'].astype('string').str.strip()
    df['competitor'] = df['competitor'].astype('string').str.strip()
    df['team'] = df['team'].astype('string').str.strip()
    invalid = df['date'].isna() | df['season'].isna() | df['season'].eq('') | df['competitor'].isna() | (df['competitor'] == '')
    removed = int(invalid.sum())
    df = df.loc[~invalid].copy()
    for metric in SPORTS[sport]['metrics']:
        if metric not in df.columns:
            df[metric] = float('nan')  # Missing is NOT zero.
        df[metric] = pd.to_numeric(df[metric], errors='coerce').replace([np.inf, -np.inf], np.nan)
    # Keep the original public `rating` column, but calculate the same bounded,
    # documented experimental score as the profile and comparison views.
    # Previously this column multiplied season totals by arbitrary weights,
    # making a full season incomparable with one game. The rating module
    # resolves the record grain and real games denominator before scoring.
    from .ratings import rating_frame
    df['rating'] = rating_frame(df,sport)['experimental_rating'].to_numpy()
    df = df.sort_values('date').reset_index(drop=True)
    return df, {'input_rows': original, 'duplicates_removed': duplicates, 'invalid_rows_removed': removed, 'valid_rows': len(df)}

def rankings(df: pd.DataFrame, sport: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=['competitor', 'team', 'appearances', 'average_rating', *SPORTS[sport]['metrics']])
    key = 'competitor_id' if 'competitor_id' in df else 'competitor'
    rows = []
    for identity, group in df.groupby(key, dropna=True):
        latest = group.sort_values('date').iloc[-1]
        kinds = group.get('record_type', pd.Series('', index=group.index)).fillna('').astype(str)
        kinds = kinds + ' ' + group.get('record_kind', pd.Series('',index=group.index)).fillna('').astype(str)
        season = kinds.str.contains('season|career', case=False, regex=True)
        games = game_counts(group).where(season,1)
        count = int(games.sum()) if games.notna().all() else None
        rating = float(group['rating'].mean()) if group['rating'].notna().any() else np.nan
        if season.any():
            rating = weighted_average(group['rating'], games)
        row = {'competitor':latest['competitor'], 'team':latest['team'], 'appearances':count, 'average_rating':rating}
        if key == 'competitor_id':
            row[key] = identity
        for metric in SPORTS[sport]['metrics']:
            stats = metric_summary(group, metric)
            row[metric] = stats['per_game'] if stats['per_game'] is not None else stats['average']
        rows.append(row)
    return pd.DataFrame(rows).sort_values('average_rating', ascending=False, na_position='last')

def recent_form(df: pd.DataFrame, competitor: str, n: int = 5) -> float | None:
    values = df.loc[df['competitor'] == competitor].sort_values('date')['rating'].dropna().tail(n)
    return round(float(values.mean()), 2) if not values.empty else None

def summary(df: pd.DataFrame, sport: str) -> dict:
    return {'records': len(df), 'competitors': int(df['competitor'].nunique()), 'teams': int(df['team'].nunique()), 'seasons': int(df['season'].nunique()), 'average_rating': round(float(df['rating'].mean()), 2) if df['rating'].notna().any() else None}


NON_TOTAL = {'finish_position', 'grid_position', 'position', 'round', 'rating',
             'experimental_rating', 'recent_rating', 'rating_weight',
             'age', 'rank', 'number', 'fastest_lap', 'lap_time', 'speed',
             'x', 'y', 'shot_x', 'shot_y', 'latitude', 'longitude'}


def is_rate(metric: str) -> bool:
    return (metric in NON_TOTAL or metric.endswith(('_pg', '_per_90', '_per_36', '_ms', '_position', '_number', '_game_high', '_rating', '_rate'))
            or metric.startswith('minutes_weighted_game_')
            or metric.removeprefix('advanced_') in {'pace', 'pie', 'player_impact_estimate', 'box_plus_minus', 'win_shares_per_48'}
            or metric in {'championship_points', 'usage_rate', 'net_rating', 'positions_gained', 'fastest_lap_number', 'classified_position'}
            or any(token in metric for token in ('percentage', '_pct', 'accuracy', 'efficiency', 'per_game', 'average', 'percentile')))


def lower_is_better(metric: str) -> bool:
    return metric.endswith(('_position', '_time_ms')) or metric in {'position', 'q1_ms', 'q2_ms', 'q3_ms', 'lap_time', 'turnovers', 'fouls', 'yellow_cards', 'red_cards', 'race_time_ms', 'goals_against', 'points_against', 'goals_conceded', 'points_conceded', 'average_finish', 'average_qualifying'}


def game_counts(df: pd.DataFrame) -> pd.Series:
    """Resolve the two supported games fields row by row, retaining unknowns.

    A merged import can contain a `games` column from one source and a
    `games_played` column from another. Choosing one entire column would lose
    genuine denominators on the other rows. Neither missing value becomes zero.
    """
    primary = pd.to_numeric(df.get('games', pd.Series(np.nan,index=df.index)),errors='coerce')
    alternate = pd.to_numeric(df.get('games_played', pd.Series(np.nan,index=df.index)),errors='coerce')
    return primary.where(primary.notna(),alternate).replace([np.inf,-np.inf],np.nan)


def weighted_average(values, weights) -> float | None:
    values, weights = pd.Series(values, dtype=float), pd.Series(weights, dtype=float)
    valid = values.notna() & weights.notna() & (weights > 0) & np.isfinite(values) & np.isfinite(weights)
    return float(np.average(values[valid], weights=weights[valid])) if valid.any() else None


def metric_summary(df: pd.DataFrame, metric: str) -> dict:
    """Do not count one season-total row as one game, or add percentages."""
    shooting = {'field_goal_pct':('field_goals_made','field_goal_attempts'),
                'three_point_pct':('three_point_makes','three_point_attempts'),
                'free_throw_pct':('free_throws_made','free_throw_attempts'),
                'pass_accuracy':('passes_completed','passes')}
    values = pd.to_numeric(df.get(metric, pd.Series(np.nan,index=df.index)), errors='coerce').replace([np.inf, -np.inf], np.nan)
    if metric in shooting:
        made_key, attempts_key = shooting[metric]
        if made_key in df and attempts_key in df:
            made = pd.to_numeric(df[made_key],errors='coerce')
            attempts = pd.to_numeric(df[attempts_key],errors='coerce')
            values = values.where(values.notna(),made.div(attempts.where(attempts.gt(0))))
    valid = values.dropna()
    if valid.empty:
        return {'total': None, 'average': None, 'best': None, 'count': 0, 'per_game': None}
    per_game = None
    total = None if is_rate(metric) else float(valid.sum())
    average = float(valid.mean())
    if not is_rate(metric):
        kinds = df.get('record_type', df.get('record_kind', pd.Series('event', index=df.index))).fillna('event').astype(str)
        if 'record_kind' in df:
            kinds = kinds + ' ' + df['record_kind'].fillna('').astype(str)
        season_rows = kinds.str.contains('season|career', case=False, regex=True)
        average_rows = season_rows & kinds.str.contains(r'per.?game|average', case=False, regex=True)
        games = game_counts(df)
        if average_rows.any():
            # Earlier GameSense archives contained PPG, whereas the new provider
            # supplies season totals. Explicit record grain preserves both.
            needed = average_rows & values.notna()
            if games[needed].notna().all() and (games[needed] > 0).all():
                contributions = values.where(~average_rows, values * games)
                total = float(contributions.sum(min_count=1))
                if average_rows[values.notna()].all():
                    average = weighted_average(values, games)
            else:
                total = None
        denominators = games.where(season_rows, 1).where(values.notna())
        if total is not None and denominators[values.notna()].notna().all() and (denominators[values.notna()] > 0).all() and denominators.sum() > 0:
            per_game = float(total / denominators.sum())
    if metric.endswith('_pg') or 'per_game' in metric:
        weights = game_counts(df)
        weighted = weighted_average(values, weights)
        if weighted is not None:
            average = weighted
    # Career percentages use the source's actual attempt counts. An unweighted
    # mean of 1/1 and 0/9 would incorrectly report 50% instead of 10%.
    if metric in shooting:
        made_key, attempts_key = shooting[metric]
        if made_key in df and attempts_key in df:
            made = pd.to_numeric(df[made_key], errors='coerce')
            attempts = pd.to_numeric(df[attempts_key], errors='coerce')
            eligible = values.notna()
            if made[eligible].notna().all() and attempts[eligible].notna().all() and attempts[eligible].sum() > 0:
                # Some official imports supply season *per-game* makes and
                # attempts. Multiply each by its actual games before forming
                # the career ratio; otherwise a short season gets equal weight.
                eligible_frame = df.loc[eligible]
                made_total = metric_summary(eligible_frame,made_key)['total']
                attempt_total = metric_summary(eligible_frame,attempts_key)['total']
                if made_total is not None and attempt_total is not None and attempt_total > 0:
                    average = float(made_total/attempt_total)
    return {'total': total, 'average': average, 'best': float(valid.min() if lower_is_better(metric) else valid.max()), 'count': len(valid), 'per_game': per_game}


def season_history(df: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    if df.empty or 'season' not in df:
        return pd.DataFrame()
    rows = []
    for season, group in df.groupby('season', sort=True):
        row = {'season': season, 'records': len(group), 'teams': ', '.join(group['team'].dropna().astype(str).unique()) if 'team' in group else ''}
        for metric in metrics:
            stats = metric_summary(group, metric)
            row[metric] = stats['average'] if is_rate(metric) else stats['total']
        rows.append(row)
    return pd.DataFrame(rows)


def leaderboard(df: pd.DataFrame, metric: str, total=True) -> pd.DataFrame:
    if df.empty or metric not in df:
        return pd.DataFrame(columns=['competitor_id', 'competitor', 'team', metric, 'records'])
    key = 'competitor_id' if 'competitor_id' in df else 'competitor'
    rows = []
    for identity, group in df.groupby(key):
        stats = metric_summary(group, metric)
        value = stats['total'] if total and not is_rate(metric) else stats['average']
        latest = group.sort_values('date').iloc[-1] if 'date' in group else group.iloc[-1]
        rows.append({'competitor_id': identity, 'competitor': latest['competitor'], 'team': latest['team'], metric: value, 'records': len(group)})
    return pd.DataFrame(rows).sort_values(metric, ascending=lower_is_better(metric), na_position='last').reset_index(drop=True)
