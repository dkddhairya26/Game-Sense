# GameSense

GameSense is a native Python/PySide6 desktop application that turns real
football, NBA, AFL and Formula 1 records into profiles, comparisons,
sport-specific calculations and interactive charts. Downloaded data and
licensed cached portraits remain available offline.

This final assessment development branch starts from the actual
**v0.9.0-beta.1** release (`fa44c59`) and preserves that public release.
The separately versioned final beta target is **v0.10.0-beta.1**. Consult
[TEST_REPORT.md](TEST_REPORT.md) for actual verification and publication status;
source code and passing tests alone do not establish a published installer.

**[Official download page](https://dkddhairya26.github.io/Game-Sense/)** ·
**[Published release assets](https://github.com/dkddhairya26/Game-Sense/releases)**

## What the application does

- Explore stable player, club and driver identities with season/competition
  filters and source attribution. Football club profiles retain recorded
  Premier League and Championship histories across reviewed name aliases.
- Calculate club results, scoring and venue splits, dated recent form and
  streaks; player season/career totals and correctly weighted per-game
  statistics; F1 wins, podiums, points and observed finishing performance.
- Explain experimental sport-specific GameSense ratings, show their changes
  and describe actual data with deterministic source-qualified insights.
- Compare compatible competitors with measured statistics and charts.
  Missing values remain unavailable; team scores never become player stats.
- Import CSV, JSON and Excel `.xlsx`, validate/clean records and retain a
  Data Quality Report showing duplicates, rejection, conversions, missingness
  and database insertion/update outcomes.
- Show several different sport-specific charts simultaneously, plus an
  interactive deep-dive. Hover, pan/zoom, PNG and underlying CSV export are
  supported when the selected data provide the required fields.
- Load identity-verified permitted Commons photos with attribution and an
  original silhouette when no suitable image can be verified.

## Understand the coverage

The checked starter contains **27,687 F1 driver-result rows from 1950–2026**
and **2,673 NBA player-season rows from 2022–23 through 2026–27**. Builds
also generate completed European club matches from published CC0
OpenFootball files. Current seasons are incomplete and source detail varies
by era. The NBA starter does not include pre-2022 player careers.

Optional historical NBA Stats requests can be blocked by NBA.com. API-Football
requires the user's own account key and permitted seasons. StatsBomb covers
selected football competitions; its Ronaldo action requests observed Portugal
2022 World Cup matches, not his full career. Squiggle supplies AFL club
results. Player disposals/tackles require a separate actual player source or
permitted import. The opt-in AFL research dataset is not bundled because its
original data rights need independent review. No provider guarantees every
athlete, year or metric.

See [DATA_SOURCES.md](DATA_SOURCES.md) for counts, source rights, unavailable
categories, photo coverage and precise limitations. There is no invented
shot location or F1 telemetry. Fictional demonstration data are explicitly
separate from the real archive.

## Install or run

Native packages target **Windows x64** and **macOS Apple Silicon, macOS 14+**.
No Intel Mac package is supplied. Beta builds are unsigned; macOS builds are
not notarised. Installation/package tests and manual interactive checks are
reported separately. Installed users need no Python, Git, VS Code or terminal.

Developers can run the native app from source:

```sh
python -m pip install -r requirements.txt
python app.py
```

Default user data live in `%LOCALAPPDATA%/GameSense` on Windows and
`~/Library/Application Support/GameSense` on macOS, separately from the
installation. `GAMESENSE_DATA_DIR` isolates development/test archives.
Internet is needed for new downloads and uncached portraits.

## Test, build and retain evidence

```sh
python -m pip install pytest
python -m pytest -q
python app.py --smoke-test --screenshots output/screenshots
python scripts/build.py --dry-run
python scripts/build.py --installer
```

Build on the target OS. Windows requires Inno Setup 6 (`GAMESENSE_ISCC`
can point to it). macOS uses native `hdiutil`. Run
`scripts/check_package.py --installer <artifact>` for isolated native
installation/startup verification. Existing production installations must
be preserved during QA. A build is not an installation test or publication.

The submission packager uses a committed Git snapshot and matching checked
artifacts, excludes personal archives/caches and refuses to replace an
existing ZIP:

```sh
python scripts/package_submission.py --ref HEAD --tag v0.10.0-beta.1 --artifacts output --evidence evidence
```

Use `--source-only` only for an explicitly labelled package without installers.
Read the produced manifest and actual test reports before assessment use.

## Documentation and assessment

| Document | Contents |
| --- | --- |
| [USER_GUIDE.md](USER_GUIDE.md) | Installation, filters, profiles, imports, comparisons, offline use and troubleshooting |
| [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) | Architecture, persistence, threads, pipeline, packaging and trade-offs |
| [DATA_SOURCES.md](DATA_SOURCES.md) | Real source scope, recorded populations, permissions and gaps |
| [ALGORITHMS.md](ALGORITHMS.md) | Formulae, denominators, ratings, missing data and limitations |
| [TEST_REPORT.md](TEST_REPORT.md) | Executed checks, expected/actual results, fixes/retests and unverified work |
| [PROPOSAL_ALIGNMENT.md](PROPOSAL_ALIGNMENT.md) | Original commitments and 70-mark rubric linked to code/evidence |
| [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) | Reasons for technical choices and observed problem corrections |
| [REFERENCES.md](REFERENCES.md) | Dataset, library, assessment and AI-assistance references |
| [REFLECTION_EVIDENCE.md](REFLECTION_EVIDENCE.md) | Factual development record and unfilled student review prompts |

The proposal's Python/Pandas analytical workflow is retained. PySide6 and
Matplotlib replace Streamlit/Plotly to deliver an installable desktop product.
The supplied task allows AI Collaboration (Level 3) for the project and
requires the student to critically evaluate and modify assisted content.
Assistance is disclosed in [docs/AI_ASSISTANCE.md](docs/AI_ASSISTANCE.md).
The separate supervised validation is No AI. No personal reflection or
validation response has been written for the student.

Dataset and photograph licences remain attached to their manifests, and
dependency notices accompany packages. Importing a file or accessing a public
API does not grant redistribution rights over its contents.
