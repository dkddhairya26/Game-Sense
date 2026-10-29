# GameSense technical documentation

Engineering reference for the final assessment development branch, based on
the released v0.9 source `fa44c59dfa6b970cdaf744c75cbb1c4587ca7e37`.
Written with AI assistance on 29 October 2026. Implementation evidence and
test results are separate from the student's own reflection.

## Problem and architecture

The proposal asks how a single platform can process and visualise different
sporting data to compare performance and reveal trends (Dhiraj, 2026, pp. 1–5).
The shared structure is **collect → validate → clean → persist → calculate →
analyse → visualise**. Sport-specific functions preserve the meaning of club
results, player season totals and driver race records.

| Module | Purpose and design rationale |
| --- | --- |
| `app.py` | Native Qt entry point, isolated smoke mode and screenshot capture. |
| `gamesense/window.py` | Routes, filters, loading states, profiles, comparisons, dashboards and background jobs. |
| `gamesense/archive.py` | SQLite persistence, indexed identity/filter queries, source attribution, seed loading and coverage checkpoints. |
| `gamesense/provider_base.py` | Provider contracts and independently committed download batches; shared base prevents circular imports. |
| `gamesense/providers.py` | F1DB, BoxScore Lab, StatsBomb, Squiggle and Jolpica normalization/registry. |
| `gamesense/openfootball_provider.py` | Completed club matches from published CC0 league files. |
| `gamesense/club_identity.py` | Country-scoped club names and reviewed aliases across divisions. |
| `gamesense/extra_providers.py` | Optional NBA Stats and user-key API-Football requests. |
| `gamesense/afl_player_provider.py` | Explicitly opt-in third-party AFL research parsing; no redistribution assumption. |
| `gamesense/importers.py` | User-file normalization, validation and the Data Quality Report. |
| `gamesense/analytics.py` | Grain-aware totals, per-game denominators, weighted percentages, season tables and rankings. |
| `gamesense/team_analytics.py` | Observed club W/D/L, scoring, venue splits, recent form and streaks. |
| `gamesense/ratings.py` | Explainable experimental 0–100 indicators with fixed references and required components. |
| `gamesense/insights.py` | Deterministic statements derived from stored records with period and source. |
| `gamesense/charts.py` | Embedded Qt/Matplotlib charts, hover, navigation, PNG and underlying-data CSV exports. |
| `gamesense/images.py` | Verified Wikimedia identity/licence lookup, asynchronous cache and silhouette fallback. |
| `scripts/build.py` / `scripts/check_package.py` | Native packaging, checksums and isolated target-platform startup/install checks. |
| `scripts/package_submission.py` | Committed source plus reviewed evidence and verified packages, excluding personal archives. |

SQLite needs no separate server and offers transactions, indexes and a single
portable archive suitable for a local application (SQLite, n.d.). Each record
stores indexed sport/provider/season/date/identity fields plus a JSON payload.
The latter accommodates different sports without creating hundreds of empty
columns. The trade-off is that calculations on optional payload fields often
need a bounded Pandas query rather than a simple indexed SQL aggregation.

`record_id` identifies an observation; `competitor_id` identifies the source
entity. Names are presentation fields, not safe global primary keys. Records
retain transfers, competitions and source URLs. Reviewed OpenFootball aliases
carry Aston Villa through the Premier League and Championship while country
scoping reduces accidental collisions. Unknown aliases need review; fuzzy
name equality does not establish identity.

## Validation and calculations

Imports normalize headers before changing data and reject ambiguous aliases.
Essential identity/date failures and invalid scores are reported, duplicates
are detected, known numeric fields are converted, and missing optional
statistics remain `NaN`/JSON `null`. The quality report records processing and
persistence outcomes separately. Dates assigned for season sorting explicitly
state their precision and must not appear as invented fixtures.

`metric_summary` distinguishes additive totals from non-additive positions,
rates and percentages. A player season total is divided by matching known
games rather than by the number of season rows. Percentages use actual
attempts where available. Club match functions accept team records with both
scores; they do not total league standings snapshots or infer player goals.
See [ALGORITHMS.md](ALGORITHMS.md) for formulas, hand-checkable examples and
limitations.

The experimental rating replaces the legacy raw weighted formula; the public
`rating` compatibility column uses the same normalized calculation.
It uses fixed, explained reference values and only calculates when every
required component is available. An insight is a deterministic description,
not generated sports commentary or an inferred cause of performance.

## Responsiveness, cache and failure handling

Qt's event loop handles input and painting. Network/download/portrait work
runs in worker threads and returns via queued signals, avoiding direct widget
mutation from a worker (Qt Project, n.d.). Providers check cancellation and
commit small batches, so a later error does not erase saved observations.
Coverage distinguishes saved status from universal source completeness.

Tables use Qt models and bounded database queries. This limits startup work,
but a displayed subset cannot be called a complete all-time population.
Profiles and charts must state their scope. Source availability, latency and
licensed coverage vary; an empty response is not a fictional successful
download. Offline mode reuses records and cached images without requiring
new data requests.

Wikidata resolves a sport-relevant athlete identity before requesting its
Commons image. Accepted metadata require an explicit permitted licence,
source and author. Cache hashes detect corrupted bytes; uncertain identity
or missing rights leaves an original silhouette. Photographs and statistics
have separate permissions (Wikimedia, n.d.).

The API-Football key is memory-only. Contact email and user settings belong
in the private user archive. Release packaging never copies that archive or
HTTP cache. A file importer does not grant rights to its contents.

## Development and verification

```sh
python -m pip install -r requirements.txt pytest
python -m pytest -q
python app.py --smoke-test --screenshots output/screenshots
python scripts/build.py --dry-run
python scripts/build.py --installer
python scripts/check_package.py --installer output/GameSenseSetup-Windows.exe
```

Build on the target OS. Windows needs Inno Setup 6 (`GAMESENSE_ISCC` can locate
it). macOS uses `hdiutil` to produce the Apple Silicon DMG. PyInstaller bundles
the application and dependencies; their licences still apply. Generated
notices accompany the package. Installer reports explicitly distinguish
automated checks, signing and manual interactive validation.

Do not silently install over an existing production installation for QA.
Use the isolated QA installer path where required, preserve user data, and
keep each release version/tag separate. Publishing must follow successful
Windows and macOS package checks; an implementation or build command alone
does not prove the final product works. See [TEST_REPORT.md](TEST_REPORT.md)
for actual outcomes and remaining checks.

For the assessment package, commit reviewed source first and run:

```sh
python scripts/package_submission.py --ref HEAD --tag v0.10.0-beta.1 --artifacts output --evidence output/screenshots
```

The script requires both platform installers, matching build checksums,
successful package reports and target-platform test XML. `--source-only`
creates an explicitly labelled alternative and makes no package-verification
claim. The final ZIP is checked for integrity and assigned a SHA-256 digest.

## Scope and evaluation

The public desktop requirement changed the original Streamlit/Plotly stack
to PySide6/Matplotlib. The data question, four sports, validation, calculated
ratings, comparisons and graphs remain the acceptance criteria. No prediction
model or complete all-athlete archive is promised. Source granularity and era
gaps are material limits, documented in [DATA_SOURCES.md](DATA_SOURCES.md).
References are listed in [REFERENCES.md](REFERENCES.md).
