"""Offline regression tests for identity, resumability, rights and real event math."""
import gzip
import io
import json
import sqlite3
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import pandas as pd

from gamesense.archive import Archive
from gamesense.http import HttpClient, Cancelled
from gamesense.providers import Provider, ProviderMeta, StatsBombProvider, NBAProvider

ROOT=Path(__file__).resolve().parents[1]


def record(identity='source:1', name='Same Name', season='2020', event='1', **extra):
    row=dict(sport='F1',provider='test',season=season,date=season+'-05-01',
        competitor_id=identity,competitor=name,team='Team A',event_id=event,points=10)
    row.update(extra)
    return row


class TemporaryTest(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'.qa'; parent.mkdir(exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(dir=parent)
        self.directory=Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()


class ArchiveTests(TemporaryTest):
    def setUp(self):
        super().setUp()
        self.archive=Archive(self.directory/'archive.db')

    def test_upsert_is_idempotent_and_updates_only_matching_record(self):
        self.archive.upsert([record(),record(event='2')])
        self.archive.upsert([record(points=15)])
        self.assertEqual(self.archive.count('F1'),2)
        self.assertEqual(self.archive.query('F1')['points'].sum(),25)

    def test_same_names_remain_distinct_stable_identities(self):
        self.archive.upsert([record('source:1'),record('source:2')])
        self.assertEqual(len(self.archive.search('F1','Same Name')),2)
        self.assertEqual(len(self.archive.query('F1',competitor_id='source:1')),1)

    def test_filters_pagination_and_counts_agree(self):
        self.archive.upsert([record(event='1'),record(event='2'),record(season='2021')])
        self.assertEqual(self.archive.count('F1',season='2020'),2)
        first=self.archive.query('F1',season='2020',limit=1)
        second=self.archive.query('F1',season='2020',limit=1,offset=1)
        self.assertNotEqual(first.iloc[0]['record_id'],second.iloc[0]['record_id'])
        self.assertEqual(self.archive.seasons('F1'),['2021','2020'])
        self.assertEqual(self.archive.stats('F1')['competitors'],1)

    def test_literal_search_does_not_interpret_sql_wildcards(self):
        self.archive.upsert([record(name='100% Name'),record(identity='source:2',name='Other')])
        self.assertEqual(len(self.archive.search('F1','%')),1)
        self.assertEqual(len(self.archive.search('F1',"' OR 1=1 --")),0)

    def test_coverage_does_not_claim_partial_as_complete(self):
        self.archive.upsert([record()])
        self.archive.mark('test','F1','2020','partial','Only one event')
        self.assertFalse(self.archive.completed('test','2020'))
        self.assertEqual(self.archive.coverage('F1')[0]['record_count'],1)
        self.archive.mark('test','F1','2020','complete')
        self.assertTrue(self.archive.completed('test','2020'))

    def test_same_import_source_keeps_independent_coverage_per_sport(self):
        self.archive.mark('common.csv','NBA','2020','complete')
        self.archive.mark('common.csv','F1','2020','partial')
        self.assertEqual(len(self.archive.coverage()),2)
        self.assertTrue(self.archive.completed('common.csv','2020','NBA'))
        self.assertFalse(self.archive.completed('common.csv','2020','F1'))

    def test_legacy_coverage_schema_migrates_without_losing_download_history(self):
        path=self.directory/'legacy.db'
        con=sqlite3.connect(path)
        con.execute('CREATE TABLE downloads(provider TEXT,sport TEXT,season TEXT,status TEXT,record_count INTEGER,updated TEXT,error TEXT,PRIMARY KEY(provider,season))')
        con.execute('INSERT INTO downloads VALUES(?,?,?,?,?,?,?)',('test','F1','2020','complete',5,'2024-01-01',''))
        con.commit(); con.close()
        migrated=Archive(path)
        self.assertTrue(migrated.completed('test','2020','F1'))
        self.assertEqual(migrated.coverage()[0]['record_count'],5)
        migrated.mark('test','NBA','2020','partial')
        self.assertEqual(len(migrated.coverage()),2)

    def test_missing_and_nonfinite_statistics_preserved_as_missing(self):
        self.archive.upsert([record(points=float('nan'),laps=None)])
        row=self.archive.query('F1').iloc[0]
        self.assertTrue(pd.isna(row['points']))
        self.assertTrue(pd.isna(row['laps']))

    def test_invalid_record_rejected_before_any_batch_commit(self):
        with self.assertRaisesRegex(ValueError,'ISO date'):
            self.archive.upsert([record(),record(event='2',date='not-a-date')])
        self.assertEqual(self.archive.count('F1'),0)

    def test_import_preserves_other_seasons_and_source_identity(self):
        self.archive.upsert([record()])
        frame=pd.DataFrame([dict(date='2024-01-01',season='2024',competitor='Imported',team='T',points=9)])
        self.archive.import_frame('NBA',frame,'User-file.csv')
        self.archive.import_frame('NBA',frame,'User-file.csv')
        self.assertEqual(self.archive.count('F1'),1)
        self.assertEqual(self.archive.count('NBA'),1)
        self.assertIn('identity_warning',self.archive.query('NBA').columns)

    def test_corrected_import_updates_same_event_instead_of_duplicating(self):
        frame=pd.DataFrame([dict(date='2024-01-01',season='2024',competitor='Imported',team='T',points=9)])
        self.archive.import_frame('NBA',frame,'source.csv')
        frame.loc[0,'points']=12
        self.archive.import_frame('NBA',frame,'source.csv')
        self.assertEqual(self.archive.count('NBA'),1)
        self.assertEqual(self.archive.query('NBA').iloc[0]['points'],12)

    def test_exported_id_reimport_cannot_relabel_or_overwrite_original_source(self):
        self.archive.upsert([record(record_id='provider-original')])
        export=self.archive.query('F1')
        export.loc[0,'points']=99
        self.archive.import_frame('F1',export,'export.csv')
        self.assertEqual(self.archive.count('F1'),2)
        original=self.archive.query('F1',provider='test')
        self.assertEqual(original.iloc[0]['points'],10)
        self.assertEqual(self.archive.query('F1',provider='export.csv').iloc[0]['points'],99)

    def test_import_accepts_nullable_pandas_and_nested_missing_values(self):
        frame=pd.DataFrame([dict(date='2024-01-01',season='2024',competitor='Imported',team=pd.NA,
            points=pd.NA,details={'unknown':float('nan'),'values':[pd.NA,None]})])
        self.archive.import_frame('NBA',frame,'nullable.csv')
        row=self.archive.query('NBA').iloc[0]
        self.assertIsNone(row['team'])
        self.assertIsNone(row['details']['unknown'])
        self.assertEqual(row['details']['values'],[None,None])

    def test_seed_inserts_do_not_replace_fresher_downloaded_records(self):
        self.archive.upsert([record(record_id='seed-id',points=30)])
        changed=self.archive.upsert([record(record_id='seed-id',points=10)],overwrite=False)
        self.assertEqual(changed,0)
        self.assertEqual(self.archive.query('F1').iloc[0]['points'],30)

    def test_deleting_football_season_clears_only_absent_match_checkpoints(self):
        self.archive.upsert([record(sport='Soccer',provider='statsbomb',event_id='100'),
            record(sport='Soccer',provider='statsbomb',season='2021',event_id='200')])
        self.archive.set_setting('statsbomb_match:100',True)
        self.archive.set_setting('statsbomb_match:200',True)
        self.archive.delete_season('Soccer','2020','statsbomb')
        self.assertFalse(self.archive.setting('statsbomb_match:100',False))
        self.assertTrue(self.archive.setting('statsbomb_match:200',False))

    def test_storage_delete_scoped_to_provider_and_season(self):
        self.archive.upsert([record(),record(provider='other'),record(season='2021')])
        self.archive.delete_season('F1','2020',provider='test')
        self.assertEqual(self.archive.count('F1'),2)

    def test_preferences_roundtrip_does_not_require_global_files(self):
        self.archive.set_setting('favorites',['source:1'])
        self.assertEqual(self.archive.setting('favorites'),['source:1'])
        self.assertEqual(self.archive.setting('absent',[]),[])


class FixtureProvider(Provider):
    meta=ProviderMeta('test','Fixture','F1','race results','test','https://example.org','fixture','fixture')
    def __init__(self,cancel_midway=False):
        self.calls=0
        self.cancel_midway=cancel_midway
    def iter_season(self,season,client,archive=None,force=False):
        self.calls+=1
        yield [record(season=season)]
        if self.cancel_midway:
            client.cancel.set()
            client.check()
        yield [record(season=season,event='2')]


class ResumeTests(TemporaryTest):
    def test_completed_closed_seasons_are_not_requested_again(self):
        archive=Archive(self.directory/'archive.db')
        provider=FixtureProvider(); client=HttpClient(self.directory/'cache')
        provider.download(archive,['2020'],client=client)
        provider.download(archive,['2020'],client=client)
        self.assertEqual(provider.calls,1)
        self.assertEqual(archive.count('F1'),2)

    def test_cancel_commits_first_batch_then_resume_upserts_without_duplicates(self):
        archive=Archive(self.directory/'archive.db')
        provider=FixtureProvider(cancel_midway=True); cancel=threading.Event()
        client=HttpClient(self.directory/'cache',cancel=cancel)
        with self.assertRaises(Cancelled):
            provider.download(archive,['2020'],client=client,cancel=cancel)
        self.assertEqual(archive.count('F1'),1)
        self.assertEqual(archive.coverage()[0]['status'],'cancelled')
        provider.cancel_midway=False; cancel.clear()
        provider.download(archive,['2020'],client=client,cancel=cancel)
        self.assertEqual(archive.count('F1'),2)
        self.assertTrue(archive.completed('test','2020'))


class Response(io.BytesIO):
    headers={}


class HttpTests(TemporaryTest):
    def client(self,**kwargs):
        client=HttpClient(self.directory/'cache',**kwargs)
        client._throttle=lambda host:None
        client.pause=lambda seconds:None
        return client

    def test_cache_reused_offline_without_network(self):
        client=self.client()
        with patch('gamesense.http.urlopen',return_value=Response(b'{"real":true}')) as call:
            self.assertEqual(client.get_json('https://example.org/data'),{'real':True})
            self.assertEqual(client.get_json('https://example.org/data'),{'real':True})
            self.assertEqual(call.call_count,1)
        offline=self.client(offline=True)
        with patch('gamesense.http.urlopen',side_effect=AssertionError('network not allowed')):
            self.assertEqual(offline.get_json('https://example.org/data'),{'real':True})

    def test_429_retry_is_bounded_and_then_returns_real_response(self):
        failure=HTTPError('https://example.org/data',429,'throttled',{'Retry-After':'1'},None)
        with patch('gamesense.http.urlopen',side_effect=[failure,Response(b'[]')]) as call:
            self.assertEqual(self.client().get_json('https://example.org/data'),[])
            self.assertEqual(call.call_count,2)

    def test_404_not_retried(self):
        failure=HTTPError('https://example.org/data',404,'missing',{},None)
        with patch('gamesense.http.urlopen',side_effect=failure) as call:
            with self.assertRaisesRegex(OSError,'404'):
                self.client().get_json('https://example.org/data')
            self.assertEqual(call.call_count,1)

    def test_cancelled_client_never_opens_network(self):
        event=threading.Event(); event.set()
        with patch('gamesense.http.urlopen') as call:
            with self.assertRaises(Cancelled):
                self.client(cancel=event).get_json('https://example.org/data')
            self.assertFalse(call.called)

    def test_non_https_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'HTTPS'):
            self.client().get_json('http://example.org/data')

    def test_response_size_is_bounded(self):
        with patch('gamesense.http.urlopen',return_value=Response(b'123456789')):
            with self.assertRaisesRegex(ValueError,'size limit'):
                self.client().get_bytes('https://example.org/data',max_bytes=5)


class FootballMathTests(unittest.TestCase):
    def shot(self,period=1,xg=.2):
        return dict(player={'id':5503,'name':'Messi'},team={'name':'Argentina'},period=period,
            type={'name':'Shot'},location=[100,40],shot={'outcome':{'name':'Goal'},'statsbomb_xg':xg},minute=23)

    def test_shootout_goals_excluded_from_match_totals(self):
        row=list(StatsBombProvider.aggregate_match({},[self.shot(),self.shot(period=5)],[]))[0]
        self.assertEqual(row['goals'],1)
        self.assertEqual(row['shots'],1)
        self.assertEqual(row['shootout_goals'],1)
        self.assertEqual(row['xg'],.2)
        self.assertEqual(len(row['shot_events']),1)

    def test_missing_shot_xg_is_not_zero(self):
        row=list(StatsBombProvider.aggregate_match({},[self.shot(xg=None)],[]))[0]
        self.assertIsNone(row['xg'])

    def test_lineup_includes_zero_touch_participant_but_excludes_unused_bench(self):
        lineup=[dict(team_name='Argentina',lineup=[
            dict(player_id=1,player_name='Starter',positions=[{'start_reason':'Starting XI','position':'Goalkeeper'}]),
            dict(player_id=2,player_name='Unused',positions=[])])]
        rows=list(StatsBombProvider.aggregate_match({},[],lineup))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['starts'],1)
        self.assertEqual(rows[0]['goals'],0)


class BundledDataTests(unittest.TestCase):
    def test_seed_has_only_permitted_providers_with_genuine_source_metadata(self):
        seed=ROOT/'data'/'seed.jsonl.gz'
        if not seed.exists():
            self.skipTest('Release seed not present')
        manifest=json.loads((ROOT/'data'/'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
        counts={}; first_year=9999; lebron=False
        with gzip.open(seed,'rt',encoding='utf-8') as stream:
            for line in stream:
                row=json.loads(line)
                self.assertIn(row['provider'],('f1db','boxscorelab'))
                self.assertEqual(row['license'],'CC BY 4.0')
                self.assertTrue(row['source_url'].startswith('https://'))
                counts[row['sport']]=counts.get(row['sport'],0)+1
                if row['sport']=='F1':
                    first_year=min(first_year,int(row['season']))
                elif row['competitor_id']=='nba:2544':
                    lebron=True
                    self.assertEqual(row['record_kind'],'season_total')
                    self.assertEqual(row['date_precision'],'season')
        self.assertEqual(counts,manifest['records'])
        self.assertEqual(first_year,1950)
        self.assertTrue(lebron)


if __name__=='__main__':
    unittest.main()
