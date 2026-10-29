# GameSense v0.8.0 — Real football leagues + AFL box-score preview

**Native Windows / Mac preview — source-backed, no fictional sports history.**

## This version directly addresses the user's screenshots

- The Football home screen previously had only **35** Portugal/World Cup
  event records. The v0.8 installer builds an additional, automatically
  imported **CC0 European club results library**, with completed matches from
  the Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Eredivisie and
  Portuguese Primeira Liga for published league-seasons from 2015–16 to
  2025–26. The CI build refuses to publish if fewer than 7,500 real team
  records from five leagues and five seasons are available. Earlier seasons,
  more national leagues and supported divisions can be downloaded from the
  Data Manager without an API key.
- **Important:** OpenFootball is a **team fixture / score** provider. Every
  participating club is included in available league-season match files, but
  it cannot identify the match players, goalscorers, assists or lineups.
  Those require a genuinely player-level licensed/authorised source.
  Cristiano Ronaldo's real Portugal 2022 World Cup match data and optional
  API-Football player records remain separate.
- The AFL screen previously had a sizeable club-results archive but most
  graphs said "stat not available". The AFL dashboard now automatically
  uses the club data actually present: final points scored, points conceded,
  goals, behinds, margin, draws, wins and season trajectories. These are
  actual AFL team results, not pretend individual disposals.
- New **opt-in AFL player-game research archive**. With a clear warning about
  the data's origin and original rights, users may locally download the
  public [AFL Data Analysis](https://github.com/akareen/AFL-Data-Analysis)
  research repository, which includes many historical player-match box scores
  (kicks, marks, handballs, disposals, goals, tackles, etc.). It is NOT
  bundled, due to underlying AFL Tables-derived dataset permissions being
  independently unverified. It may be large and requires a network connection.
  Early seasons lack many categories of measurements.
- Sport dashboards distinguish **TEAM match rows vs ATHLETE rows** and
  choose relevant chart modes based on the actual dataset rather than
  forcing player-disposal charts onto club scores.
- All older F1DB, NBA, user imports and existing local database files are
  retained; new soccer starter seed imports without deleting prior records.

## Source coverage and permissions

| Sport | Source | Grain and coverage | Caveat |
|---|---|---|---|
| Football | [OpenFootball football.json](https://github.com/openfootball/football.json), **CC0** | Club match results for many European leagues and published 2015–26 starter seasons | NO player stats, current/live data depends on contributors |
| Football | [StatsBomb Open Data](https://github.com/statsbomb/open-data) | Player match events for selected published competitions | Public research agreement, not worldwide club careers |
| Football | API-Football (optional account key) | Real player/league/team season aggregates where plan allows | Account, coverage and commercial rights restrictions |
| AFL | [Squiggle](https://api.squiggle.com.au/) | AFL club match scores, ~2000 onward where recorded | No individual AFL player stats |
| AFL | [AFL Data Analysis](https://github.com/akareen/AFL-Data-Analysis), **opt-in** | Historical player-game statistics from repository records | Original AFL Tables rights need review; never bundled for public redistribution |
| NBA | BoxScore Lab | Recent public NBA player seasons, 2022–23 onward | Older NBA years require a separately accessible provider |
| NBA | Official NBA Stats optional | Requestable 1946–47 onward historical player seasons | NBA endpoint can block access; no guaranteed career completeness |
| F1 | F1DB | Driver race results since 1950 where recorded | No complete historical telemetry |

## What is still not complete

GameSense cannot honestly guarantee every player in every league in every
historical season. OpenFootball supplies **clubs**, not individual footballers.
Full club-career statistics for Ronaldo still require an appropriate
player-level source and licence; the paid football API is not automatically
configured for public users. The optional AFL archive covers what its public
research publisher recorded and does not establish original data rights.
Many historic player-specific measurements were never captured.

## Testing / distribution

- GitHub Actions builds an actual CC0 football starter archive **before**
  native Windows/macOS installers, and fails if coverage is too sparse.
- All automated tests, native screen captures and packaged smoke checks
  must pass before the prerelease is published.
- Binaries are unsigned. Windows SmartScreen and macOS Gatekeeper may warn.
- End users need no Python, VS Code or Git; downloaded datasets are stored
  in the user's local SQLite archive.
