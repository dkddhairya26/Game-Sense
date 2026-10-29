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

    def query(self, sport, season=None, competitor_id=None, limit=1000, offset=0, entity_type=None, provider=None, team=None):
        clauses, args = ['sport=?'], [sport]
        for column, value in [('season', season), ('competitor_id', competitor_id), ('entity_type', entity_type), ('provider', provider), ('team', team)]:
            if value is not None and value not in ('All seasons', ''):
                clauses.append(column + '=?')
                args.append(str(value))
        sql = 'SELECT payload FROM records WHERE ' + ' AND '.join(clauses) + ' ORDER BY date DESC,record_id'
        if limit is not None:
            sql += ' LIMIT ? OFFSET ?'
            args.extend([max(0, int(limit)), max(0, int(offset))])
        with self.connect() as con:
            rows = [json.loads(r['payload']) for r in con.execute(sql, args)]
        if not rows:
            return pd.DataFrame(columns=['date','season','competitor_id','competitor','team','sport','provider','entity_type'])
        frame = pd.DataFrame(rows)
        frame['date'] = pd.to_datetime(frame['date'], errors='coerce', utc=True).dt.tz_localize(None)
        return frame

    def search(self, sport, text='', limit=100, first_season=None, last_season=None):
        # Escape LIKE syntax, so names containing %/_ remain literal searches.
        clauses, args = ['sport=?'], [sport]
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
        sql = '''SELECT competitor_id,competitor,entity_type,MIN(season) first_season,
                 MAX(season) last_season,COUNT(*) records,
                 (SELECT r2.team FROM records r2 WHERE r2.competitor_id=records.competitor_id
                  AND r2.sport=records.sport ORDER BY r2.date DESC LIMIT 1) team
                 FROM records WHERE ''' + ' AND '.join(clauses) + ' GROUP BY competitor_id ORDER BY competitor COLLATE NOCASE LIMIT ?'
        args.append(max(1, min(int(limit), 10000)))
        with self.connect() as con:
            return pd.read_sql_query(sql, con, params=args)

    def seasons(self, sport):
        with self.connect() as con:
            return [row[0] for row in con.execute('SELECT DISTINCT season FROM records WHERE sport=? ORDER BY season DESC', (sport,))]

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
        rows = []
        namespace = hashlib.sha256(source.encode()).hexdigest()[:12]
        for i, raw in enumerate(frame.to_dict('records')):
            row = {k: _json_value(v) for k,v in raw.items()}
            row.update(sport=sport, provider=source)
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
                row.pop('record_id',None)
            rows.append(row)
        count = self.upsert(rows)
        for season in frame['season'].astype(str).unique():
            self.mark(source, sport, season, 'complete')
        return count

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
            count, rows, seasons = 0, [], set()
            opener = gzip.open if seed.suffix == ".gz" else open
            with opener(seed, "rt", encoding="utf-8") as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    seasons.add((row["provider"], row["sport"], str(row["season"])))
                    rows.append(row)
                    if len(rows) >= 1000:
                        count += self.upsert(rows, overwrite=False)
                        rows = []
            if rows:
                count += self.upsert(rows, overwrite=False)
            for provider, sport, season in seasons:
                # OpenFootball covers a selection of club leagues, NEVER all
                # possible soccer competitions or individual players.
                if provider == "openfootball":
                    self.mark(provider, sport, season, "partial",
                              "CC0 European club match results for selected leagues. "
                              "No player statistics, lineups or comprehensive league coverage.")
                else:
                    self.mark(provider, sport, season, "complete")
            self.set_setting(key, stamp)
            total += count
        return total
