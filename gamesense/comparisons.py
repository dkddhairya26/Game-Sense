"""Compatibility rules and reproducible head-to-head differences.

Labels never establish identity: grouping uses provider IDs. Two sources may
describe the same season, so comparisons require one chosen source. Team and
athlete observations cannot share a statistical denominator.
"""
from __future__ import annotations
import numbers
import pandas as pd
from .insights import performance_summary


def comparison_guard(frame: pd.DataFrame) -> str:
    if frame.empty or 'competitor_id' not in frame or frame['competitor_id'].nunique()!=2:
        return 'Choose two different competitors with records under the current filters.'
    for column, message in (
        ('entity_type','Choose two players, two drivers or two clubs. Athlete and club statistics use different units.'),
        ('provider','Choose one source. Overlapping provider records cannot be counted together.'),
        ('phase','Choose one competition phase; regular-season and playoff statistics are different contexts.')):
        if column in frame and frame[column].dropna().nunique()>1:
            return message
    if 'record_kind' in frame:
        kinds=frame['record_kind'].fillna('').astype(str)+' '+frame.get('record_type',pd.Series('',index=frame.index)).fillna('').astype(str)
        if kinds.str.contains('career',case=False).any():
            return 'Career snapshots are not comparable to match or season records. Select a consistent source grain.'
        aggregate=kinds.str.contains('season',case=False)
        if aggregate.any() and not aggregate.all():
            return 'Choose one record grain. Individual matches and season summaries cannot share a head-to-head timeline.'
    if 'phase' in frame and frame['phase'].notna().any() and frame['phase'].isna().any():
        return 'Some records have an unknown competition phase. Select records with a consistently identified phase.'
    return ''


def comparison_table(frame: pd.DataFrame, sport: str) -> pd.DataFrame:
    """Return shared measured summaries; unavailable values remain blank.

    A difference has meaning only when both sides supply that measure. Missing
    values propagate to the difference instead of making one competitor zero.
    """
    if comparison_guard(frame):
        return pd.DataFrame(columns=['statistic','A','B','A minus B'])
    groups=list(frame.groupby('competitor_id',sort=False))
    summaries=[performance_summary(group,sport) for _,group in groups]
    names=[str(group['competitor'].iloc[0]) for _,group in groups]
    rows=[]
    for key in dict.fromkeys([*summaries[0],*summaries[1]]):
        values=[summary.get(key) for summary in summaries]
        if not any(isinstance(value,numbers.Real) and not isinstance(value,bool) for value in values):
            continue
        observed=[float(value) if isinstance(value,numbers.Real) and pd.notna(value) else None for value in values]
        rows.append({'statistic':key.replace('_',' ').title(),
                     'A · '+names[0]:observed[0],'B · '+names[1]:observed[1],
                     'A minus B':observed[0]-observed[1] if all(value is not None for value in observed) else None})
    return pd.DataFrame(rows)
