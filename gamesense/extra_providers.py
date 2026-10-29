"""Optional real player-level providers for historic NBA and global football.

These downloads run only after the user requests them. NBA Stats can block
automated requests. API-Football requires the USER'S OWN API key and provider
rights; GameSense must not distribute API-Sports photographs or downloaded
licensed data without the appropriate permission.

No athlete, score, season, or historical statistic is synthesized here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from urllib.parse import urlencode

from .archive import data_directory
from .http import HttpClient
from .providers import Provider, ProviderMeta, _base, _number


def _id(value):
    """Normalize integer IDs, including floats created by Pandas iterrows."""
    try:
        return str(int(float(value)))
    except (ValueError, TypeError, OverflowError):
        return str(value)


def _num(value):
    try:
        return float(value) if value not in ('', None) else None
    except (TypeError, ValueError):
        return None


class NBAStatsHistoryProvider(Provider):
    meta = ProviderMeta(
        'nba_stats', 'NBA Stats (historical, on demand)', 'NBA',
        'official NBA player-season statistics',
        'NBA-controlled statistical data; nba_api package MIT; redistribution NOT granted',
        'https://www.nba.com/terms-of-use',
        'REQUESTABLE years begin in 1946–47; actual coverage is verified per request. '
        'NBA.com endpoints can refuse automated clients. Older metrics were not recorded. '
        'This provider never bundles or republishes NBA statistics.',
        'Source: NBA Stats via nba_api, https://github.com/swar/nba_api. '
        'NBA retains rights in NBA content; downloaded data are stored privately.')

    @staticmethod
    def available_seasons(client=None):
        current = datetime.now(timezone.utc)
        last = current.year if current.month >= 9 else current.year - 1
        return [f'{year}-{(year + 1) % 100:02d}' for year in
                range(last, 1945, -1)]

    @staticmethod
    def parse_frame(frame, season, advanced=None):
        """Normalize every actual source athlete row and all nonempty stat fields."""
        if frame is None or frame.empty:
            return []
        required = {'PLAYER_ID', 'PLAYER_NAME'}
        if not required.issubset(set(frame.columns)):
            raise ValueError('NBA provider omitted player identities')
        meta = NBAStatsHistoryProvider.meta
        start = int(season[:4])
        extras = {}
        if advanced is not None and not advanced.empty and 'PLAYER_ID' in advanced:
            for _, item in advanced.iterrows():
                extras[_id(item['PLAYER_ID'])] = dict(item)
        fields = {
            'GP':'games', 'GS':'starts','MIN':'minutes', 'PTS':'points',
            'REB':'rebounds','AST':'assists','STL':'steals','BLK':'blocks',
            'TOV':'turnovers','OREB':'offensive_rebounds','DREB':'defensive_rebounds',
            'FGM':'field_goals_made','FGA':'field_goal_attempts',
            'FG_PCT':'field_goal_pct','FG3M':'three_point_makes',
            'FG3A':'three_point_attempts','FG3_PCT':'three_point_pct',
            'FTM':'free_throws_made','FTA':'free_throw_attempts',
            'FT_PCT':'free_throw_pct','PF':'personal_fouls',
            'PLUS_MINUS':'plus_minus','W':'wins','L':'losses'
        }
        rows=[]
        for _, player in frame.iterrows():
            pid = player.get('PLAYER_ID')
            if pid is None:
                continue
            pid = _id(pid)
            team_id = str(player.get('TEAM_ID') or '')
            team = player.get('TEAM_ABBREVIATION') or 'Not specified'
            name = player.get('PLAYER_NAME')
            if not name or str(name)=='nan':
                continue
            record = _base(
                meta, season, record_id=f'nba_stats:{season}:{pid}:{team_id}',
                date=f'{start+1}-06-30', date_precision='season',
                record_kind='season_per_game_average',
                competitor_id=f'nba:{pid}', competitor=str(name),
                entity_type='athlete', team=str(team),
                team_id='nba:'+team_id if team_id else '',
                competition='NBA regular season',
                nba_id=pid, athlete_id=pid,
                source_url='https://www.nba.com/stats/players/traditional',
                advanced_data_status='unavailable')
            for key, value in player.items():
                if key in required or key in {'TEAM_ID','TEAM_ABBREVIATION'}:
                    continue
                if key in fields or _num(value) is not None:
                    numeric = _num(value)
                    if numeric is not None:
                        record[fields.get(key, key.lower())] = numeric
            if 'games' in record and 'points' in record:
                record['points_pg']=record['points']
            adv=extras.get(pid)
            if adv:
                for key,value in adv.items():
                    if key in {'PLAYER_ID','PLAYER_NAME','TEAM_ID',
                               'TEAM_ABBREVIATION'}:
                        continue
                    if _num(value) is not None:
                        record['advanced_'+key.lower()]=_num(value)
                record['advanced_data_status']='reported by NBA Stats'
            rows.append(record)
        return rows

    def iter_season(self, season, client, archive=None, force=False):
        if not re.fullmatch(r'\d{4}-\d{2}', str(season)):
            raise ValueError('NBA season must be YYYY-YY')
        try:
            from nba_api.stats.endpoints import leaguedashplayerstats
        except ImportError as exc:
            raise RuntimeError('Install nba_api to use historical NBA Stats') from exc
        # This endpoint is owned by NBA.com; user network/IP restrictions vary.
        client.check()
        try:
            raw = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season, season_type_all_star='Regular Season',
                per_mode_detailed='PerGame', timeout=25).get_data_frames()[0]
        except Exception as exc:
            raise RuntimeError(
                f'NBA.com blocked or could not supply {season}: {type(exc).__name__}. '
                'No season was fabricated or marked downloaded.') from exc
        if raw.empty:
            raise ValueError(f'NBA.com returned zero players for {season}')
        advanced=None
        if int(season[:4]) >= 1996:
            client.check()
            try:
                advanced = leaguedashplayerstats.LeagueDashPlayerStats(
                    season=season, season_type_all_star='Regular Season',
                    per_mode_detailed='PerGame',
                    measure_type_detailed_defense='Advanced',
                    timeout=25).get_data_frames()[0]
            except Exception:
                pass  # Advanced values unavailable is not zero.
        rows=self.parse_frame(raw, season, advanced)
        if not rows:
            raise ValueError('NBA Stats returned no usable player identities')
        for i in range(0,len(rows),250):
            client.check()
            yield rows[i:i+250]


class APIFootballProvider(Provider):
    meta = ProviderMeta(
        'api_football', 'API-Football (player records, own key)', 'Soccer',
        'league/team/player historical season aggregates',
        'API-Sports paid/free account terms; user owns key; redistribution rights not assumed',
        'https://www.api-football.com/documentation_v3',
        'Optional authenticated provider covering league and player histories '
        'WHERE YOUR PLAN GRANTS ACCESS. Search Cristiano Ronaldo or another '
        'real player by stable API ID; retrieve his covered seasons or browse '
        'specific league-seasons. Does not guarantee his complete career.',
        'Source: API-Football by API-Sports. Users must comply with their own '
        'subscription and any player image/data redistribution restrictions.')

    def __init__(self):
        self.api_key = ''

    def set_api_key(self, key):
        # Secret is memory-only; never written to source control, logs, QSettings
        # or historical data records.
        self.api_key = str(key or '').strip()

    def _request(self, route, params=None, client=None):
        if not self.api_key:
            raise RuntimeError(
                'API-Football needs your own key. Enter it in Data manager; '
                'no API key is bundled with GameSense.')
        query=urlencode(params or {})
        url='https://v3.football.api-sports.io/'+route
        if query:
            url+='?'+query
        # Separate cache per credential, without putting keys in cache filenames.
        key_fingerprint=sha256(self.api_key.encode()).hexdigest()[:16]
        secure_cache=data_directory()/'http'/'api-football-'+key_fingerprint
        active=HttpClient(secure_cache, cancel=getattr(client,'cancel',None),
                          timeout=30, offline=getattr(client,'offline',False))
        payload=active.get_json(url,headers={'x-apisports-key': self.api_key},
                                max_age=3600)
        if not isinstance(payload,dict):
            raise RuntimeError('Unexpected API-Football response')
        if payload.get('errors'):
            raise RuntimeError('API-Football refused this request: '+
                               json.dumps(payload['errors'],ensure_ascii=False)[:350])
        return payload

    def available_seasons(self,client=None):
        payload=self._request('players/seasons',client=client)
        return [str(y) for y in sorted(
            {int(y) for y in payload.get('response',[])
             if isinstance(y,(int,str)) and str(y).isdigit()},reverse=True)]

    def search_profiles(self,name,client=None):
        term=str(name or '').strip()
        if len(term)<4:
            raise ValueError('Enter at least four characters of a player name.')
        payload=self._request('players/profiles', {'search':term},client)
        found=[]
        for entry in payload.get('response',[]):
            p=entry.get('player') or {}
            if p.get('id') is None:
                continue
            found.append({
                'id':int(p['id']), 'name':p.get('name') or '',
                'nationality':p.get('nationality') or '',
                'birth':(p.get('birth') or {}).get('date'),
                'position':p.get('position') or '',
                'provider':'api_football',
            })
        return found

    def player_seasons(self,player_id,client=None):
        value=str(int(player_id))
        payload=self._request('players/seasons', {'player':value},client)
        return sorted({int(y) for y in payload.get('response',[])
                       if str(y).isdigit()})

    @staticmethod
    def normalize_player(item, season):
        """Each team-league-season is separate; transfers are not overwritten."""
        p=item.get('player') or {}
        pid=p.get('id')
        if pid is None:
            return []
        meta=APIFootballProvider.meta
        result=[]
        for part in item.get('statistics') or []:
            team=part.get('team') or {}
            league=part.get('league') or {}
            games=part.get('games') or {}
            goals=part.get('goals') or {}
            shots=part.get('shots') or {}
            passes=part.get('passes') or {}
            tackles=part.get('tackles') or {}
            duels=part.get('duels') or {}
            dribbles=part.get('dribbles') or {}
            cards=part.get('cards') or {}
            fouls=part.get('fouls') or {}
            penalty=part.get('penalty') or {}
            league_id=league.get('id','unknown')
            team_id=team.get('id','unknown')
            row=_base(
                meta, season, record_id=f'api_football:{season}:{pid}:{league_id}:{team_id}',
                date=f'{int(season)+1}-06-30', date_precision='season',
                record_kind='season_total', entity_type='athlete',
                competitor_id=f'api-football:{pid}',competitor=p.get('name',''),
                nationality=p.get('nationality'),date_of_birth=(p.get('birth') or {}).get('date'),
                team=team.get('name') or 'Unknown club',
                team_id=f'api-football:{team_id}',position=games.get('position') or p.get('position'),
                competition=league.get('name') or 'Unknown competition',
                competition_id=str(league_id),
                league_country=league.get('country'),
                games=_num(games.get('appearences')),
                starts=_num(games.get('lineups')),
                minutes=_num(games.get('minutes')),
                rating=_num(games.get('rating')),
                shots=_num(shots.get('total')),
                shots_on_target=_num(shots.get('on')),
                goals=_num(goals.get('total')),
                assists=_num(goals.get('assists')),
                passes=_num(passes.get('total')),
                key_passes=_num(passes.get('key')),
                pass_accuracy=_num(passes.get('accuracy')),
                tackles=_num(tackles.get('total')),
                interceptions=_num(tackles.get('interceptions')),
                blocks=_num(tackles.get('blocks')),
                duels=_num(duels.get('total')),
                duels_won=_num(duels.get('won')),
                dribbles=_num(dribbles.get('attempts')),
                dribbles_completed=_num(dribbles.get('success')),
                fouls=_num(fouls.get('committed')),
                yellow_cards=_num(cards.get('yellow')),
                red_cards=_num(cards.get('red')),
                penalty_scored=_num(penalty.get('scored')),
                penalty_missed=_num(penalty.get('missed')),
                source_url=meta.terms_url)
            # API-Sports photo URLs are intentionally NOT redistributed as
            # licensed images; portrait widget handles verified Commons media.
            result.append(row)
        return result

    def _pages(self,params,client=None):
        page=1
        while True:
            if client:
                client.check()
            request=dict(params,page=page)
            payload=self._request('players',request,client)
            for player in payload.get('response') or []:
                yield player
            last=int((payload.get('paging') or {}).get('total') or 1)
            if page>=last:
                break
            if page>=250:
                raise RuntimeError('API-Football results exceed the 250-page safety limit.')
            page+=1

    def iter_season(self, season, client, archive=None, force=False):
        """A global player-season request is unsupported; ask for league or ID."""
        raise RuntimeError('API-Football needs a selected league or player. '
                           'Use Download competition or Find player in Data manager.')

    def competitions(self,client=None):
        payload=self._request('leagues',client=client)
        entries=[]
        for item in payload.get('response') or []:
            league=item.get('league') or {}
            country=item.get('country') or {}
            if not league.get('id'):
                continue
            for season in item.get('seasons') or []:
                year=season.get('year')
                if not isinstance(year,int):
                    continue
                entries.append({
                    'competition_id':int(league['id']),
                    'season_id':year,
                    'competition_name':f"{league.get('name','Unknown')} · {country.get('name','')}",
                    'season_name':str(year),
                })
        return entries

    def download_competition(self,archive,competition_id,season_id,
                             client=None,cancel=None,progress=None):
        league=int(competition_id)
        year=int(season_id)
        client=client or HttpClient(data_directory()/'http',cancel=cancel)
        count=0
        for index,item in enumerate(self._pages({'league':league,'season':year},client),1):
            records=self.normalize_player(item,str(year))
            if records:
                count+=archive.upsert(records)
            if progress and (index%20==0 or index==1):
                progress(index,0,f'League {league} season {year}: {index} athletes scanned')
        archive.mark(self.meta.id,'Soccer',str(year),'partial',
                     f'League {league} downloaded; not every league in this season.')
        return count

    def download_player(self, archive, player_id, client=None, progress=None):
        """A Ronaldo-style career download uses the verified provider player ID."""
        pid=int(player_id)
        years=self.player_seasons(pid,client)
        if not years:
            raise ValueError('No supported seasons returned for this player ID')
        count=0
        failures=[]
        for index,year in enumerate(years,1):
            if client:
                client.check()
            try:
                rows=[]
                for item in self._pages({'id':pid,'season':year},client):
                    if int((item.get('player') or {}).get('id') or -1)==pid:
                        rows+=self.normalize_player(item,str(year))
                if rows:
                    count+=archive.upsert(rows)
                    archive.mark(self.meta.id,'Soccer',str(year),'partial',
                                 f'Player {pid} imported, not all league players')
                else:
                    failures.append(str(year))
            except Exception as exc:
                failures.append(f'{year}: {type(exc).__name__}')
            if progress:
                progress(index,len(years),f'Player {pid}: {year} saved ({count} rows)')
        if count==0:
            raise RuntimeError(
                'No licensed player records returned. Check key plan/coverage. '
                'Missing years: '+', '.join(failures[:8]))
        return {'records':count,'seasons':len(years),
                'failures':failures, 'player_id':pid}
