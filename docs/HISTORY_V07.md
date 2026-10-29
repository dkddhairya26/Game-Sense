# GameSense 0.7 development: scope and acceptance checklist

This branch is a real implementation upgrade on top of **v0.6.0-beta.1**. It is
not yet a publicly signed production release. The existing v0.6 download page
still points to v0.6 until a separately verified version is published.

## What actually changed

- Seven simultaneous chart panels on each sport dashboard: six different
  fixed sport-specific views plus a customizable interactive deep-dive. These
  show only observed metrics from the local archive; missing values are not
  replaced with sample statistics.
- An optional `NBA Stats (historical, on demand)` provider requests player
  seasons going back to 1946–47, including pre-2022, via `nba_api`.
  Seasons are **request candidates**, not a guarantee the NBA endpoint returns
  them. API restrictions and era-dependent statistics remain significant.
- An optional authenticated `API-Football` source adds multi-league season
  discovery, real player ID lookup, player career downloads and league-level
  downloads. Each user must supply their **own API key**. GameSense does not
  store it, bundle it, or display it in logs.
- A simple free `GET REAL CRISTIANO RONALDO · WORLD CUP 2022` button uses
  StatsBomb's 2022 FIFA World Cup event data for Portugal matches. These are
  **real World Cup observations only**: they do *not* amount to Cristiano
  Ronaldo's complete senior career. The original StatsBomb restrictions apply.
- Existing portrait cards continue to use verified Wikimedia Commons licence
  and artist details; photographs are not silently copied from commercial
  API-Football profile URLs.
- Fixture tests cover the provider parsing, players with duplicate surnames,
  same-player transfers, historical NBA season normalization and partial
  coverage of a World Cup player.

## Historical source coverage

| Source | Dataset grain | Earliest candidates / coverage | Restrictions |
| --- | --- | --- | --- |
| F1DB | Driver/event | 1950–latest supplied release | CC BY 4.0 attribution |
| NBA BoxScore Lab bundled | NBA player-season totals | 2022–23 onward where supplied | CC BY 4.0 attribution; no older seasons |
| NBA Stats via nba_api, opt-in | Player-season averages | Requestable 1946–47 onwards; **not guaranteed accessible** | NBA-controlled source; no redistributable bundle |
| StatsBomb Open Data | Selected event/match/competition player data | Provider's actual published catalogue | Research/noncommercial; no bulk redistribution |
| API-Football optional | Player-league-team-season statistics | Provider and account-plan dependent | User API key and provider rights required |
| Squiggle | AFL club match scores | Provider catalogue, team results only | No AFL player-disposal history |
| Jolpica F1 optional | Driver/race result | 1950 onward where recorded | Noncommercial terms distinct from F1DB |

**Known gaps**: no legally sourced complete Ronaldo club-career feed is bundled;
no complete historical AFL player database; no guaranteed NBA access to all
1946 onward seasons; no fabricated shot positions/telemetry; downloadable
datasets and images must comply with each source's licence. The presence of
`available_seasons()` is not proof every year has a valid result.

## Test the real functionality

1. Launch GameSense and select NBA. In Data Manager choose NBA Stats
   (historical, on demand), discover years and request a pre-2022 season
   (for example 1995–96). Confirm an actual provider response, not only that
   1995–96 appears in the dropdown. If NBA.com blocks requests, GameSense
   reports failure and retains previous cached data.
2. Select Soccer → Data Manager → Get Real Cristiano Ronaldo · World Cup
   2022. Confirm the resulting profile is labelled Portugal / World Cup
   and only contains the observed matches.
3. To research Ronaldo's other club years, provide a valid API-Football
   account key; search `Ronaldo`, distinguish Cristiano Ronaldo (Portugal)
   from Ronaldo Nazário (Brazil) using provider IDs, and download only the
   seasons the subscription permits.
4. Open every sport dashboard. Confirm six independent fixed chart panels
   plus the custom chart, with different labels and explicit data-absent
   states rather than made-up graphs.
5. Run `python -m pytest -q` and `python app.py --smoke-test --screenshots
   output/screenshots`. The screenshot workflow for this development branch
   runs under GitHub Actions on Ubuntu; Windows and macOS installer checks are
   separate.

## Privacy and ethical data handling

- Never enter an API key into a GitHub file, bug report or screenshot.
- The API-Football key is stored only in runtime memory. HTTP caches use a
  nonreversible credential fingerprint for separation, never the secret.
- Downloaded statistics stay in the local per-user GameSense archive.
- Respect StatsBomb's noncommercial access and attribution conditions. Public
  installer redistribution does not automatically grant redistribution rights
  for downloaded sports data or photos.
- A verified portrait is optional, with a labelled original silhouette if
  no suitably licensed, identity-verified image is found.

## Remaining roadmap

1. Verify a successful pre-2022 NBA Stats response from an ordinary Windows
   internet connection; otherwise secure a licensed/redistributable source.
2. Obtain rights for comprehensive historic league/player databases where
   free sources are incomplete, including Ronaldo's full club career.
3. Source legally reusable AFL player-season statistics, not just team matches.
4. Run complete Windows + Mac packaged installers; inspect new screenshots
   and publish a separate clearly labelled v0.7 beta only after the tests.
