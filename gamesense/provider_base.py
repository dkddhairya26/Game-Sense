"""Shared provider contracts, kept separate to avoid import cycles.

Providers for different sports may be imported directly by seed generators,
tests and packaged installers. Registering them in providers.py must not
be a prerequisite for importing their own classes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import threading

from .archive import data_directory, utc_now
from .http import HttpClient, Cancelled

@dataclass(frozen=True)
class ProviderMeta:
    id: str
    name: str
    sport: str
    scope: str
    license: str
    terms_url: str
    description: str
    attribution: str
    requires_contact: bool = False


def _client(client=None, cancel=None):
    return client or HttpClient(data_directory() / 'http-cache', cancel=cancel)


def _number(value):
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _current_year():
    return datetime.now(timezone.utc).year


def _base(meta, season, **kwargs):
    row = dict(sport=meta.sport, provider=meta.id, season=str(season),
                source_url=meta.terms_url, license=meta.license,
                attribution=meta.attribution, fetched_at=utc_now())
    row.update(kwargs)
    return row


class Provider:
    def download(self, archive, seasons, client=None, cancel=None, progress=None, force=False):
        cancel = cancel or threading.Event()
        client = _client(client, cancel)
        selected = list(dict.fromkeys(str(s) for s in seasons))
        progress = progress or (lambda done,total,message: None)
        count = 0
        for index, season in enumerate(selected):
            if cancel.is_set():
                raise Cancelled('Download cancelled; saved records remain available.')
            if not force and archive.completed(self.meta.id, season, self.meta.sport) and self.is_closed_season(season):
                progress(index+1,len(selected),f'{self.meta.name} · {season}: already downloaded')
                continue
            archive.mark(self.meta.id, self.meta.sport, season, 'downloading')
            progress(index,len(selected),f'{self.meta.name} · {season}: downloading')
            try:
                for batch in self.iter_season(season, client, archive, force):
                    if cancel.is_set():
                        raise Cancelled('Download cancelled; saved records remain available.')
                    count += archive.upsert(batch)
                archive.mark(self.meta.id, self.meta.sport, season, 'complete')
            except Cancelled as exc:
                archive.mark(self.meta.id, self.meta.sport, season, 'cancelled', str(exc))
                raise
            except Exception as exc:
                archive.mark(self.meta.id, self.meta.sport, season, 'failed', str(exc))
                raise
            progress(index+1,len(selected),f'{self.meta.name} · {season}: saved')
        return count

    def is_closed_season(self, season):
        years = re.findall(r'\d{4}', str(season))
        now=datetime.now(timezone.utc)
        if not years:
            return False
        # Calendar-year F1/AFL seasons close before the next calendar year.
        if re.fullmatch(r'\d{4}',str(season)):
            return int(season)<now.year
        # NBA's abbreviated ending year is significant: 2025-26 ends in 2026.
        nba=re.fullmatch(r'(\d{4})-(\d{2})',str(season))
        if nba:
            start=int(nba[1]); end=start//100*100+int(nba[2])
            if end<start:
                end+=100
            return end<now.year or (end==now.year and now.month>=8)
        return max(map(int,years))<now.year


