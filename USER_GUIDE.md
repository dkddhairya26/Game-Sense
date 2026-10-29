# GameSense user guide

GameSense is a native desktop application for Soccer, NBA, AFL and Formula 1.
It stores historical records on your computer and turns the selected records
into profiles, comparisons, calculations and charts. Coverage depends on the
source and downloaded seasons; a missing statistic is shown as unavailable.

## Install and start

Use the [official download page](https://dkddhairya26.github.io/Game-Sense/).
Check the version beside the download button. Older releases remain available
on [GitHub Releases](https://github.com/dkddhairya26/Game-Sense/releases).
Windows packages target x64. The macOS package targets Apple Silicon and
requires macOS 14 or later; an Intel package is not supplied. Beta packages
are unsigned and the Mac app is not notarised.

Install the Windows executable, or open the Mac DMG and copy GameSense to
Applications. Packaged users do not need Python or a terminal. First startup
loads the permitted starter data into a separate user archive. Allow this to
finish before judging search results.

## Select the records you mean

Choose a sport, competition and downloaded season in the top bar. Search
matches downloaded competitor names. The identity picker respects the
selected league and year. Different people with similar names retain their
source identifiers. A football club is separate from an individual player.

Open **Players & clubs** for a profile. For Aston Villa, select Premier League
history and then Championship history. **Show full downloaded club history**
opens the reconciled club across recorded leagues and seasons. Its statistics
are club matches, not an inferred roster or player goals. The season table
keeps each competition distinct; the match table shows dates, opponents,
scores and sources.

NBA player records supplied by the starter archive are season totals from
2022–23 onward. Per-game values use recorded games played; one season row is
not counted as one match. Older seasons require a successful optional NBA
Stats request or a permitted import. A year in a provider's request catalogue
does not prove the endpoint returned data.

AFL club records show match scores, goals, behinds and results when supplied.
Player disposals, kicks, handballs, marks and tackles need actual player
records; Squiggle team data cannot supply them. F1 profiles use race results,
with qualifying and pit-stop information only where recorded. A decorative
circuit does not represent telemetry.

## Read ratings and insights

The experimental GameSense rating is a documented 0–100 indicator calculated
from sport-specific recorded components. Use **How Is This Rating Calculated?**
to inspect the formula, references and limitations. It is not an official
league ranking and should not be compared between sports or treated as an
era-adjusted measure of ability. A missing required component gives no score.

Recent form means the latest eligible observations in the stated scope.
Season-only NBA records describe recorded seasons, not a player's last five
games. Statistical insights are deterministic descriptions of the selected
records. Read their period and source; they do not establish why performance
changed or predict the next result.

## Compare competitors

Open **Compare**, choose two competitors of the same sport and entity type,
then inspect the scope and source coverage. Football clubs compare to clubs;
NBA players to players; AFL clubs and AFL players use different metrics; F1
drivers compare to drivers and constructor views aggregate recorded drivers.
Totals can reflect different numbers of matches. Per-game averages, common
seasons, recent observations and missing components help interpret that
difference. An unavailable metric must not be read as zero.

## Use charts and export

The dashboard shows several sport-specific views simultaneously. Titles and
axis labels describe the selected metric and aggregation. The deep-dive chart
supports another metric or chart mode when the data permit it. Hover for
values, use the Matplotlib toolbar to pan or zoom, and export PNG or CSV from
the chart. A data-absent explanation is deliberate when a required field such
as shot coordinates is not recorded.

Portraits load asynchronously from identity-verified Wikimedia Commons
records with acceptable licences. Their credits remain available with cached
images offline. A silhouette means the image is unavailable or uncertain;
it is not an invented photograph. Athlete photos do not imply that every
season in their career is downloaded.

## Import your own permitted dataset

Use the import action in the application, choose the sport and a CSV, JSON or
Excel `.xlsx` file, then review the **Data Quality Report**. Required fields
are a competitor name and season. Common aliases such as `player`, `year`,
`pts`, `reb` and `ast` are normalized. Supply real match dates where possible.
Date-free season rows receive an explicitly labelled ordering marker, not a
claimed match date. Label season totals and per-game averages correctly and
supply games played for correct denominators.

The report explains input, valid, duplicate, rejected and cleaned rows,
missing values, conversions and database changes. Invalid essential identity,
dates or impossible scoring values are rejected; optional missing
measurements remain missing. Re-importing the same source does not create a
new copy of every observation. Export the report to retain the audit trail.
You must hold the necessary rights to use or redistribute your file.

## Download, work offline and recover

**Data manager** lists each source's actual scope and terms. Discover its
catalogue before selecting years or competitions. Downloading commits saved
batches incrementally, so cancellation or a network error preserves completed
work. Read the saved coverage status before describing a season as complete.
An active season contains only results supplied so far.

API-Football requires your own account key, entered in the app for the current
session. Access depends on the plan and endpoint; no subscription or broad
redistribution permission is bundled. Squiggle requires a valid contact
email for its request identity. These settings are not part of release data.

Enable offline mode in Settings to use downloaded data and cached portraits.
Downloads cannot retrieve new records while offline. If a page is empty,
clear the competition/season filter, check the source's local coverage and
confirm the entity type. A provider failure is not proof a competitor never
played. Restricted or absent histories may require another permitted source.

User data are separate from the installation:

| System | Default folder |
| --- | --- |
| Windows | `%LOCALAPPDATA%/GameSense` |
| macOS | `~/Library/Application Support/GameSense` |

Back up this folder before manually changing local files. The developer
override `GAMESENSE_DATA_DIR` can isolate a testing archive. Do not share an
archive containing private credentials, contact settings or restricted data.

## Run from source

Developers can install dependencies and launch the same native application:

```sh
python -m pip install -r requirements.txt
python app.py
```

See [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) for tests and builds,
[DATA_SOURCES.md](DATA_SOURCES.md) for coverage and [ALGORITHMS.md](ALGORITHMS.md)
for mathematical definitions.
