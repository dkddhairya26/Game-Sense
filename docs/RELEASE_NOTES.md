# GameSense v0.10.0-beta.1 — Final analytics and assessment beta

Native Windows and macOS desktop application, based on the actual
`v0.9.0-beta.1` source. This is a separately versioned unsigned preview;
v0.9 remains available. Publication is gated on both platform jobs succeeding
and refuses to replace an existing release or its assets.

## Calculated performance, not only raw tables

- Football/AFL club profiles calculate observed wins, draws, losses, score
  difference, average scoring, home/away splits, dated last-five/ten form and
  winning/losing streaks. AFL scoring percentage uses points for divided by
  points against; club scores never become individual player disposals.
- NBA player totals and per-game averages respect recorded games and source
  grain, including transferred-player season weighting and legacy per-game
  imports. Combined shooting rates use recorded attempts. Estimated true
  shooting and effective field-goal percentage need their required inputs.
- F1 views calculate observed wins, podiums, points, finishing averages and
  paired qualifying-to-race performance. Constructor comparison aggregates
  recorded driver starts and discloses that driver points are not necessarily
  the official constructor championship tally. Missing finishes are not zero.
- Experimental GameSense 0–100 ratings now use explicit sport/entity-specific
  formulas, reference values and weights. Required missing inputs invalidate
  a score. An in-app explanation, component contributions and rating history
  make the result inspectable. The score is not an official or era-adjusted
  ranking. Recent form uses the actual latest observation window before
  excluding its unavailable scores.
- Deterministic statistical insights describe actual selected records and
  attach the period/source. They do not invent causes or predict results.

## Imports, comparisons and native interface

- CSV, JSON and Excel `.xlsx` imports produce a persistent Data Quality
  Report: input/valid/duplicate/rejected rows, invalid dates/scores, numeric
  conversions, missing values and inserted/updated/unchanged database rows.
  Reports export to JSON. Invalid rows do not discard the other valid rows.
- Repeat imports preserve stable observation identities. Conflicting same-day
  rows need distinct event IDs instead of silently overwriting each other.
- Comparisons enforce compatible entities and a single source/phase, show
  measured differences and coverage, and retain missing values as unavailable.
  Athlete and club results are not placed on the same denominator.
- Sport dashboards retain multiple simultaneous meaningful charts alongside
  the custom deep-dive. The final work improves chart aggregation, context,
  profile analysis and rating/insight presentation inside the existing native
  PySide6 application.
- Source/entity filtering and search help distinguish a genuinely empty
  archive from records hidden by a league or season filter. Licensed portraits
  retain attribution and cached offline fallbacks.

## Real data and material limitations

The checked starter contains F1DB **27,687 driver-result rows, 1950–2026** and
BoxScore Lab **2,673 NBA player-season rows, 2022–23 through 2026–27**.
The European club seed assembled for this beta has **108,962 club-perspective
match rows**, 12 observed leagues and 17 observed seasons across the published
files (individual league-year coverage varies). Every football match appears
from two club perspectives; that is not 108,962 distinct fixtures. Current
seasons contain only completed supplied results and remain incomplete.

OpenFootball is CC0 club results, with no player rosters, individual goals,
assists or xG. Optional StatsBomb covers selected research competitions.
The Ronaldo shortcut supplies observed Portugal 2022 World Cup events, not
his full Sporting/Manchester United/Real Madrid/Juventus/Al Nassr career.
API-Football needs the user's own key and applicable account/data rights.

Bundled NBA does **not** contain Michael Jordan/Kobe/Shaq historical careers.
The optional NBA Stats integration requests earlier years, but NBA.com may
refuse requests. A catalogue year is not a verified downloaded season.
Squiggle supplies AFL teams, not player disposals or tackles. Optional AFL
research downloads remain local because underlying rights require separate
review; no AFL player dataset or personal user archive is redistributed.
F1 race records do not supply complete lap/sector/speed telemetry.

Six distinct verified photographs are included with individual Commons
licences; additional images require successful identity/licence checks.
Missing images use original silhouettes. Photos do not imply complete
statistical coverage. See [DATA_SOURCES.md](../DATA_SOURCES.md), source
manifests and [portrait credits](../data/portraits/ATTRIBUTION.md).

## Verification and assessment evidence

Controlled calculation/import tests, native UI regression checks, real-data
acceptance screenshots and target-platform package reports are separate
evidence. Read [TEST_REPORT.md](../TEST_REPORT.md) and the attached generated
reports for actual outcomes. A build or a test count alone is not a claim
that all product features or all historical coverage are complete.

The source includes the user guide, technical documentation, algorithms,
source/reference list, proposal/rubric mapping, design decisions and factual
reflection evidence. `package_submission.py` creates a separate assessment
ZIP from the matching committed source, checked native artifacts and reviewed
evidence. It excludes personal databases, API caches and credentials.

The supplied project conditions permit AI Collaboration with critical student
review/modification. Assistance is disclosed. Personal reflection and the
separate supervised No AI validation have not been written for the student.

## Platform limits

Windows packages target x64. The Mac package targets Apple Silicon with
macOS 14+ dependencies; no Intel Mac package is supplied. Packages are not
trusted-code-signed or notarised. Automated native install/startup checks
are distinguished from a person testing the visible application on a clean
machine. Preserve your user archive when upgrading.
