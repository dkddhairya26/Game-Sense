# GameSense

Native desktop sports analytics for **football/soccer, NBA, AFL and Formula 1**. GameSense combines a local historical archive, real source records, athlete/team exploration, licensed portraits where available and interactive Matplotlib figures inside PySide6/Qt. It does not run a website or require a local web server.

Version **[0.6.0-beta.1](https://github.com/dkddhairya26/Game-Sense/releases/tag/v0.6.0-beta.1)** is a published preview, built from commit `920f3af` after native Windows and macOS checks passed. Earlier releases are preserved. Coverage is determined by the selected provider and records actually downloaded; it does **not** include every athlete, metric or historical event across all four sports. AFL team results remain labelled as team results. Missing measurements and unavailable telemetry are not fabricated. Fictional records are confined to an explicitly labelled demonstration mode.

## GameSense v0.9 — Club profiles fixed across leagues and years

Aston Villa (historical "Aston Villa" and current "Aston Villa FC") now uses
one stable, country-scoped CLUB identity, shared across the Premier League
and Championship seasons. Upgrading an existing archive reconciles old IDs
without erasing actual match data. The "Players & clubs" explorer displays
real club W/D/L, scores, goal difference, league points, dated fixtures and
season-by-league match summaries, instead of empty athlete-only goals/xG
boxes. "Show full downloaded club history" ignores the global season/league
filter for a verified career overview. The identity picker itself honours
the selected league/year.

Installer packaging also requests the **CC0 OpenFootball** completed club
match results for published 2010–11 to 2026–27 seasons, spanning both top
divisions and supported second divisions. Upstream files vary by year. The
source contains *club results only*, not each footballer's lineups, goals,
assists or xG. For player-specific records, use separate approved athlete
providers. Other sports and optional AFL player source remain available.

See [v0.9 release notes](docs/RELEASE_NOTES.md) for precise rights and
coverage limitations. Tests validate the actual Aston Villa EPL +
Championship career profile in the packaged native application.

## GameSense v0.8 — historic European clubs and AFL athlete stats

The v0.8 development branch addresses reports that Football showed only
35 World Cup records and AFL showed six mostly empty graphs:

- A CC0 **real team/match** starter archive is generated during installer
  packaging. It contains completed Premier League, La Liga, Bundesliga,
  Serie A, Ligue 1, Eredivisie and Primeira Liga fixtures from **published
  2015–16 through 2025–26 files** (league-year availability varies). The
  installer build **fails** if at least 7,500 team rows spanning five seasons
  and five leagues cannot be sourced. Additional league histories are
  available in the Data Manager via the new OpenFootball source. These
  records contain **clubs and scores**, NOT individual player records.
- AFL team scores from Squiggle are now shown correctly as scoring charts:
  goals, behinds, points for/against, goal margins, wins, and season trends.
- User-initiated AFL player-game history is optionally retrievable from the
  public [AFL Data Analysis research project](https://github.com/akareen/AFL-Data-Analysis)
  with provenance and a permissions warning. The dataset was assembled from
  AFL Tables and its original data rights are not independently verified for
  redistribution; GameSense does **not** bundle it.
- The optional authenticated API-Football integration remains necessary for
  broader club-level footballer careers (for example Cristiano Ronaldo).
  OpenFootball team scores cannot substitute for Ronaldo's player goals.

**No provider guarantees every league, every player, every season or every
statistic.** Missing historic measurements remain missing. See
[the v0.8 release notes](docs/RELEASE_NOTES.md) for the precise coverage.

| Sport/source | Implemented scope | Material limit |
| --- | --- | --- |
| F1 / F1DB | Published race-result history from 1950, joined available qualifying, fastest laps, standings and pit stops; CC BY 4.0 | Race records are not a complete telemetry archive. Latest source release/seed details are in `data/SOURCE_MANIFEST.json`. |
| F1 / Jolpica | Alternative locally downloaded historical race results | CC BY-NC-SA terms differ from F1DB; not included as a redistributable default dataset. |
| NBA / BoxScore Lab | Published player-season totals, 2022–23 to 2026–27; CC BY 4.0 | No 1946-onward NBA player archive or Michael Jordan career history is supplied by this source. A season row is not an individual game. |
| Soccer / StatsBomb Open Data | Catalogue-backed selected competitions, real event-derived player statistics and shot coordinates | Research/noncommercial terms; no raw data bundled for redistribution. It is not every league or every season. |
| AFL / Squiggle | Completed club match results from the supported catalogue; contact email required in request identity | Team results only. Player disposals, tackles and career archives need an appropriately licensed user import or another provider. |

Read provider terms before enabling downloads or distributing derived work. Free public access and permission to redistribute are separate questions.

## Use the desktop application

Public download page: **https://dkddhairya26.github.io/Game-Sense/**. Download buttons activate only when GitHub confirms matching published release assets:

- [Windows x64 installer](https://github.com/dkddhairya26/Game-Sense/releases/download/v0.6.0-beta.1/GameSenseSetup-Windows.exe)
- [macOS Apple Silicon disk image](https://github.com/dkddhairya26/Game-Sense/releases/download/v0.6.0-beta.1/GameSense-macOS.dmg)

Both packages passed automated native startup and installation/mount checks on
their target OS; reports and checksums accompany the public release. The Mac app
is **arm64 for Apple Silicon**. Its bundled dependencies require **macOS 14+**;
the package was tested on macOS 26, not on every earlier compatible version. An
Intel Mac package is not supplied. Builds are not trusted-code-signed or notarised,
and manual interactive clean-machine testing remains unverified.

Once a native package is installed, users need no Python, Git, VS Code or terminal. Internet is required to retrieve additional data and portraits; downloaded records and cached images remain accessible offline.

## Explore

The sidebar opens Home, the selected sport dashboard, Profiles, Compare, Teams, Leaderboards, Historical Explorer, Data Downloads, Settings and About/Sources. Changing sports changes the typography treatment, palette and original pitch/court/oval/racing artwork.

Use Data Downloads to inspect a provider's scope and discover its real catalogue. Download all available years or a selected historical range, update recent seasons, cancel a running job and resume it later. Saved batches remain on disk. Search is over the downloaded archive, with stable identities keeping same-name athletes separate. An absent player may indicate missing source coverage or an archive that has not been downloaded.

Profiles present permitted portraits, available career metrics, team history, season records and trends. Comparisons use the selected identities and actual available metrics. Charts offer season trends, event timelines, rolling averages, rankings, distributions, scatter comparisons, radar comparisons, heatmaps, box plots and cumulative totals where the data supports them. Hover, pan/zoom and PNG/CSV export are available. A silhouette is used when no identity-verified, explicitly licensed portrait can be obtained.

Exploration uses bounded database queries: dashboards and teams work with a visible subset, profiles cap their loaded records, and the raw explorer pages through the archive. Read the displayed scope before treating a figure as a complete all-time aggregate. A field illustration is decorative unless genuine coordinates are present; GameSense does not invent shot locations, passes or racing telemetry.

## Run from source

Use a supported Python installation with the dependencies available for your platform (CI targets Python 3.12):

```sh
python -m pip install -r requirements.txt
python app.py
```

On Windows `py` can replace `python`. Developers can isolate user data with `GAMESENSE_DATA_DIR`; normal storage is `%LOCALAPPDATA%/GameSense` on Windows and `~/Library/Application Support/GameSense` on macOS. Downloads and image caches are stored separately from the application installation.

CSV/Excel imports must include `date`, `season`, `competitor` and `team`; numerical fields depend on the sport. Provider records include stable IDs, provenance and explicit entity/record types. Missing statistics remain missing. Importing a file does not confer redistribution rights.

## Verification and packaging

```sh
python -m pip install pytest
python -m pytest -q
python app.py --smoke-test
python app.py --smoke-test --screenshots output/screenshots
python scripts/build.py --dry-run
python scripts/build.py --installer
```

Build on the target operating system. Windows installer creation requires Inno Setup 6; `GAMESENSE_ISCC` can point to a compiler or it may be placed in `tools/inno/ISCC.exe`. `python scripts/build.py` builds the executable/app without an installer. macOS uses its native `hdiutil` to create a DMG. Build scripts generate original application icons, version metadata, build reports and SHA-256 files. They do not publish or obtain signing credentials.

To check an existing Windows executable or installer:

```sh
python scripts/check_package.py --application dist/GameSense/GameSense.exe
python scripts/check_package.py --installer output/GameSenseSetup-Windows.exe
```

On macOS use `--installer output/GameSense-macOS.dmg`. Checks run with isolated data and native offscreen startup; Windows can also verify silent install/uninstall. They do not replace visible clean-machine testing.

The release workflow tests and builds on Windows/macOS, uploads artifacts and
publishes a **new prerelease** for an explicitly pushed matching version tag after
both platform jobs succeed. It refuses to overwrite an existing release and
leaves the latest stable release unchanged. Manual workflow runs build artifacts
without publishing. The Pages workflow serves `docs/`; its public download tag is
updated only after the new installer assets exist.

## Documentation

- [Technical architecture, algorithms, data ethics and limits](docs/TECHNICAL_REPORT.md)
- [Assessment and proposal alignment](docs/ASSESSMENT_ALIGNMENT.md)
- [AI assistance disclosure and student review record](docs/AI_ASSISTANCE.md)
- [Development evidence log](docs/DEVELOPMENT_LOG.md)
- [Actual verification results and outstanding release checks](docs/VERIFICATION.md)
- [Build, review and public release instructions](PUBLIC_RELEASE_GUIDE.md)

The assessment's separate supervised No AI validation has not been written here. AI-assisted code and documentation require the student's own review and acknowledgement under their teacher-approved conditions.

## Attribution

Provider records retain source and licence metadata; permitted bundled datasets need accompanying source manifests. Wikimedia Commons portraits retain author, source and licence information. Original field artwork and the GameSense icon do not reproduce official team or league marks. PySide6, Pandas, NumPy, Matplotlib, OpenPyXL, Pillow and PyInstaller retain their respective licences. Packaging these dependencies does not remove their redistribution obligations.
