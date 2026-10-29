"""Real historical providers, with explicit coverage, identifiers and rights.

F1DB and BoxScore Lab permit attributed redistribution. StatsBomb downloads stay
local under its public research agreement. Squiggle supplies AFL *team games*,
never player disposals. A missing source field remains missing.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import threading
import time
import unicodedata
import zipfile

from .archive import Archive, data_directory, utc_now
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


class F1DBProvider(Provider):
    meta = ProviderMeta('f1db','F1DB','F1','driver race results', 'CC BY 4.0',
        'https://github.com/f1db/f1db/blob/main/LICENSE',
        '1950 onwards. All published race results, qualifying and fastest-lap times, championship standings and recorded pit stops. No invented telemetry.',
        'F1DB by Marcel Overdijk and contributors · https://github.com/f1db/f1db · CC BY 4.0. Fields renamed and records joined by GameSense.')

    def __init__(self):
        self._release = None
        self._zip_data = None
        self._release_checked = 0
        self._zip_tag = None
        self._force_release = False

    def release(self, client):
        if self._release is None or time.monotonic()-self._release_checked>3600 or self._force_release:
            self._release = client.get_json('https://api.github.com/repos/f1db/f1db/releases/latest', max_age=0 if self._force_release else 3600)
            self._release_checked=time.monotonic()
            self._force_release=False
        return self._release

    def available_seasons(self, client=None):
        # The release is authoritative; this avoids claiming future results.
        client = _client(client)
        tag = self.release(client)['tag_name']
        last = int(tag.lstrip('v').split('.')[0])
        return [str(y) for y in range(last, 1949, -1)]

    def _archive(self, client):
        release = self.release(client)
        if self._zip_data is None or self._zip_tag!=release['tag_name']:
            asset = next(a for a in release['assets'] if a['name'] == 'f1db-json-splitted.zip')
            self._zip_data = client.get_bytes(asset['browser_download_url'], max_age=86400*365)
            self._zip_tag=release['tag_name']
        return zipfile.ZipFile(io.BytesIO(self._zip_data))

    def download(self, archive, seasons, client=None, cancel=None, progress=None, force=False):
        if force:
            self._force_release=True
        return super().download(archive,seasons,client=client,cancel=cancel,progress=progress,force=force)

    @staticmethod
    def normalize_zip(zip_archive, seasons=None, release='unknown'):
        selected = set(map(str,seasons)) if seasons is not None else None
        def read(name):
            return json.loads(zip_archive.read('f1db-' + name + '.json'))
        drivers = {d['id']:d for d in read('drivers')}
        teams = {t['id']:t for t in read('constructors')}
        races = {r['id']:r for r in read('races')}
        def by_driver(name):
            return {(r['raceId'],r['driverId']):r for r in read(name)}
        qualifying = by_driver('races-qualifying-results')
        fastest = by_driver('races-fastest-laps')
        standings = by_driver('races-driver-standings')
        pits = defaultdict(list)
        for p in read('races-pit-stops'):
            pits[(p['raceId'],p['driverId'])].append({
                'stop':p.get('stop'),'lap':p.get('lap'),'duration_ms':p.get('timeMillis')})
        meta = F1DBProvider.meta
        for result in read('races-race-results'):
            if selected is not None and str(result['year']) not in selected:
                continue
            race = races[result['raceId']]
            driver = drivers[result['driverId']]
            team = teams[result['constructorId']]
            key = result['raceId'],result['driverId']
            q,fl,st = qualifying.get(key,{}),fastest.get(key,{}),standings.get(key,{})
            row = _base(meta,result['year'],
                record_id=f"f1db:race:{result['raceId']}:{result['driverId']}:{result['constructorId']}:{result['positionDisplayOrder']}",
                event_id=str(result['raceId']), date=race['date'],
                competitor_id='f1db:'+driver['id'], competitor=driver['name'],
                entity_type='athlete', team=team['name'], team_id='f1db:'+team['id'],
                competition='Formula 1 World Championship', record_kind='event',
                date_precision='day', position='Driver',nationality=driver.get('nationalityCountryId'),
                date_of_birth=driver.get('dateOfBirth'), round=race.get('round'),
                event=race.get('officialName'),circuit_id=race.get('circuitId'),
                circuit_layout_id=race.get('circuitLayoutId'),
                points=result.get('points'), finish_position=result.get('positionNumber'),
                classified_position=result.get('positionText'), grid_position=result.get('gridPositionNumber'),
                qualifying_position=result.get('qualificationPositionNumber'),
                laps=result.get('laps'),fastest_lap=int(result['fastestLap']) if result.get('fastestLap') is not None else None,
                wins=int(result.get('positionNumber') == 1), podiums=int(result.get('positionNumber') in (1,2,3)),
                pole_positions=int(result['polePosition']) if result.get('polePosition') is not None else None,
                retired=int(bool(result.get('reasonRetired'))), status=result.get('reasonRetired') or 'No retirement recorded',
                positions_gained=result.get('positionsGained'),race_time_ms=result.get('timeMillis'),
                qualifying_time_ms=q.get('timeMillis'),q1_ms=q.get('q1Millis'),q2_ms=q.get('q2Millis'),q3_ms=q.get('q3Millis'),
                fastest_lap_time_ms=fl.get('timeMillis'),fastest_lap_number=fl.get('lap'),
                championship_points=st.get('points'),championship_position=st.get('positionNumber'),
                pit_stops=result.get('pitStops'),pit_stop_events=pits.get(key,[]),
                tyre_manufacturer=result.get('tyreManufacturerId'),source_version=release)
            # Whole-career source totals are labelled separately from the local
            # downloaded-history totals; they are never summed across events.
            row['source_career'] = {k:v for k,v in driver.items() if k.startswith('total') or k.startswith('best')}
            yield row

    def iter_season(self, season, client, archive=None, force=False):
        with self._archive(client) as zipped:
            rows=[]
            for row in self.normalize_zip(zipped,[season],self.release(client)['tag_name']):
                rows.append(row)
                if len(rows)>=500:
                    client.check(); yield rows; rows=[]
            if rows:
                yield rows


class JolpicaProvider(Provider):
    meta = ProviderMeta('jolpica','Jolpica F1','F1','driver race results','CC BY-NC-SA 4.0',
        'https://github.com/jolpica/jolpica-f1/blob/main/TERMS.md',
        '1950 onwards. Alternative local noncommercial race results; use F1DB for redistributable archives. Coverage of laps and pit stops varies by era.',
        'Jolpica F1 · https://api.jolpi.ca · CC BY-NC-SA 4.0. Normalized by GameSense.')

    def available_seasons(self, client=None):
        data=_client(client).get_json('https://api.jolpi.ca/ergast/f1/seasons.json?limit=100&offset=0')
        return sorted([r['season'] for r in data['MRData']['SeasonTable']['Seasons']],reverse=True)

    def iter_season(self, season, client, archive=None, force=False):
        if not re.fullmatch(r'\d{4}',season):
            raise ValueError('Expected a four-digit F1 season.')
        offset=0
        while True:
            url=f'https://api.jolpi.ca/ergast/f1/{season}/results.json?limit=100&offset={offset}'
            data=client.get_json(url,max_age=0 if force else 86400)
            mr=data['MRData']; rows=[]
            for race in mr['RaceTable']['Races']:
                for result in race.get('Results',[]):
                    d=result['Driver']; t=result['Constructor']; fl=result.get('FastestLap',{})
                    position=_number(result.get('position'))
                    rows.append(_base(self.meta,season,
                        event_id=f"{season}:{race['round']}",date=race['date'],
                        competitor_id='jolpica:'+d['driverId'],competitor=d['givenName']+' '+d['familyName'],
                        team=t['name'],team_id='jolpica:'+t['constructorId'],entity_type='athlete',
                        competition='Formula 1 World Championship',record_kind='event',
                        nationality=d.get('nationality'),date_of_birth=d.get('dateOfBirth'),
                        event=race['raceName'],round=int(race['round']),circuit_id=race['Circuit']['circuitId'],
                        points=_number(result.get('points')),finish_position=position,
                        grid_position=_number(result.get('grid')),laps=_number(result.get('laps')),
                        wins=int(position==1),podiums=int(position in (1,2,3)),status=result.get('status'),
                        fastest_lap=int(fl['rank']=='1') if fl.get('rank') is not None else None,
                        fastest_lap_number=_number(fl.get('lap'))))
            if rows:
                yield rows
            actual=sum(len(r.get('Results',[])) for r in mr['RaceTable']['Races'])
            if actual==0 or offset+actual>=int(mr['total']):
                break
            offset+=actual


def _name_key(name):
    value=''.join(c for c in unicodedata.normalize('NFKD',name).casefold() if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]','',value)


class NBAProvider(Provider):
    meta = ProviderMeta('boxscorelab','BoxScore Lab','NBA','player season totals','CC BY 4.0',
        'https://boxscorelab.com/downloads/',
        '2022–23 onwards: published player season totals and derived rates. Earlier NBA history and game/shot data require another licensed provider or user import. Season rows are not individual games.',
        'BoxScore Lab · https://boxscorelab.com · CC BY 4.0; fetched date is stored with each row. Fields normalized by GameSense. NBA identifiers matched to the MIT-licensed nba_api static directory.')

    def __init__(self):
        self._ids=None

    def available_seasons(self, client=None):
        # Discover published files rather than advertise the whole NBA history.
        html=_client(client).get_bytes(self.meta.terms_url,max_age=3600,
            headers={'Accept':'text/html','User-Agent':'Mozilla/5.0 (compatible; GameSense/0.6.0)'}).decode('utf-8')
        return sorted(set(re.findall(r'(\d{4}-\d{2})-player-season-totals\.csv',html)),reverse=True)

    def identity_map(self, client):
        if self._ids is None:
            url='https://raw.githubusercontent.com/swar/nba_api/master/src/nba_api/stats/library/data.py'
            source=client.get_bytes(url,max_age=86400*30).decode('utf-8')
            tree=ast.parse(source)
            players=[]
            for node in tree.body:
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='players' for t in node.targets):
                    players=ast.literal_eval(node.value); break
            groups=defaultdict(list)
            for player in players:
                groups[_name_key(player[3])].append(str(player[0]))
            self._ids={k:v[0] for k,v in groups.items() if len(v)==1}
        return self._ids

    def iter_season(self, season, client, archive=None, force=False):
        if not re.fullmatch(r'\d{4}-\d{2}',season):
            raise ValueError('Expected an NBA season such as 2024-25.')
        url=f'https://boxscorelab.com/downloads/{season}-player-season-totals.csv'
        data=client.get_bytes(url,max_age=0 if force else 86400,
            headers={'User-Agent':'Mozilla/5.0 (compatible; GameSense/0.6.0)','Referer':self.meta.terms_url,'Accept':'text/csv,*/*'})
        identities=self.identity_map(client)
        rows=[]
        for item in csv.DictReader(io.StringIO(data.decode('utf-8-sig'))):
            name=item['player_name']; official_id=identities.get(_name_key(name))
            stable_id='nba:'+official_id if official_id else 'boxscorelab:name:'+hashlib.sha256(name.encode()).hexdigest()[:20]
            # This is an ordering key only, not a claimed game date.
            year=int(season[:4]); date=f'{year+1}-06-30'
            row=_base(self.meta,season,date=date,date_precision='season',record_kind='season_total',
                event_id=season,competitor_id=stable_id,competitor=name,team=item.get('team',''),
                entity_type='athlete',competition='NBA regular season',position=item.get('position'),
                source_url=url)
            for key,value in item.items():
                if key not in ('season','player_name','team','position'):
                    row[key]=_number(value)
            if official_id:
                row['nba_id']=official_id
            else:
                row['identity_warning']='Source supplies no player ID; unmatched name-based identity, verify namesakes.'
            rows.append(row)
        if rows:
            yield rows


class SquiggleProvider(Provider):
    meta=ProviderMeta('squiggle','Squiggle','AFL','team match results','Squiggle API terms',
        'https://api.squiggle.com.au/',
        'AFL team match results from 2000 onwards. Includes goals, behinds and margins. This source does not supply individual player disposals or advanced player statistics. Requires your contact email in the User-Agent.',
        'Squiggle API by Max Barry · https://api.squiggle.com.au/ · normalized team match results.',True)

    def available_seasons(self, client=None):
        # API changelog explicitly documents 2000–2010 added to newer seasons.
        return [str(y) for y in range(_current_year(),1999,-1)]

    def iter_season(self, season, client, archive=None, force=False):
        if not re.fullmatch(r'\d{4}',season):
            raise ValueError('Expected a four-digit AFL season.')
        contact=archive.setting('contact_email','') if archive else ''
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',contact):
            raise ValueError('Squiggle requires a valid contact email in its User-Agent. Add your contact email in Settings before downloading AFL team records.')
        headers={'User-Agent':f'GameSense desktop historical archive - {contact}'}
        data=client.get_json(f'https://api.squiggle.com.au/?q=games;year={season}',
            headers=headers,max_age=0 if force else 86400)
        rows=[]
        for game in data.get('games',[]):
            if int(game.get('complete',0))!=100:
                continue  # Do not treat scheduled or partial scores as results.
            for side,other in [('h','a'),('a','h')]:
                team_id=str(game[side+'teamid'] if side+'teamid' in game else game[side+'team'])
                name=game.get(side+'team')
                if isinstance(name,(int,float)):
                    name=game.get(side+'teamname',str(name))
                score=_number(game.get(side+'score')); against=_number(game.get(other+'score'))
                rows.append(_base(self.meta,season,event_id=str(game['id']),date=str(game['date'])[:10],
                    competitor_id='squiggle:team:'+team_id,competitor=str(name),team=str(name),
                    team_id='squiggle:team:'+team_id,entity_type='team',record_kind='event',
                    competition='AFL',event=f"{game.get('hteam')} v {game.get('ateam')}",
                    round=game.get('round'),venue=game.get('venue'),opponent=game.get(other+'team'),
                    points=score,points_against=against,goals=_number(game.get(side+'goals')),
                    behinds=_number(game.get(side+'behinds')),
                    margin=(score-against) if score is not None and against is not None else None,
                    wins=int(score>against) if score is not None and against is not None else None,
                    draws=int(score==against) if score is not None and against is not None else None,
                    is_final=bool(game.get('is_final')),is_grand_final=bool(game.get('is_grand_final'))))
        if rows:
            yield rows


class StatsBombProvider(Provider):
    meta=ProviderMeta('statsbomb','StatsBomb Open Data','Soccer','player match events','StatsBomb Public Data User Agreement — research/noncommercial, no raw redistribution',
        'https://github.com/hudl/open-data/blob/master/LICENSE.pdf',
        'Selected competitions/seasons only. Genuine event-derived player shots, xG, passing, assists, tackles and shot locations. Downloaded directly for local research; raw data is never bundled. Published analysis requires StatsBomb attribution and its logo.',
        'StatsBomb Open Data · https://github.com/hudl/open-data · StatsBomb Public Data User Agreement. Event counts aggregated by GameSense.')
    base='https://raw.githubusercontent.com/hudl/open-data/master/data/'

    def competitions(self, client=None):
        return _client(client).get_json(self.base+'competitions.json')

    def available_seasons(self, client=None):
        return sorted({str(c['season_name']) for c in self.competitions(client)},reverse=True)

    @staticmethod
    def aggregate_match(match, events, lineups):
        people={}
        for team in lineups:
            for p in team.get('lineup',[]):
                people[p['player_id']]={'name':p['player_name'],'team':team['team_name'],
                    'nationality':p.get('country',{}).get('name'),
                    'position':p.get('positions',[{}])[0].get('position') if p.get('positions') else None,
                    'positions':p.get('positions',[])}
        active={}
        def entry(identity, name, team):
            info=people.get(identity,{})
            return dict(competitor_id='statsbomb:'+str(identity),competitor=name,
                    team=team,nationality=info.get('nationality'),position=info.get('position'),
                    starts=int(any(p.get('start_reason')=='Starting XI' for p in info.get('positions',[]))) if info.get('positions') else None,
                    goals=0,assists=0,shots=0,shots_on_target=0,xg=0.,passes=0,passes_completed=0,
                    key_passes=0,progressive_passes=0,tackles=0,interceptions=0,clearances=0,
                    blocks=0,dribbles=0,dribbles_completed=0,fouls=0,cards=0,
                    goalkeeper_saves=0,shootout_goals=0,shot_events=[],pass_links=defaultdict(int))
        # Position intervals distinguish a substitute who played from an unused
        # bench player. Include actual appearances even with no ball events.
        for identity,info in people.items():
            if info.get('positions'):
                active[identity]=entry(identity,info['name'],info['team'])
        for event in events:
            p=event.get('player')
            if not p:
                continue
            identity=p['id']
            if identity not in active:
                active[identity]=entry(identity,p['name'],event.get('team',{}).get('name',''))
            row=active[identity]; kind=event.get('type',{}).get('name')
            # Shootout penalties decide the match but are not player match goals
            # or shots in standard football season statistics.
            if event.get('period')==5:
                if kind=='Shot' and event.get('shot',{}).get('outcome',{}).get('name')=='Goal':
                    row['shootout_goals']+=1
                continue
            if kind=='Shot':
                shot=event.get('shot',{}); outcome=shot.get('outcome',{}).get('name')
                row['shots']+=1; row['goals']+=int(outcome=='Goal')
                row['shots_on_target']+=int(outcome in ('Goal','Saved','Saved to Post'))
                # Provider xG is available per shot; absent shot xG remains unknown.
                xg=shot.get('statsbomb_xg')
                if xg is None:
                    row['xg']=None
                elif row['xg'] is not None:
                    row['xg']+=xg
                location=event.get('location')
                if location:
                    row['shot_events'].append({'x':location[0],'y':location[1],'xg':xg,
                        'outcome':outcome,'minute':event.get('minute'),'period':event.get('period'),
                        'body_part':shot.get('body_part',{}).get('name')})
            elif kind=='Pass':
                p=event.get('pass',{}); completed=not p.get('outcome')
                row['passes']+=1; row['passes_completed']+=int(completed)
                row['assists']+=int(bool(p.get('goal_assist')))
                row['key_passes']+=int(bool(p.get('shot_assist')))
                if completed and p.get('recipient'):
                    row['pass_links'][p['recipient']['name']]+=1
                # Custom definition is documented in data sources.
                start,end=event.get('location'),p.get('end_location')
                if completed and start and end and end[0]-start[0]>=10:
                    row['progressive_passes']+=1
            elif kind=='Duel' and event.get('duel',{}).get('type',{}).get('name')=='Tackle':
                row['tackles']+=1
            elif kind=='Interception': row['interceptions']+=1
            elif kind=='Clearance': row['clearances']+=1
            elif kind=='Block': row['blocks']+=1
            elif kind=='Dribble':
                row['dribbles']+=1
                row['dribbles_completed']+=int(event.get('dribble',{}).get('outcome',{}).get('name')=='Complete')
            elif kind=='Foul Committed': row['fouls']+=1
            elif kind=='Goal Keeper' and event.get('goalkeeper',{}).get('type',{}).get('name') in ('Shot Saved','Penalty Saved','Saved to Post'):
                row['goalkeeper_saves']+=1
            if event.get('foul_committed',{}).get('card') or event.get('bad_behaviour',{}).get('card'):
                row['cards']+=1
        for row in active.values():
            row['pass_accuracy']=row['passes_completed']/row['passes'] if row['passes'] else None
            row['pass_links']=dict(row['pass_links'])
            yield row

    def _match_rows(self, competition, match, client):
        match_id=match['match_id']
        events=client.get_json(self.base+f'events/{match_id}.json',max_age=86400*365)
        lineups=client.get_json(self.base+f'lineups/{match_id}.json',max_age=86400*365)
        return [_base(self.meta,competition['season_name'],event_id=str(match_id),date=match['match_date'],
            competition=competition['competition_name'],competition_id=str(competition['competition_id']),
            event=match['home_team']['home_team_name']+' v '+match['away_team']['away_team_name'],
            entity_type='athlete',record_kind='event',spatial_source='StatsBomb 120x80 event coordinates',
            **values) for values in self.aggregate_match(match,events,lineups)]

    def download_ronaldo_2022(self, archive, client=None, progress=None):
        """Fetch only Ronaldo's actual Portugal 2022 World Cup match records.

        This *does not* claim his entire career or any unauthorised competitions.
        Uses StatsBomb's publicly accessible research/noncommercial World Cup
        match/event files and never bundles/re-exports the raw source.
        """
        client=_client(client)
        catalogue=self.competitions(client)
        competition=next(
            (c for c in catalogue if int(c.get('competition_id',-1))==43
             and int(c.get('season_id',-1))==106),None)
        if competition is None:
            raise RuntimeError('2022 World Cup not in the live StatsBomb catalogue')
        matches=client.get_json(self.base+'matches/43/106.json')
        portugal=[m for m in matches
                  if 'portugal' in (
                      str((m.get('home_team') or {}).get('home_team_name',''))+' '+
                      str((m.get('away_team') or {}).get('away_team_name',''))
                  ).casefold()]
        if not portugal:
            raise ValueError('StatsBomb returned no Portugal World Cup 2022 matches.')
        records=[]
        for index,match in enumerate(portugal,1):
            client.check()
            all_rows=self._match_rows(competition,match,client)
            selected=[row for row in all_rows
                      if 'cristiano' in str(row.get('competitor','')).casefold()
                      and 'ronaldo' in str(row.get('competitor','')).casefold()]
            if selected:
                records.extend(selected)
                archive.upsert(selected)
            if progress:
                progress(index,len(portugal),
                         f'Portugal 2022 · {index}/{len(portugal)} real matches scanned')
        if not records:
            raise ValueError(
                'No verified Cristiano Ronaldo match record found in StatsBomb '
                'Portugal 2022 files. Nothing was invented.')
        archive.mark(self.meta.id,'Soccer','2022','partial',
                     'Cristiano Ronaldo Portugal World Cup matches only; '
                     'not all players, competitions or career seasons')
        return len(records)

    def download_match(self, archive, match_id, competition_id=43, season_id=106, client=None, cancel=None):
        """Download a genuine single match, retaining partial-season coverage."""
        client=_client(client,cancel)
        competition=next(c for c in self.competitions(client)
            if c['competition_id']==int(competition_id) and c['season_id']==int(season_id))
        matches=client.get_json(self.base+f'matches/{competition_id}/{season_id}.json')
        match=next(m for m in matches if m['match_id']==int(match_id))
        rows=self._match_rows(competition,match,client)
        result=archive.upsert(rows)
        archive.set_setting(f'statsbomb_match:{match_id}',True)
        archive.mark(self.meta.id,self.meta.sport,competition['season_name'],'partial',
            'Selected match downloaded; full season not downloaded.')
        return result

    def download_competition(self, archive, competition_id, season_id, client=None, cancel=None, progress=None):
        client=_client(client,cancel)
        competition=next(c for c in self.competitions(client)
            if c['competition_id']==int(competition_id) and c['season_id']==int(season_id))
        matches=client.get_json(self.base+f'matches/{competition_id}/{season_id}.json')
        count=0
        for index,match in enumerate(matches):
            client.check()
            marker=f"statsbomb_match:{match['match_id']}"
            if not archive.setting(marker,False):
                count+=archive.upsert(self._match_rows(competition,match,client))
                archive.set_setting(marker,True)
            if progress:
                progress(index+1,len(matches),f"{competition['competition_name']} · {match['match_date']}")
        archive.mark(self.meta.id,self.meta.sport,competition['season_name'],'partial',
            'Competition downloaded; other competitions may exist for this season.')
        return count

    def iter_season(self, season, client, archive=None, force=False):
        competitions=[c for c in self.competitions(client) if str(c['season_name'])==season]
        if not competitions:
            raise ValueError('This season is not in the StatsBomb Open Data catalogue.')
        for competition in competitions:
            matches=client.get_json(self.base+f"matches/{competition['competition_id']}/{competition['season_id']}.json")
            for match in matches:
                client.check()
                match_id=match['match_id']
                marker=f"statsbomb_match:{match_id}"
                if archive and not force and archive.setting(marker,False):
                    continue
                yield self._match_rows(competition,match,client)
                if archive:
                    # Runs only after consumer commits yielded records.
                    archive.set_setting(marker,True)


# Optional player-level sources extend coverage without altering the licensed
# seed archive or pretending unavailable historical years have been fetched.
from .extra_providers import NBAStatsHistoryProvider, APIFootballProvider

PROVIDERS={p.meta.id:p for p in [
    F1DBProvider(), NBAProvider(), NBAStatsHistoryProvider(),
    StatsBombProvider(), APIFootballProvider(), SquiggleProvider(), JolpicaProvider()
]}


def bootstrap(archive):
    return archive.seed_bundled()
