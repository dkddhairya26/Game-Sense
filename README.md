# GameSense

Native desktop sports analytics for **football/soccer, NBA, AFL and Formula 1**. GameSense combines a local historical archive, real source records, athlete/team exploration, licensed portraits where available and interactive Matplotlib figures inside PySide6/Qt. It does not run a website or require a local web server.

Version 0.6.0 is a **preview engineering upgrade**, prepared locally for review against the repository's newer public releases. It has not been published by these local edits. Coverage is determined by the selected provider and the records actually downloaded. It does **not** claim every athlete, statistic or historical event across all four sports. AFL team results remain labelled as team results; missing metrics and unavailable spatial/telemetry data are not fabricated. Fictional records are available only through an explicitly labelled demonstration mode.

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

- Windows: `GameSenseSetup-Windows.exe`
- macOS: `GameSense-macOS.dmg`

Installers and publication are separate from source availability. A configured workflow is not evidence that a working Mac build or public release has been produced. Inspect the release notes, package check reports and checksums for an actual release. Builds are not trusted-code-signed; macOS notarisation is not configured.

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
