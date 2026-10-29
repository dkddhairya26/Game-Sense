"""Regression tests for real historical NBA and authenticated football records.

No tests call external providers, assume paid access, or fabricate source success.
All sample data here are isolated fixed fixtures, NOT distributed sports records.
"""
from __future__ import annotations

import pandas as pd
import pytest

from gamesense.providers import PROVIDERS
from gamesense.extra_providers import NBAStatsHistoryProvider, APIFootballProvider
from gamesense.archive import Archive


def test_nba_historical_seasons_go_back_before_2022():
    supported=NBAStatsHistoryProvider.available_seasons()
    assert supported[-1]=='1946-47'
    assert '1995-96' in supported
    assert '2023-24' in supported
    assert all(len(item)==7 for item in supported)


def test_nba_player_identity_and_actual_stat_grain():
    frame=pd.DataFrame([{
        'PLAYER_ID':893, 'PLAYER_NAME':'Example Athlete', 'TEAM_ID':99,
        'TEAM_ABBREVIATION':'EX', 'GP':82, 'PTS':31.0, 'REB':6.6,
        'AST':5.7,'FG_PCT':.52,'FGM':11.0,'FGA':21.2,
        'STL':None, 'BLK':None,
    }])
    rows=NBAStatsHistoryProvider.parse_frame(frame,'1995-96')
    assert len(rows)==1
    row=rows[0]
    assert row['competitor_id']=='nba:893'
    assert row['season']=='1995-96'
    assert row['record_kind']=='season_per_game_average'
    assert row['games']==82
    assert row['points']==31.0
    assert row['field_goal_pct']==.52
    assert 'steals' not in row and 'blocks' not in row
    assert row['source_url'].startswith('https://')


def test_nba_advanced_is_separate():
    base=pd.DataFrame([{'PLAYER_ID':123,'PLAYER_NAME':'Example','TEAM_ID':1,
                        'TEAM_ABBREVIATION':'EX','GP':18,'PTS':22}])
    extra=pd.DataFrame([{'PLAYER_ID':123,'USG_PCT':.28,'NET_RATING':5.2}])
    parsed=NBAStatsHistoryProvider.parse_frame(base,'2024-25',extra)
    assert parsed[0]['advanced_usg_pct']==.28
    assert parsed[0]['advanced_net_rating']==5.2


def _football_player(player_id=874,team='Real Madrid',league='La Liga'):
    return {
        'player':{
            'id':player_id,'name':'Cristiano Ronaldo',
            'nationality':'Portugal', 'birth':{'date':'1985-02-05'}
        },
        'statistics':[
            {'team':{'id':85,'name':team},
             'league':{'id':140,'name':league,'country':'Spain'},
             'games':{'appearences':33,'lineups':33,'minutes':2800,'rating':'7.8'},
             'goals':{'total':35,'assists':10},'shots':{'total':180,'on':80},
             'passes':{'total':31,'key':18,'accuracy':82},
             'tackles':{'total':5,'interceptions':2,'blocks':1},
             'cards':{'yellow':4,'red':0}}
        ]
    }


def test_ronaldo_is_source_id_not_fake_alias():
    records=APIFootballProvider.normalize_player(_football_player(),'2016')
    assert len(records)==1
    record=records[0]
    assert record['competitor']=='Cristiano Ronaldo'
    assert record['competitor_id']=='api-football:874'
    assert record['team']=='Real Madrid'
    assert record['competition']=='La Liga'
    assert record['season']=='2016'
    assert record['goals']==35 and record['assists']==10
    assert record['date_precision']=='season'
    assert record['record_kind']=='season_total'
    assert 'photo_url' not in record


def test_football_transfers_are_separate_records():
    original=_football_player()
    original['statistics'].append({
        'team':{'id':33,'name':'Manchester United'},
        'league':{'id':39,'name':'Premier League','country':'England'},
        'games':{'appearences':8,'minutes':600},
        'goals':{'total':2,'assists':1}})
    rows=APIFootballProvider.normalize_player(original,'2022')
    assert len(rows)==2
    assert rows[0]['record_id']!=rows[1]['record_id']
    assert all(r['competitor_id']=='api-football:874' for r in rows)


def test_search_produces_exact_provider_player_ids(monkeypatch):
    p=APIFootballProvider()
    def fake(route,params=None,client=None):
        assert route=='players/profiles'
        return {'response':[
            {'player':{'id':874,'name':'Cristiano Ronaldo',
                       'nationality':'Portugal','birth':{'date':'1985-02-05'}}},
            {'player':{'id':12,'name':'Ronaldo',
                       'nationality':'Brazil','birth':{'date':'1976-09-18'}}}
        ]}
    monkeypatch.setattr(p,'_request',fake)
    results=p.search_profiles('Ronaldo')
    assert len(results)==2
    assert results[0]['id']==874
    assert results[1]['id']==12
    assert results[0]['nationality'] != results[1]['nationality']


def test_api_key_is_not_required_for_test_fixture_but_production_does():
    p=APIFootballProvider()
    with pytest.raises(RuntimeError,match='own key'):
        p._request('players/profiles',{'search':'Ronaldo'})
    p.set_api_key('my-local-test-key')
    assert p.api_key=='my-local-test-key'


def test_football_player_archive_stores_partial_seasons(tmp_path,monkeypatch):
    p=APIFootballProvider()
    db=Archive(tmp_path/'test_archive.sqlite3')
    monkeypatch.setattr(p,'player_seasons',lambda player_id,client:[2016,2017])
    monkeypatch.setattr(p,'_pages',lambda params,client: iter([_football_player()]))
    class Client:
        def check(self): pass
    result=p.download_player(db,874,client=Client())
    assert result['records']==2
    assert set(db.seasons('Soccer'))=={'2016','2017'}
    assert db.count('Soccer',competitor_id='api-football:874')==2
    assert all(item['status']=='partial' for item in db.coverage('Soccer'))


def test_sources_registered_but_bundling_not_misrepresented():
    assert 'nba_stats' in PROVIDERS
    assert 'api_football' in PROVIDERS
    assert PROVIDERS['api_football'].meta.sport=='Soccer'
    assert 'paid' in PROVIDERS['api_football'].meta.license.lower()


def test_statsbomb_free_ronaldo_2022_does_not_fake_club_career(tmp_path,monkeypatch):
    from gamesense.providers import StatsBombProvider
    db=Archive(tmp_path/'g.sqlite3')
    provider=StatsBombProvider()
    monkeypatch.setattr(provider,'competitions',lambda client:[
        {'competition_id':43,'season_id':106,'season_name':'2022',
         'competition_name':'FIFA World Cup'}])
    class Client:
        def check(self): pass
        def get_json(self,url):
            assert url.endswith('/matches/43/106.json')
            return [
                {'match_id':1,'home_team':{'home_team_name':'Portugal'},
                 'away_team':{'away_team_name':'Uruguay'}},
                {'match_id':2,'home_team':{'home_team_name':'France'},
                 'away_team':{'away_team_name':'Spain'}},
            ]
    monkeypatch.setattr(provider,'_match_rows',lambda competition,match,client:[
        {'sport':'Soccer','provider':'statsbomb','season':'2022',
         'date':'2022-11-28','record_id':'mock-world-cup-ronaldo',
         'competitor_id':'statsbomb:fake-source-player-id',
         'competitor':'Cristiano Ronaldo dos Santos Aveiro',
         'team':'Portugal','competition':'FIFA World Cup','goals':0}
    ])
    count=provider.download_ronaldo_2022(db,client=Client())
    assert count==1
    assert db.count('Soccer')==1
    assert 'Portugal' in db.query('Soccer').iloc[0]['team']
    assert db.coverage('Soccer')[0]['status']=='partial'


def test_dashboard_uses_six_simultaneous_visuals():
    # The source must define a grid of *different* chart instances, not
    # merely add options to a single graph's type selector.
    import inspect
    from gamesense.window import GameSenseWindow
    source=inspect.getsource(GameSenseWindow._build_dashboard)
    assert 'self.dash_visuals.append((caption, chart))' in source
    source=inspect.getsource(GameSenseWindow._plot_dashboard)
    assert all(mode in source for mode in ['Season trend','Distribution','Ranking',
                                          'Scatter','Radar','Box plot'])
