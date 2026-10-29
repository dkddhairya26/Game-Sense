"""Developer CLI for real historical downloads and redistributable seed creation.

Examples:
  python scripts/download_archive.py f1db --all --data-dir artifacts/qa
  python scripts/download_archive.py boxscorelab --all --data-dir artifacts/qa
  python scripts/download_archive.py statsbomb --seasons 2022 --data-dir artifacts/qa
  python scripts/download_archive.py --build-seed

Seed includes only F1DB and BoxScore Lab (CC BY 4.0). Research-only sources and
personal API caches are never copied into distribution assets.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
import os
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))

from gamesense.archive import Archive, utc_now
from gamesense.http import HttpClient
from gamesense.providers import PROVIDERS, F1DBProvider


def build_seed():
    output=ROOT/'data'; output.mkdir(exist_ok=True)
    cache=ROOT/'artifacts'/'download-cache'
    client=HttpClient(cache)
    f1=PROVIDERS['f1db']; nba=PROVIDERS['boxscorelab']
    counts=Counter(); years={}; now=utc_now()
    release=f1.release(client)
    with gzip.open(output/'seed.jsonl.gz','wt',encoding='utf-8',compresslevel=9) as stream:
        with f1._archive(client) as zipped:
            for row in f1.normalize_zip(zipped,release=release['tag_name']):
                stream.write(json.dumps(row,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
                counts['F1']+=1
                years.setdefault('F1',set()).add(row['season'])
        for season in nba.available_seasons(client):
            print('NBA',season,flush=True)
            for batch in nba.iter_season(season,client):
                for row in batch:
                    stream.write(json.dumps(row,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
                    counts['NBA']+=1
                    years.setdefault('NBA',set()).add(row['season'])
    manifest={'created_utc':now,'records':dict(counts),'seasons':{k:sorted(v) for k,v in years.items()},
        'sources':[{'provider':p.meta.id,'name':p.meta.name,'license':p.meta.license,
                    'terms_url':p.meta.terms_url,'attribution':p.meta.attribution} for p in [f1,nba]],
        'f1db_version':release['tag_name'],
        'changes':'Fields renamed; F1 race results joined to driver/constructor identities, qualifying, fastest laps, pit stops, standings and source career totals. NBA season totals normalized and mapped to unique NBA identifiers where unambiguous. No fabricated records. Source fields may be missing.',
        'warning':'Data is provided as-is. Coverage is not uniform by era. NBA dates are season ordering keys, not game dates. No research-only StatsBomb or personal API data bundled.'}
    (output/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    # Retain original licenses and notices next to the redistributable data.
    for name,url in [('F1DB-LICENSE.txt','https://raw.githubusercontent.com/f1db/f1db/main/LICENSE'),
                     ('NBA_API-MIT-LICENSE.txt','https://raw.githubusercontent.com/swar/nba_api/master/LICENSE')]:
        (output/name).write_bytes(client.get_bytes(url,max_age=86400*365))
    print(json.dumps(manifest,indent=2),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('provider',choices=PROVIDERS,nargs='?')
    parser.add_argument('--all',action='store_true')
    parser.add_argument('--seasons',nargs='+')
    parser.add_argument('--data-dir',default=str(ROOT/'artifacts'/'qa'))
    parser.add_argument('--force',action='store_true')
    parser.add_argument('--contact-email')
    parser.add_argument('--build-seed',action='store_true')
    args=parser.parse_args()
    if args.build_seed:
        build_seed(); return
    if not args.provider:
        parser.error('Choose a provider or --build-seed.')
    target=Path(args.data_dir).resolve(); os.environ['GAMESENSE_DATA_DIR']=str(target)
    archive=Archive(target/'archive.sqlite3')
    if args.contact_email:
        archive.set_setting('contact_email',args.contact_email)
    provider=PROVIDERS[args.provider]
    client=HttpClient(target/'http-cache')
    seasons=provider.available_seasons(client) if args.all else args.seasons
    if not seasons:
        print('Available seasons:',', '.join(provider.available_seasons(client))); return
    print(provider.meta.attribution,flush=True)
    result=provider.download(archive,seasons,client=client,force=args.force,
        progress=lambda done,total,message:print(f'{done}/{total} {message}',flush=True))
    print('Saved',result,'records.',archive.stats(provider.meta.sport),flush=True)


if __name__=='__main__':
    main()
