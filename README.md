# GameSense Desktop — Historical Edition (v0.4 development)

GameSense is a **native PySide6 desktop application** for Windows and macOS. There is no Streamlit server and no browser-based analytics interface.

## What the desktop application does

- Four distinct sports interfaces: **Soccer/Pitch, NBA/Court, AFL/Oval and F1/Race**.
- A premium dark dashboard with original vector sporting diagrams and six analytical visualisations: trends, leaderboards, stat breakdown, season history, sport-specific analytics and metric completeness.
- Searchable, sortable rankings, head-to-head comparisons, season filtering and an event/player data explorer.
- **Real, on-demand historical records** from supported data providers (not included in the installer).
- Controlled downloads of **up to five seasons at a time** to reduce API abuse; repeat to build a local archive.
- Import CSV, Excel and JSON with common player, team, year and stat header aliases.
- Store downloaded/imported statistics locally in SQLite and export filtered records.
- Clearly distinguish fictional offline demo records from downloaded records.

## Coverage — what is and is not available

| Sport | Included real-data connector | Record grain | Available history | Limits |
|---|---|---|---|---|
| Soccer | OpenLigaDB | Bundesliga team/match result | 1963 onwards **where recorded** | Only Germany's Bundesliga, **not player-level**; no advanced xG feed |
| NBA | NBA Stats via nba_api | One player-season row of *per-game averages* | Connector requests from 1996 onward | NBA endpoints may throttle/block; advanced stats vary by era |
| AFL | Squiggle API | Australian rules **team** match results | Approximately 2000 onward | Requires user-supplied contact email in request User-Agent. No player stats via Squiggle |
| F1 | Jolpica F1 | Driver race results | 1950 onward where recorded | Historical qualifying/laps/telemetry are not all present |

**No provider can supply every historical statistic, every player and every year.** The application never fills unknown historical fields with made-up numbers. Use authorised source files to expand historical athlete coverage; check any provider's licensing before using those data in a publicly distributed product.

Jolpica is non-commercial CC BY-NC-SA 4.0; [Jolpica terms](https://github.com/jolpica/jolpica-f1/blob/main/TERMS.md). Squiggle requires user identification and responsible caching; [Squiggle API](https://api.squiggle.com.au/). [nba_api source](https://github.com/swar/nba_api). [OpenLigaDB](https://www.openligadb.de/).

### Importing historical data

The Data Studio recognises headers such as `Player`, `Player Name`, `Club`, `Year`, `Match Date`, `PTS`, `REB`, `AST`, and common AFL abbreviations. It preserves additional numeric columns where possible.

For season-summary files without real match dates, it uses January 1 of the season strictly as a **chronological sorting marker**. It sets `date_is_marker=True` and labels the rows as season aggregates. These markers are **not actual match dates**.

To use the example desktop application without network access, GameSense loads **fictional demo data**. Demo players and teams do not represent real results and are labelled as such.

### Formula notes

GameSense ratings are illustrative formulas, **not official league ratings**. Soccer team-match records use an explicit wins/draws/goals/goal-difference score; AFL team matches use wins/draws/score margin. NBA player-season ranking metrics are weighted by games played when combining season averages. See `gamesense/analytics.py` for definitions.

## For ordinary Windows and Mac users

Download the Windows installer or macOS DMG from an **actual published GameSense Release**. An installer includes Python and application dependencies — users do **not** need VS Code, Python or Git. Mac unsigned builds can show security warnings; code signing/notarisation has not yet been completed.

The download page is at https://dkddhairya26.github.io/Game-Sense/ . **Do not claim a public installer is available until both release assets are attached and verified.**

Downloaded/imported data are stored on the user's computer under `~/GameSenseData/gamesense.sqlite3`; raw provider requests occur only when the user initiates a download.

AFL Squiggle's required contact email is sent as the identifying request User-Agent only for AFL downloads. GameSense does not store the email.

## Developer instructions

From a developer checkout, install Python 3.12 and run:

```bash
python -m pip install -r requirements.txt pytest
python -m pytest -q
python app.py
```

```bash
# Headless UI verification on CI (requires Qt system libraries)
QT_QPA_PLATFORM=offscreen PYTHONPATH=. python tests/render_preview.py
```

The `Verify GameSense UI and analytics` workflow validates parsers and generates desktop screenshots, while `Build public installers` creates platform builds on version tags or manual workflow runs. A successful build is **not** equivalent to testing the installer on a real user's Windows or Mac system.

## Project scope and credits

Based on the Year 12 Independent Study GameSense proposal: four sports, clean/validate/process data, sport-specific indicators, graphs, rankings, comparisons, seasonal filtering and documentation. Supports historical expansion through provider modules and imports.

This is an independent educational sports analytics project, not affiliated with the NBA, AFL, FIA, Formula 1 or soccer leagues. No official league crests, trademarks or copyrighted photos are bundled. Preserve provider attribution and source licences in any public distribution.
