"""Indexed, incremental historical archive with stable identities and source scope.

One row per provider / event / entity. Flexible statistics retain their original
meaning in JSON; common search/filter columns stay indexed. Every batch commits
independently, so cancellation or failure cannot discard completed downloads.
"""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import contextmanager
import hashlib
import gzip
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys

import pandas as pd


def data_directory():
    override = os.environ.get('GAMESENSE_DATA_DIR')
    if override:
        return Path(override)
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'GameSense'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'GameSense'
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))) / 'GameSense'


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _json_value(value):
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, dict):
        return {str(k):_json_value(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    if hasattr(value, 'item'):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def _seed_coverage(row):
    """Classify a snapshot at its source capture date, not the current year.

    An October 2026 NBA 2026–27 snapshot remains partial even when opened in
    2028. Time passing cannot add the missing games to an immutable bundle.
    Past closed seasons keep the legacy completed-import status; this still does
    not guarantee every historical field, athlete or competition was recorded.
    """
    if row['provider'] == 'openfootball':
        return ('partial', 'CC0 club match results for selected leagues only; no comprehensive league or player coverage.')
    declared = str(row.get('season_status') or row.get('coverage_status') or '')
    if declared in ('ongoing_partial', 'partial'):
        return declared, 'Source explicitly identifies this season snapshot as incomplete.'
    captured = row.get('source_updated') or row.get('fetched_at')
    try:
        as_of = datetime.fromisoformat(str(captured).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return 'partial', 'Source snapshot date is unavailable; season completion cannot be verified.'
    season = str(row['season'])
    split = re.fullmatch(r'(\d{4})-(\d{2}|\d{4})', season)
    if split:
        start, end_text = int(split[1]), split[2]
        end = int(end_text) if len(end_text) == 4 else start // 100 * 100 + int(end_text)
        if end < start:
            end += 100
        # August is deliberately conservative for a basketball season ending
        # in June; the algorithm does not infer closure from the latest row.
        closed = end < as_of.year or (end == as_of.year and as_of.month >= 8)
    elif re.fullmatch(r'\d{4}', season):
        closed = int(season) < as_of.year
    else:
        return 'partial', 'Nonstandard season identifier; completion is not verified.'
    if not closed:
        return ('ongoing_partial', 'Bundled source snapshot was captured during this season; later results are not present or verified.')
    return 'complete', ''


class Archive:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else data_directory() / 'archive.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS records(
                    record_id TEXT PRIMARY KEY, sport TEXT NOT NULL,
                    provider TEXT NOT NULL, season TEXT NOT NULL,
                    date TEXT NOT NULL, competitor_id TEXT NOT NULL,
                    competitor TEXT NOT NULL, team TEXT NOT NULL DEFAULT '',
                    entity_type TEXT NOT NULL DEFAULT 'athlete',
                    competition TEXT NOT NULL DEFAULT '', payload TEXT NOT NULL,
                    updated TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS records_sport_season ON records(sport,season,date);
                CREATE INDEX IF NOT EXISTS records_identity ON records(sport,competitor_id,season);
                CREATE INDEX IF NOT EXISTS records_names ON records(sport,competitor COLLATE NOCASE);
                CREATE TABLE IF NOT EXISTS downloads(
                    provider TEXT NOT NULL, sport TEXT NOT NULL, season TEXT NOT NULL,
                    status TEXT NOT NULL, record_count INTEGER NOT NULL DEFAULT 0,
                    updated TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY(provider, sport, season));
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            ''')
            # Earlier previews keyed downloads only by source/season. The same
            # imported filename can supply several sports, which must retain
            # independent coverage rather than overwrite each other's status.
            primary=tuple(row['name'] for row in sorted(con.execute('PRAGMA table_info(downloads)'),key=lambda row:row['pk']) if row['pk'])
            if primary!=('provider','sport','season'):
                con.executescript('''
                    BEGIN IMMEDIATE;
                    ALTER TABLE downloads RENAME TO downloads_legacy;
                    CREATE TABLE downloads(
                        provider TEXT NOT NULL,sport TEXT NOT NULL,season TEXT NOT NULL,
                        status TEXT NOT NULL,record_count INTEGER NOT NULL DEFAULT 0,
                        updated TEXT NOT NULL,error TEXT NOT NULL DEFAULT '',
                        PRIMARY KEY(provider,sport,season));
                    INSERT INTO downloads SELECT provider,sport,season,status,record_count,updated,error FROM downloads_legacy;
                    DROP TABLE downloads_legacy;
                    COMMIT;
                ''')

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA busy_timeout=30000')
        try:
            with con:
                yield con
        finally:
            con.close()

    def upsert(self, rows, overwrite=True):
        values = []
        now = utc_now()
        for raw in rows:
            row = {str(k): _json_value(v) for k, v in raw.items()}
            for required in ('sport', 'provider', 'season', 'date', 'competitor_id', 'competitor'):
                if not row.get(required):
                    raise ValueError('Historical record is missing ' + required)
            if row['sport'] not in ('Soccer', 'NBA', 'AFL', 'F1'):
                raise ValueError('Unknown sport')
            try:
                datetime.fromisoformat(str(row['date']).replace('Z','+00:00'))
            except ValueError as exc:
                raise ValueError('Historical record has an invalid ISO date.') from exc
            row['season'] = str(row['season'])
            record_id = row.get('record_id')
            if not record_id:
                identity = '|'.join(str(row.get(k, '')) for k in ('provider', 'sport', 'season', 'event_id', 'date', 'competitor_id', 'team'))
                record_id = hashlib.sha256(identity.encode()).hexdigest()
            row['record_id'] = record_id
            values.append((record_id, row['sport'], row['provider'], row['season'], str(row['date']), row['competitor_id'], row['competitor'], row.get('team') or '', row.get('entity_type') or 'athlete', row.get('competition') or '', json.dumps(row, ensure_ascii=False, allow_nan=False), now))
        with self.connect() as con:
            conflict = '''ON CONFLICT(record_id) DO UPDATE SET date=excluded.date,competitor=excluded.competitor,
                team=excluded.team,entity_type=excluded.entity_type,competition=excluded.competition,
                payload=excluded.payload,updated=excluded.updated''' if overwrite else 'ON CONFLICT(record_id) DO NOTHING'
            before=con.total_changes
            con.executemany('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?,?) '+conflict, values)
            changed=con.total_changes-before
        return changed

    def query(self, sport, season=None, competitor_id=None, limit=1000, offset=0, entity_type=None, provider=None, team=None, competition=None):
        clauses, args = ['sport=?'], [sport]
        for column, value in [('season', season), ('competitor_id', competitor_id), ('entity_type', entity_type), ('provider', provider), ('team', team), ('competition', competition)]:
            if value is not None and value not in ('All seasons', ''):
                clauses.append(column + '=?')
                args.append(str(value))
        sql = 'SELECT payload FROM records WHERE ' + ' AND '.join(clauses) + ' ORDER BY date DESC,record_id'
        if limit is not None:
            sql += ' LIMIT ? OFFSET ?'
            args.extend([max(0, int(limit)), max(0, int(offset))])
        with self.connect() as con:
            rows = [json.loads(r['payload']) for r in con.execute(sql, args)]
            coverage = {(item['provider'], str(item['season'])): item['status']
                        for item in con.execute(
                            'SELECT provider,season,status FROM downloads WHERE sport=?',
                            (sport,))}
        if not rows:
            return pd.DataFrame(columns=['date','season','competitor_id','competitor','team','sport','provider','entity_type'])
        # Coverage belongs to a provider/season snapshot, not an individual
        # athlete's performance. Expose it alongside measured values so charts
        # and exports can label in-season points rather than hiding the flag in
        # Data Manager. This annotates the result; stored source data is intact.
        for row in rows:
            status = coverage.get((row.get('provider'), str(row.get('season'))))
            row['archive_status'] = status
            if status == 'ongoing_partial':
                original = row.get('season_status')
                if original is not None and original != 'ongoing_partial':
                    row.setdefault('source_season_status', original)
                row['season_status'] = 'ongoing_partial'
        frame = pd.DataFrame(rows)
        frame['date'] = pd.to_datetime(frame['date'], errors='coerce', utc=True).dt.tz_localize(None)
        return frame

    def search(self, sport, text='', limit=100, first_season=None, last_season=None, competition=None, season=None, provider=None, entity_type=None):
        # Escape LIKE syntax, so names containing %/_ remain literal searches.
        clauses, args = ['sport=?'], [sport]
        if competition and competition != 'All competitions':
            clauses.append('competition=?')
            args.append(str(competition))
        if season and season not in ('All downloaded seasons','All seasons'):
            clauses.append('season=?')
            args.append(str(season))
        for column, value in (('provider', provider), ('entity_type', entity_type)):
            if value:
                clauses.append(column + '=?')
                args.append(str(value))
        # Source names can include middle names (e.g. Lionel Andrés Messi).
        # Match every literal token without merging distinct stable identities.
        for token in str(text).split():
            escaped = token.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            clauses.append("(competitor LIKE ? ESCAPE '\\' OR team LIKE ? ESCAPE '\\')")
            args.extend(['%' + escaped + '%', '%' + escaped + '%'])
        if first_season is not None:
            clauses.append('season>=?'); args.append(str(first_season))
        if last_season is not None:
            clauses.append('season<=?'); args.append(str(last_season))
        # Rank only the matched selection before taking display metadata. A
        # latest-career subquery against the whole archive previously labelled
        # LeBron's selected 2024–25 LAL row with the source's 2026–27 team PHI.
        # One window pass also avoids rescanning a large archive per identity.
        sql = '''WITH selected AS (
                    SELECT competitor_id,competitor,team,entity_type,season,
                           ROW_NUMBER() OVER (
                               PARTITION BY competitor_id ORDER BY date DESC,record_id
                           ) AS latest
                    FROM records WHERE ''' + ' AND '.join(clauses) + '''),
                 populations AS (
                    SELECT competitor_id,MIN(season) first_season,
                           MAX(season) last_season,COUNT(*) records
                    FROM selected GROUP BY competitor_id)
                 SELECT populations.competitor_id,selected.competitor,
                        selected.entity_type,populations.first_season,
                        populations.last_season,populations.records,selected.team
                 FROM populations JOIN selected
                   ON populations.competitor_id=selected.competitor_id
                  AND selected.latest=1
                 ORDER BY selected.competitor COLLATE NOCASE LIMIT ?'''
        args.append(max(1, min(int(limit), 10000)))
        with self.connect() as con:
            return pd.read_sql_query(sql, con, params=args)

    def seasons(self, sport):
        with self.connect() as con:
            return [row[0] for row in con.execute('SELECT DISTINCT season FROM records WHERE sport=? ORDER BY season DESC', (sport,))]

    def competitions(self, sport):
        """List actual competitions with stored records, never guessed leagues."""
        with self.connect() as con:
            return [row[0] for row in con.execute(
                "SELECT DISTINCT competition FROM records WHERE sport=? "
                "AND competition<>'' ORDER BY competition COLLATE NOCASE", (sport,))]

    def sources(self, sport):
        """Return only providers with locally stored rows for this sport."""
        with self.connect() as con:
            return [row[0] for row in con.execute(
                'SELECT DISTINCT provider FROM records WHERE sport=? ORDER BY provider',
                (sport,))]

    def entity_types(self, sport):
        """Keep club, athlete and constructor selectors based on actual records."""
        with self.connect() as con:
            return [row[0] for row in con.execute(
                'SELECT DISTINCT entity_type FROM records WHERE sport=? ORDER BY entity_type',
                (sport,))]

    def stats(self, sport):
        with self.connect() as con:
            row = dict(con.execute('''SELECT COUNT(*) records,COUNT(DISTINCT competitor_id) competitors,
                  COUNT(DISTINCT team) teams,COUNT(DISTINCT season) seasons,
                  MIN(season) first_season,MAX(season) last_season FROM records WHERE sport=?''', (sport,)).fetchone())
        row['bytes'] = self.path.stat().st_size if self.path.exists() else 0
        return row

    def count(self, sport, season=None, competitor_id=None, team=None, provider=None):
        clauses, args=['sport=?'],[sport]
        for name,value in [('season',season),('competitor_id',competitor_id),('team',team),('provider',provider)]:
            if value is not None and value not in ('All seasons',''):
                clauses.append(name+'=?'); args.append(str(value))
        with self.connect() as con:
            return con.execute('SELECT COUNT(*) FROM records WHERE '+' AND '.join(clauses),args).fetchone()[0]

    def mark(self, provider, sport, season, status, error=''):
        with self.connect() as con:
            count = con.execute('SELECT COUNT(*) FROM records WHERE provider=? AND sport=? AND season=?', (provider,sport,str(season))).fetchone()[0]
            con.execute('''INSERT INTO downloads VALUES(?,?,?,?,?,?,?) ON CONFLICT(provider,sport,season)
                DO UPDATE SET status=excluded.status,record_count=excluded.record_count,
                updated=excluded.updated,error=excluded.error''', (provider, sport, str(season), status, count, utc_now(), str(error)))

    def coverage(self, sport=None):
        with self.connect() as con:
            if sport:
                rows = con.execute('SELECT *,record_count AS count FROM downloads WHERE sport=? ORDER BY season DESC,provider', (sport,))
            else:
                rows = con.execute('SELECT *,record_count AS count FROM downloads ORDER BY sport,season DESC,provider')
            return [dict(row) for row in rows]

    def completed(self, provider, season, sport=None):
        with self.connect() as con:
            clause,args='provider=? AND season=?',[provider,str(season)]
            if sport:
                clause+=' AND sport=?'; args.append(sport)
            rows=con.execute('SELECT status FROM downloads WHERE '+clause,args).fetchall()
            return bool(rows) and all(row[0]=='complete' for row in rows)

    def setting(self, key, default=None):
        with self.connect() as con:
            row = con.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self, key, value):
        with self.connect() as con:
            con.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, json.dumps(value)))

    def import_frame(self, sport, frame, source='User import'):
        """Save already-cleaned records; retain the legacy integer return API.

        Call importers.import_dataset for validation and a detailed quality report.
        The return value counts inserts and genuine corrections, not identical
        repeated imports (SQLite otherwise counts an unchanged UPSERT as a write).
        """
        report = self.import_frame_report(sport, frame, source)
        return report['inserted_rows'] + report['updated_rows']

    def import_frame_report(self, sport, frame, source='User import'):
        """Persist accepted rows and distinguish new, corrected and unchanged data.

        Source namespaces prevent an imported export from overwriting its original
        provider. Explicit source/event identities are preferred; the fallback
        name/date/team identity is flagged because names alone cannot distinguish
        namesakes. A transaction guards the read/compare/write operation so the
        report counts match the persisted database, even during background work.
        """
        rows = []
        source = str(source)
        namespace = hashlib.sha256(source.encode()).hexdigest()[:12]
        for i, raw in enumerate(frame.to_dict('records')):
            row = {k: _json_value(v) for k,v in raw.items()}
            row.update(sport=sport, provider=source)
            row['import_source'] = source
            if not row.get('competitor_id'):
                # Name-only imported identities are isolated by source; source IDs
                # should be supplied to distinguish same-name athletes reliably.
                name_key = str(row.get('competitor', '')).strip().casefold()
                row['competitor_id'] = f'import:{namespace}:' + hashlib.sha256(name_key.encode()).hexdigest()[:20]
                row['identity_warning'] = 'Name-based imported identity; supply competitor_id to distinguish namesakes.'
            row.setdefault('entity_type', 'athlete')
            # Exported/provider record IDs belong to that source; reimporting one
            # must not overwrite its original archive record under a new label.
            # Without a source ID the stable event/date identity is used by
            # upsert, so correcting a statistic updates instead of duplicating.
            if row.get('record_id'):
                original_id=str(row['record_id'])
                row['source_record_id']=original_id
                row['record_id']='import:'+hashlib.sha256((sport+'|'+source+'|'+original_id).encode()).hexdigest()
            else:
                identity = '|'.join(str(row.get(key, '')) for key in (
                    'provider', 'sport', 'season', 'event_id', 'date',
                    'competitor_id', 'team'))
                row['record_id'] = hashlib.sha256(identity.encode()).hexdigest()
            rows.append(row)
        counts = {'inserted_rows': 0, 'updated_rows': 0, 'unchanged_rows': 0}
        now = utc_now()
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            for row in rows:
                # Normalize before comparison so pandas nullable scalars, dates
                # and nonfinite values have the exact persisted JSON semantics.
                row = {str(key): _json_value(value) for key, value in row.items()}
                row['season'] = str(row['season'])
                for required in ('sport', 'provider', 'season', 'date', 'competitor_id', 'competitor'):
                    if not row.get(required):
                        raise ValueError('Historical record is missing ' + required)
                if sport not in ('Soccer', 'NBA', 'AFL', 'F1'):
                    raise ValueError('Unknown sport')
                try:
                    datetime.fromisoformat(str(row['date']).replace('Z', '+00:00'))
                except ValueError as exc:
                    raise ValueError('Historical record has an invalid ISO date.') from exc
                existing = con.execute('SELECT payload FROM records WHERE record_id=?',
                                       (row['record_id'],)).fetchone()
                if existing and json.loads(existing['payload']) == row:
                    counts['unchanged_rows'] += 1
                    continue
                counts['updated_rows' if existing else 'inserted_rows'] += 1
                con.execute('''INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(record_id) DO UPDATE SET date=excluded.date,
                    competitor=excluded.competitor, team=excluded.team,
                    entity_type=excluded.entity_type,competition=excluded.competition,
                    payload=excluded.payload,updated=excluded.updated''', (
                    row['record_id'], sport, source, row['season'], str(row['date']),
                    row['competitor_id'], row['competitor'], row.get('team') or '',
                    row.get('entity_type') or 'athlete', row.get('competition') or '',
                    json.dumps(row, ensure_ascii=False, allow_nan=False), now))
        if 'season' in frame:
            for season in frame['season'].dropna().astype(str).unique():
                # Import completion describes the operation, not completeness of
                # a league or season. A CSV may contain just one competitor.
                self.mark(source, sport, season, 'imported',
                          'User dataset imported; competition/season completeness is not verified.')
        return counts

    def delete_season(self, sport, season, provider=None):
        clause, args = 'sport=? AND season=?', [sport, str(season)]
        if provider:
            clause += ' AND provider=?'; args.append(provider)
        with self.connect() as con:
            con.execute('DELETE FROM records WHERE ' + clause, args)
            con.execute('DELETE FROM downloads WHERE ' + clause, args)
            # Remove match checkpoints belonging to deleted StatsBomb data so a
            # later resume restores it instead of skipping now-absent matches.
            if provider in (None,'statsbomb'):
                con.execute("DELETE FROM settings WHERE key LIKE 'statsbomb_match:%' AND substr(key,17) NOT IN (SELECT json_extract(payload,'$.event_id') FROM records WHERE provider='statsbomb')")

    def reconcile_openfootball_clubs(self) -> int:
        """Repair existing v0.8 team IDs without discarding user history.

        v0.8 used a league-specific club name as its ID; Aston Villa and
        Aston Villa FC were different identities. Reconcile those to stable
        country-scoped club identifiers, including years already saved in the
        current user's database. Importantly, retain all underlying match
        dates, goal counts, source attribution and original record IDs.
        """
        from .club_identity import club_id
        changed = 0
        updates = []
        with self.connect() as con:
            source_rows = con.execute(
                "SELECT record_id, competitor_id, payload FROM records "
                "WHERE sport='Soccer' AND provider='openfootball' "
                "AND entity_type='team'").fetchall()
            for record_id, previous, payload in source_rows:
                record = json.loads(payload)
                code = str(record.get("competition_id") or "")
                if not code:
                    # Legacy downloaded items sometimes encode country/league
                    # in their ID even when competition_id was omitted.
                    pieces = str(previous).split(":")
                    if len(pieces) >= 3:
                        code = pieces[1]
                if not code:
                    continue
                try:
                    identity = club_id(record.get("competitor", ""), code)
                except ValueError:
                    continue
                if previous == identity and record.get("team_id") == identity:
                    continue
                record["competitor_id"] = identity
                record["team_id"] = identity
                updates.append((identity, json.dumps(
                    record, ensure_ascii=False, allow_nan=False), utc_now(), record_id))
                if len(updates) >= 1000:
                    con.executemany(
                        "UPDATE records SET competitor_id=?, payload=?, updated=? "
                        "WHERE record_id=?", updates)
                    changed += len(updates)
                    updates.clear()
            if updates:
                con.executemany(
                    "UPDATE records SET competitor_id=?, payload=?, updated=? "
                    "WHERE record_id=?", updates)
                changed += len(updates)
        return changed

    def seed_bundled(self):
        """Load *each* verified redistributable historical seed once.

        Old preview versions bundled a single large F1/NBA seed; keep its
        original per-file stamp so existing users do not lose data. New CC0
        soccer club results live in a separate gzip and never replace their
        existing player research imports.
        """
        base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
        folder = base / "data"
        if not folder.is_dir():
            return 0
        sources = sorted(path for path in folder.iterdir()
                         if path.is_file() and (
                             path.name.startswith("seed_") or
                             path.name.startswith("seed.")
                         ) and (
                             path.name.endswith(".jsonl") or
                             path.name.endswith(".jsonl.gz")
                         ))
        total = 0
        for seed in sources:
            stamp = hashlib.sha256(seed.read_bytes()).hexdigest()
            key = "seed_version" if seed.name in ("seed.jsonl", "seed.jsonl.gz") \
                  else "seed_version:" + seed.name
            if self.setting(key) == stamp:
                continue
            count, rows, seasons = 0, [], {}
            opener = gzip.open if seed.suffix == ".gz" else open
            with opener(seed, "rt", encoding="utf-8") as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    identity = (row["provider"], row["sport"], str(row["season"]))
                    status, reason = _seed_coverage(row)
                    previous = seasons.get(identity)
                    priority = {'complete': 0, 'partial': 1, 'ongoing_partial': 2}
                    if previous is None or priority[status] > priority[previous[0]]:
                        seasons[identity] = (status, reason)
                    rows.append(row)
                    if len(rows) >= 1000:
                        count += self.upsert(rows, overwrite=(
                        seed.name.startswith("seed_soccer_cc0")))
                        rows = []
            if rows:
                count += self.upsert(rows, overwrite=(
                    seed.name.startswith("seed_soccer_cc0")))
            for (provider, sport, season), (status, reason) in seasons.items():
                # OpenFootball covers a selection of club leagues, NEVER all
                # possible soccer competitions or individual players.
                self.mark(provider, sport, season, status, reason)
            self.set_setting(key, stamp)
            total += count
        # Run for existing users too: a completed previous seed stamp must not
        # prevent repairing legacy multi-league club identity fragments.
        self.reconcile_openfootball_clubs()
        # Existing installations can already have the same immutable seed stamp.
        # Repair misleading completed coverage labels without reimporting data or
        # overwriting a later successful live-provider refresh.
        self._repair_bundled_coverage()
        return total

    def _repair_bundled_coverage(self):
        """Repair old seed-only in-season labels using the saved source snapshot."""
        with self.connect() as con:
            groups = con.execute(
                "SELECT provider,sport,season,MAX(updated) latest FROM records "
                "WHERE provider IN ('f1db','boxscorelab') GROUP BY provider,sport,season").fetchall()
            repairs = []
            for group in groups:
                # The most recently captured record is conservative evidence of
                # the current local snapshot. Do not use SQLite import time to
                # infer when the sports season ended.
                raw = con.execute(
                    'SELECT payload FROM records WHERE provider=? AND sport=? AND season=? '
                    "ORDER BY COALESCE(json_extract(payload,'$.fetched_at'),'') DESC LIMIT 1",
                    (group['provider'], group['sport'], group['season'])).fetchone()
                if not raw:
                    continue
                status, reason = _seed_coverage(json.loads(raw['payload']))
                if status == 'ongoing_partial':
                    repairs.append((status, reason, group['provider'], group['sport'], group['season']))
            for status, reason, provider, sport, season in repairs:
                con.execute('UPDATE downloads SET status=?,error=? WHERE provider=? AND sport=? AND season=? AND status=?',
                            (status, reason, provider, sport, season, 'complete'))
