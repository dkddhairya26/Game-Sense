"""Sport-specific data validation and analytics for GameSense.

Design: raw records are cleaned once, then all UI views reuse the same calculations.
The scoring formulas are illustrative indicators, not official sport rankings.
"""
from __future__ import annotations
import pandas as pd

SPORTS = {
    'Soccer': {'metrics': ['goals', 'assists', 'shots', 'passes', 'tackles'], 'weights': {'goals': 5, 'assists': 3, 'shots': .4, 'passes': .025, 'tackles': .4}},
    'NBA': {'metrics': ['points', 'rebounds', 'assists', 'steals', 'blocks'], 'weights': {'points': 1, 'rebounds': 1.2, 'assists': 1.5, 'steals': 2, 'blocks': 2}},
    'AFL': {'metrics': ['disposals', 'marks', 'tackles', 'goals', 'clearances'], 'weights': {'disposals': .65, 'marks': 1.1, 'tackles': 1.5, 'goals': 5, 'clearances': 1.4}},
    'F1': {'metrics': ['points', 'finish_position', 'grid_position', 'laps', 'fastest_lap'], 'weights': {'points': 1, 'finish_position': -1.1, 'grid_position': -.3, 'fastest_lap': 3}},
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
    df = df.drop_duplicates()
    duplicates = original - len(df)
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['season'] = df['season'].astype('string').str.strip()
    df['competitor'] = df['competitor'].astype('string').str.strip()
    df['team'] = df['team'].astype('string').str.strip()
    invalid = df['date'].isna() | df['season'].isna() | df['competitor'].isna() | (df['competitor'] == '')
    removed = int(invalid.sum())
    df = df.loc[~invalid].copy()
    for metric in SPORTS[sport]['metrics']:
        if metric not in df.columns:
            df[metric] = float('nan')  # Missing is NOT zero.
        df[metric] = pd.to_numeric(df[metric], errors='coerce')
    # Preserve all supplied extra statistics. Convert numeric-looking fields while
    # leaving names, IDs, competition labels and unknown categories untouched.
    # This makes historical imports useful beyond the five default sport metrics.
    protected = set(REQUIRED) | {"record_type", "event", "opponent", "status",
                                  "position", "driver_id", "player_id", "team_id",
                                  "source", "competition"}
    for col in df.columns:
        if col in protected or col.endswith("_id") or col in SPORTS[sport]["metrics"]:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            continue
        nonempty = df[col].notna().sum()
        if not nonempty:
            continue
        values = pd.to_numeric(df[col], errors="coerce")
        if values.notna().sum() / nonempty >= .95:
            df[col] = values
    # A rating is only computed when at least one rating component is present.
    weights = SPORTS[sport]['weights']
    present = df[list(weights)].notna()
    df['rating'] = sum(df[k].fillna(0) * w for k, w in weights.items())
    df.loc[~present.any(axis=1), 'rating'] = float('nan')
    # Imported OpenLigaDB rows describe club MATCHES, not individual athletes.
    # Use a separately documented team-form formula rather than a player rating.
    if sport == "Soccer" and "record_type" in df and {"wins", "draws", "goal_difference"} <= set(df.columns):
        clubs = df["record_type"].eq("team match").fillna(False)
        for column in ("wins","draws","goal_difference"):
            df[column] = pd.to_numeric(df[column], errors="coerce")
        df.loc[clubs, "rating"] = (
            4 * df.loc[clubs, "wins"].fillna(0)
            + 2 * df.loc[clubs, "draws"].fillna(0)
            + df.loc[clubs, "goals"].fillna(0)
            + .6 * df.loc[clubs, "goal_difference"].fillna(0)
        )
    # AFL match scores are not athlete-level disposals or marks.
    if sport == "AFL" and "record_type" in df and {"wins", "draws", "margin"} <= set(df.columns):
        clubs = df["record_type"].eq("team match").fillna(False)
        for col in ("wins", "draws", "margin"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df.loc[clubs, "rating"] = (
            4 * df.loc[clubs, "wins"].fillna(0)
            + 2 * df.loc[clubs, "draws"].fillna(0)
            + .08 * df.loc[clubs, "margin"].fillna(0)
        )
    df = df.sort_values('date').reset_index(drop=True)
    return df, {'input_rows': original, 'duplicates_removed': duplicates, 'invalid_rows_removed': removed, 'valid_rows': len(df)}

def rankings(df: pd.DataFrame, sport: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=['competitor', 'team', 'appearances', 'average_rating', *SPORTS[sport]['metrics']])
    agg = {'team': 'last', 'date': 'count', 'rating': 'mean'}
    agg.update({metric: 'mean' for metric in SPORTS[sport]['metrics']})
    out = df.groupby('competitor', dropna=True).agg(agg).reset_index()
    return out.rename(columns={'date': 'appearances', 'rating': 'average_rating'}).sort_values('average_rating', ascending=False, na_position='last')

def recent_form(df: pd.DataFrame, competitor: str, n: int = 5) -> float | None:
    values = df.loc[df['competitor'] == competitor].sort_values('date')['rating'].dropna().tail(n)
    return round(float(values.mean()), 2) if not values.empty else None

def summary(df: pd.DataFrame, sport: str) -> dict:
    return {'records': len(df), 'competitors': int(df['competitor'].nunique()), 'teams': int(df['team'].nunique()), 'seasons': int(df['season'].nunique()), 'average_rating': round(float(df['rating'].mean()), 2) if df['rating'].notna().any() else None}
