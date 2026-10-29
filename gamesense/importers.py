"""Normalize permitted user datasets while retaining their source columns.

Ported from the 0.5 importer. Date-free rows carry an explicit season-grain
marker; that date is a sort key, never a claimed match. Ambiguous headers are
rejected before any data is changed.
"""
from __future__ import annotations

from collections import defaultdict
import re

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
