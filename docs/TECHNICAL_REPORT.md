# GameSense technical report

Engineering reference for version 0.6.0, prepared with AI assistance on 28 October 2026. This document describes implementation decisions and their limits. It is not a student's personal reflection or a completed validation response.

## Problem and audience

GameSense turns historical sporting records into searchable profiles, comparisons and visual explanations for sports fans, students and people learning data analysis. Football, NBA, AFL and Formula 1 share navigation, storage and chart controls while keeping sport-specific metrics and presentation. A race finishing position and a basketball point total have different meanings; comparing a universal score across sports would be misleading.

The original proposal describes the pipeline **sports data → validation → processing → calculation → analysis → visualisation**. This remains the application structure. The change from the proposed Streamlit/browser stack to PySide6/Qt supports the user's updated requirement for an installable desktop application with no Python or terminal needed by end users. Matplotlib supplies native embedded interactive figures; Pandas and NumPy handle tabular calculations.

## Architecture

| Component | Responsibility and rationale |
| --- | --- |
| `app.py` | Native application entry point and startup configuration. |
| `gamesense/window.py` | Qt navigation, search, athlete/team views, filters and download workers. Network and media processing belong in background workers so the event loop can continue painting and handling input. |
| `gamesense/archive.py` | Indexed SQLite archive. It stores stable identities and filter columns separately from flexible per-record JSON metrics. WAL and short committed batches support concurrent reading and resumable downloads. |
| `gamesense/providers.py` | Provider-specific normalization, coverage and attribution. A provider's available years do not imply equal detail in every year. |
| `gamesense/http.py` | Network transport, caching and provider request controls. |
| `gamesense/analytics.py` | Shared validation and explicit mathematical calculations. |
| `gamesense/charts.py` | Qt/Matplotlib figures, hover information, navigation toolbar and exports. |
| `gamesense/images.py` | Wikimedia identity lookup, rights metadata, cached portraits and original silhouette fallback. |
| `gamesense/demo.py` | Fictional records, used only in clearly identified demonstration mode. |
| `scripts/build.py` | Native executable and installer creation, original app icons, version metadata and checksums. |
| `scripts/check_package.py` | Isolated packaged startup and platform installer checks. |

SQLite is suitable because a single-user desktop library benefits from transactional updates and indexed queries without a separate server. A source record is identified independently of the displayed athlete name. This prevents two people with the same name being combined and retains team changes rather than overwriting a career with its most recent club.

## Database and user data

The archive contains `records`, `downloads` and `settings`. Records carry `record_id`, `sport`, `provider`, `season`, `date`, `competitor_id`, `competitor`, `team`, `entity_type`, `competition`, a JSON payload and an update time. Indexes support sport/season/date queries, identity queries and name searches. SQL values are bound parameters rather than interpolated user input.

Download status is stored per provider and season. Successful batches commit immediately; cancellation or a later network failure does not erase earlier batches. A partially downloaded season must not be described as complete. Coverage displays describe what is actually stored, not a hard-coded list of promised seasons. Queries use limits so opening a view does not require loading the complete archive into memory.

Default user data locations are `%LOCALAPPDATA%/GameSense` on Windows and `~/Library/Application Support/GameSense` on macOS. `GAMESENSE_DATA_DIR` provides an override for development and isolated testing. Downloaded archives and portraits are user data, separate from the installed application. Uninstalling the program should preserve that data; users can manage their local storage independently.

## Sources and historical coverage

The in-app provider information and actual archive coverage are the authoritative runtime record. Source terms, per-year availability and field-level coverage differ. A complete F1 result archive does not provide historical speed or tyre telemetry, and AFL club results are not AFL athlete statistics. No view may invent missing fields to fill a chart.

| Provider | Implemented data scope | Rights and limits |
| --- | --- | --- |
| F1DB | Race results from 1950 to the published release, with available qualifying, fastest-lap times, driver standings and recorded pit-stop lists | CC BY 4.0; requires credit and notice of transformations. No invented speed, sector or tyre telemetry. |
| BoxScore Lab | Published NBA player-season totals for 2022–23 through 2026–27, with counting/shooting fields and available derived rates | CC BY 4.0. This is five seasons, not the requested complete 1946-onward NBA history. Season dates are ordering anchors, not fabricated game dates. |
| StatsBomb Open Data | Selected football competitions/seasons and event-derived player measurements, including genuine shot coordinates where supplied | Research/noncommercial agreement; local downloads only. Required provider acknowledgement/branding applies to published analysis; no unrestricted raw-data redistribution is assumed. |
| Jolpica | Alternative historical Formula 1 race results | CC BY-NC-SA 4.0; local retrieval under those distinct terms, not bundled with the permissively redistributable F1DB seed. Requests are serialized conservatively. |
| Squiggle | Basic AFL team fixtures/results, goals/behinds, margins and outcomes | Team scope, not player scope. A real user contact email is required in the API request identity. No advanced Champion Data measurements are inferred. |

The redistributable bundled seed is documented in `data/SOURCE_MANIFEST.json` with source versions and transformations. In particular, the shipped NBA source does not satisfy an all-era historical athlete search; a query for an older player can correctly have no local statistics. AFL athlete profiles need a separately licensed athlete dataset. Those are remaining coverage gaps, not completed requirements.

Provider-backed downloads and user imports are separate provenance paths. Imports require the user to hold the relevant rights; accepting a CSV does not grant GameSense redistribution rights. Do not publish downloaded third-party datasets with a release unless their terms permit it and the required attribution accompanies them. See the source manifests beside any bundled dataset.

For new providers, implement stable identities, explicit record granularity (event, match, season totals or team results), source URLs, documented coverage, safe pagination, throttling, incremental persistence and cancellation before adding UI claims about that provider.

## Validation and missing values

Input columns are normalized, duplicates are detected, invalid dates and missing essential identity fields are rejected, and known numerical metrics are coerced to numbers. Missing numerical measurements remain `NaN`/SQL JSON `null`, never a fictional zero. Validation reports show how many rows were removed.

Different granularities must not be added together. A player-season total and that player's constituent games represent overlapping observations. Team records and athlete records are kept distinguishable with `entity_type`. Provider namespaces prevent accidental identity collisions. Imported names alone cannot prove that two rows refer to the same person.

## Calculations

| Quantity | Definition and missing-data rule |
| --- | --- |
| Total | Sum of known observed values for additive counting statistics. If none are present, the result is missing. Percentages and positions are not added. |
| Arithmetic mean | Sum of present values divided by the number of present observations. This must be labelled with its observation unit. |
| Weighted average | `sum(value × weight) / sum(weight)` over finite values with positive, known weights. Useful when season averages represent different numbers of games. |
| Per game | Known total divided by the matching known games played. A season-total row is not treated as one game. The result stays missing if the required denominator is unknown. |
| Recent form | Mean of up to the latest five observed ratings, ordered by event date, with missing ratings excluded. |
| Rolling average | Mean of the chosen preceding observation window, with window and metric shown on the chart. |
| Best performance | Maximum for higher-is-better counting metrics; minimum for finishing and grid positions. |
| Season change | `(new − old) / abs(old) × 100` only when both values exist and the earlier value is nonzero. Missing or zero baseline does not produce an infinite improvement. |
| Win percentage | Wins divided by the number of matches with a known result, multiplied by 100. A draw is not a win; missing results are excluded. |

The legacy GameSense custom rating is a weighted sum, not an official league rating. It is calculated only when all formula components are available; partial formulas would make athletes incomparable. Soccer weights are goals `5`, assists `3`, shots `0.4`, passes `0.025`, tackles `0.4`. NBA weights are points `1`, rebounds `1.2`, assists `1.5`, steals `2`, blocks `2`. AFL weights are disposals `0.65`, marks `1.1`, tackles `1.5`, goals `5`, clearances `1.4`. F1 weights are points `1`, finish position `−1.1`, grid position `−0.3`, fastest-lap indicator `3`. These are experimental design choices. They do not adjust for role, minutes, era, injury or rule changes and should not be used to claim an objective all-time best athlete.

The table also documents intended interpretation for future analytical extensions. Only calculations actually exposed by the current application should be represented as implemented; inspect the code and test report before relying on an additional metric.

## Visualisation decisions

Chart controls offer observed season trends, event timelines, rolling averages, rankings, distributions, scatter comparisons, radar comparisons, heatmaps, box plots and cumulative totals where the selected data can support them. Each chart needs a metric label, aggregation explanation, legend and useful empty-data message. Missing data is excluded transparently rather than filled with synthetic values. Toolbar pan/zoom and saved PNGs support exploration; CSV exports expose the observations or aggregates behind a displayed figure.

The four modes use emerald football, orange basketball, navy/gold AFL and red/metallic F1 palettes. Original vector pitch, court, oval and motorsport motifs communicate context without distributing protected team marks. Decorative field artwork is not a spatial performance map. Shot maps require real shot coordinates; passing networks require real passes with player identities; circuit telemetry requires real location/time/speed data. Without those inputs the interface must state the limitation and show an appropriate nonspatial alternative.

Dark surfaces, clear numerical hierarchy, distinct accents and bounded tables support legibility. Visual screenshots at several sizes provide evidence of clipping and layout quality; a screenshot alone does not prove correct statistics or interaction.

## Portraits, rights and ethics

Portrait lookup resolves a sport-relevant identity and inspects Wikimedia Commons image metadata rather than taking an arbitrary search image. Accepted sources need an explicitly permitted public-domain, CC0, CC BY or CC BY-SA licence. The system records source/description URLs, author/credit, licence URL, size and cache time. Source credit must remain visible with the portrait. A missing or ambiguous match, broken response or missing licence leads to an original silhouette.

Background loading prevents network delays from blocking the UI. Cached images work offline and retain attribution. A valid image URL is not itself evidence of permission. Team logos, league marks and athlete photography carry separate rights from match statistics. No AI-generated lookalike is presented as a real athlete photograph.

GameSense uses public sporting information rather than private addresses or contact details. Ratings and trends describe a historical sample and do not explain every cause of performance. The app is not a prediction guarantee or betting recommendation. Historical coverage and missingness can bias comparisons; users should compare similar scopes, roles and eras.

## Verification and release evidence

Run automated checks with `python -m pytest -q` after installing the development test dependency. Provider/archive tests should check stable identities, idempotent imports, per-batch persistence, interrupted downloads and missing data. Analytical tests should use small hand-checkable examples; image tests should check licence rejection, cache corruption and offline fallback. Qt rendering checks should open all main views, change filters, compare competitors and export figures.

Build commands and logs are evidence of packaging, not of a successful public installation. `scripts/check_package.py` exercises a packaged executable or a platform installer in an isolated location. Its JSON report explicitly separates automated startup from a manual interactive check. Windows checks can install, launch and uninstall silently. macOS checks mount a DMG and launch its bundled application on a Mac. Manual clean-machine review, trusted code signing, macOS notarisation and actual publication are separate milestones. Review `output/` reports and the development log for actual results; do not infer they passed from this document.

## Remaining limits and evaluation

The product should be evaluated against the actual downloaded data and observed test results. Complete coverage of every athlete, year and metric across four sports cannot be guaranteed from open sources. Providers can remove data, change terms or throttle requests. NBA and AFL player archives require particular care because accessible team results do not satisfy player-level coverage. Spatial events, lap sectors and telemetry exist only for some sources/eras. Free portrait metadata and identity matches are not available for everyone.

The original proposal's core outcomes remain the evaluation criteria: four sport choices; validated historical records; meaningful sport-specific calculations; graphs; competitor comparison; testing evidence; and documentation. Additional profiles, imagery and installable packages extend those outcomes. The student's own evaluation should identify what they personally tested, which limitations matter to their target audience, how decisions changed the original plan, and what they would improve next. No personal reflection has been fabricated here.

## References

Dates below are access dates for engineering research, not a claim that the student personally reviewed each source.

- Inno Setup (2026) *PrivilegesRequired*. Available at: https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm (Accessed: 28 October 2026).
- F1DB contributors (2026) *F1DB dataset and licence*. Available at: https://github.com/f1db/f1db/blob/main/LICENSE (Accessed: 28 October 2026).
- BoxScore Lab (2026) *Free NBA data downloads*, data through 26 October 2026. Available at: https://boxscorelab.com/downloads/ (Accessed: 28 October 2026).
- Hudl/StatsBomb (2026) *Open Data licence*. Available at: https://github.com/hudl/open-data/blob/master/LICENSE.pdf (Accessed: 28 October 2026).
- Squiggle (2026) *Squiggle API*. Available at: https://api.squiggle.com.au/ (Accessed: 28 October 2026).
- MediaWiki (2026) *API:Imageinfo*. Available at: https://www.mediawiki.org/wiki/API:Imageinfo (Accessed: 28 October 2026).
- pandas development team (2026) *pandas documentation*. Available at: https://pandas.pydata.org/docs/ (Accessed: 28 October 2026).
- PyInstaller development team (2026) *Using PyInstaller*. Available at: https://pyinstaller.org/en/stable/usage.html (Accessed: 28 October 2026).
- PyInstaller development team (2026) *Using spec files*. Available at: https://pyinstaller.org/en/stable/spec-files.html (Accessed: 28 October 2026).
- Qt Project (2026) *Qt for Python documentation*. Available at: https://doc.qt.io/qtforpython-6/ (Accessed: 28 October 2026).
- St Mary MacKillop College (2026) *Year 12 Digital Technologies T, Semester 2, Task 2: Major Project*, supplied assessment PDF, edited 17 August 2026.
- Dhiraj, D.K. (2026) *GameSense Independent Study Tertiary project proposal*, supplied proposal PDF.

Record AI use separately in `AI_ASSISTANCE.md`, and keep the student's own development evidence and teacher-shared progress record alongside the project.
