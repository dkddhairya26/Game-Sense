# Actual verification report

Final assessment development, **29 October 2026**. Baseline source is the
actual `v0.9.0-beta.1` tag, commit `fa44c59`, preserved on its existing branch.
This report separates controlled calculation tests, native UI checks and
package/publication evidence. No planned check is counted as passed.

## Executed automated checks

| Check | Expected outcome | Actual outcome | Result/evidence |
| --- | --- | --- | --- |
| Baseline v0.9 full suite, `python -m pytest -q` | Existing tests run without regressions before changes | **102 passed, 26 subtests passed**, 5.66 seconds | PASS; initial development-session command output |
| New data pipeline plus legacy import/archive tests | Valid rows persist; invalid/duplicate rows reported; repeated import unchanged | **58 passed**, 1.86 seconds | PASS; data-quality worker run; includes 16 new pipeline cases |
| New analytics plus legacy statistics/club tests | Four formulas match manual values; missing data/grain preserved; club results/streaks correct | **50 passed**, one fixture FutureWarning | PASS; analytics worker run, `test_final_analytics.py`, `test_statistics.py`, `test_analytics.py`, `test_club_profiles.py` |
| Analytics/chart-maths regression and full intermediate suite | Transfer season weighting, cumulative averages and recent-window missing values remain correct | **158 passed, 26 subtests passed**, 11.73 seconds, one controlled-fixture FutureWarning | PASS; analytics worker's intermediate full run; final release run still required after remaining edits |
| Final combined Windows suite | No regressions and all new tests pass | **175 passed, 26 subtests passed**, 72.58 seconds, no warnings | PASS; [JUnit evidence](evidence/unit-tests-Windows.xml), 201 test/subtest entries, zero failures/errors/skips |
| Expanded native Windows real-data acceptance/screenshots | Actual stored club/player/driver/constructor profiles, filters, comparisons and charts work | **15 required cases passed**, no unhandled errors; native Qt offscreen, offline, production database unchanged | PASS; [actual report](evidence/final_acceptance/report.json), generated 29 October 2026 10:12:57 UTC, includes corrected import view and NBA career/cohort assertions |
| Lead-agent visual inspection of real native renders | Charts legible, first-fold analysis visible and no card overlap in inspected views | Lead agent inspected Soccer dashboard, AFL six-chart page, NBA full comparison, rating/insight page and latest full NBA dashboard; another agent reviewed the NBA/import compact captures | PASS for the stated inspected views; no overlap observed and labels legible. Does not claim manual live interaction or that every screenshot was inspected |
| Windows final executable/installer check | Isolated native startup and package verification succeed without damaging production installation | Not yet recorded for final beta | PENDING |
| macOS final native package check | Native Mac build, mount/startup check and screenshots succeed | Not yet recorded for final beta | PENDING; cannot be established by a Windows build |
| Final release asset retrieval and download page | Both separately versioned installer assets exist and page points to them | Not yet recorded for final beta | PENDING; v0.9 must remain available |

## Controlled examples, bugs and retests

These small inputs are deliberately fictional QA examples. They verify
arithmetic and behaviour, not real historical sports claims.

| Test case | Expected outcome/manual check | Correction or relevant guard | Actual/retest |
| --- | --- | --- | --- |
| Season totals 100 points/10 games, 300/20 games | Total 400; PPG `400/30=13.333...` | Count matching games, not two season rows | PASS in statistics/analytics checks |
| 1/1 and 0/9 field goals | `1/10=10%`, not 50% | Recompute from actual attempts | PASS |
| Legacy per-game makes/attempts with unequal games | Combined rate weighted by actual games | Fixed aggregate shooting rate, preserving legacy source grain | PASS in new analytics check |
| Missing required rating component | No experimental score | Require all inputs; never reweight a partial formula | PASS |
| NBA at half of each fixed reference | 50/100 | Normalize per game; weights sum to one | PASS |
| Soccer club two-goal win | `100*(.70+.30*.75)=92.5` | Result/margin formula separate from athlete formula | PASS |
| F1 grid fifth, finish first | `100*(.80+.20*.70)=94` | Finishing/movement formula; grid zero excluded as ordered start | PASS |
| AFL points for/against 180/150 | Scoring percentage 120%, not goal accuracy | Zero denominator remains undefined | PASS |
| Duplicate rows with missing `record_id` | Distinct valid matches retained | Fixed accidental collapse of all NaN record IDs | PASS |
| Last five observations include a missing newest score | Average four known scores within actual five-observation window; do not substitute an older sixth record | Fixed selection of eligible rows before applying the recent window | PASS |
| NBA transfer season chart / cumulative legacy averages | Season rates use games weighting; cumulative averages convert back to known counts | Corrected chart aggregation and recorded grain precedence | PASS in nine chart-maths regression cases |
| CSV/JSON/XLSX controlled files | Supported records produce same normalized dataset | Actual local files read, source file not mutated | PASS in pipeline checks |
| Invalid date, negative score, made greater than attempts | Reject row with recorded reason; other valid rows persist | Row-local validation, report counts | PASS |
| Optional malformed/missing number | Remains missing and reported, never zero | Conversion/missingness report | PASS |
| Re-import and correction | Unchanged rows do not multiply; corrected values update | Stable import identity and payload comparison | PASS |
| Same-day unkeyed conflicting observations | Later conflict reported; explicit distinct event IDs allow separate games | Avoid silent SQLite overwrite of doubleheaders | PASS |
| Reopen SQLite and export quality report | Saved values/report survive, JSON is readable | Separate persistence counts and source metadata | PASS |
| Aston Villa Premier/Championship identity | One verified club history across divisions | Conservative reviewed aliases and legacy-ID migration | PASS; real native run opened 545 recorded club matches and a selected 46-match Championship season |
| Club/player mismatch or overlapping sources | Comparison blocked with explanation | Different entities/grains cannot share denominator | PASS for native club/player mismatch case; source/entity/phase guard covered by unit tests |
| Selected-season search display used a later team name | Search result metadata must belong to the selected source/season/entity, not the latest record outside that filter | Identified during real-data review; filtered CTE and a new regression test correct the lookup | PASS in final combined suite and expanded native search check |
| Import completed but records table still showed the previous provider | The newly imported source must be selected in the same view as its quality report | A strengthened pre-populated-library UI regression genuinely failed before the fix (expected new import, actual previous provider); import completion now selects the new source | PASS in regression retest, 174-test suite and final native recapture with selected-provider assertions |
| NBA selected-season panels had one point and sparse player-only distributions | Career context should span actual same-source seasons; cohort distribution/scatter should include the measured population | Career trend context, all-cohort PPG distribution/scatter, positional box plot and focus-aware radar replace unhelpful one-row views; focus defaults to recorded games played | PASS: final native run has five career seasons, 569 cohort distribution rows, 569 scatter rows and 528 rows with recorded positions; focus included in radar |

## Real-data acceptance checklist

The baseline screenshot files in `evidence/screenshots-baseline/` are a
before-change record. The actual improved native app was then rendered to
`evidence/final_acceptance/` on Windows 11 with Python 3.14.3 and Qt 6.12.0,
using an isolated offline archive. The expanded report distinguishes 13 source-backed
cases from two explicitly controlled fictional QA cases. The production
database was not modified. These are genuine Qt widget captures, not
design mockups or proof of a visible clean-machine installation.

| Flow | Evidence required before PASS | Current report status |
| --- | --- | --- |
| Aston Villa | Actual Premier League and Championship profile, full history, score summaries and fixtures | PASS: stable ID `openfootball:club:en:aston-villa`; 545 full-history matches, selected Championship 46; [full profile](evidence/final_acceptance/03-aston-villa-full-history.png), [Championship](evidence/final_acceptance/04-aston-villa-championship.png) |
| NBA | Real player search, season change, weighted totals, compatible comparison and source scope | PASS: LeBron `nba:2544` in 2023–24, 2024–25, 2025–26; [season profile](evidence/final_acceptance/05-nba-real-player-season.png); LeBron/Curry comparison has 25 measured summary rows, [full comparison](evidence/final_acceptance/11-nba-head-to-head-full.png). [Final dashboard](evidence/final_acceptance/08-nba-six-chart-studio.png) has five career seasons and 569 observed cohort rows. Selected-season team-label regression is corrected and retested. |
| AFL | Club scores/goals/behinds drive appropriate charts; no player-stat fiction | PASS: six charts from 436 real 2026 team rows in selected private QA dataset; [full AFL dashboard](evidence/final_acceptance/08-afl-six-chart-studio.png). QA copied 10,658 local rows; no AFL seed is shipped. |
| F1 | Historical driver and constructor views with observed races/qualifying | PASS for historical driver, six-chart dashboard and actual constructor comparison: Fangio `f1db:juan-manuel-fangio`, 58 observed rows across 1950–58 with recorded gaps; [profile](evidence/final_acceptance/06-historical-f1-driver.png), [dashboard](evidence/final_acceptance/08-f1-six-chart-studio.png). [Constructor comparison](evidence/final_acceptance/15-f1-constructor-comparison-full.png) uses Aston Martin/Ferrari 48 actual driver starts each, with 94/595 observed driver points; not an asserted official constructor championship tally. |
| Data Quality Report | Import from UI, inspect counts, repeat import, export report | PASS: actual UI worker processed four controlled rows: one valid/inserted, one exact duplicate, two rejected; repeated import reported one unchanged; [quality report screen](evidence/final_acceptance/13-data-quality-controlled-fixture.png), exported [JSON](evidence/final_acceptance/controlled-import-quality-report.json) |
| Ratings/insights | Explanation visible, plots match actual available inputs and period/source shown | PASS: Aston Villa score 46.8945/100 from 545 eligible records; recent 32.25 from five observations. Observed insight period 2010-08-14 to 2026-09-19, source OpenFootball; [rating/insight screen](evidence/final_acceptance/12-experimental-rating-and-insights.png). Values describe this source snapshot, not a universal club rating. |
| Portraits | Real verified photo + credit or clear silhouette offline | PASS: cached LeBron (Erik Drost, CC BY 2.0), Hamilton (Governo do Estado de São Paulo, CC BY 2.0) and Messi (Bryan Berlin/WikiPortraits, CC BY-SA 4.0) decode with matching IDs/metadata offline. NBA comparison screenshot shows permitted portraits. Other athletes can still have silhouettes. |
| Empty archive/invalid input/offline | Informative state; no crash or invented measurements | PASS: fresh offline startup loaded permitted F1/NBA/Soccer starter; AFL remained zero with explanation, [fresh AFL state](evidence/final_acceptance/02-afl-fresh-archive-empty.png). Invalid imports/mismatched comparisons tested with controlled fixtures. |
| Simultaneous charts and resize | Six distinct nonempty panels per recorded sport; full page and compact captures | PASS for actual populated panel checks/captures: `07-*dashboard.png`, `08-*six-chart-studio.png`, `09-*compact.png`. Agent visual inspection covered the stated views; chart PNG/CSV mathematics are checked separately. |

The first NBA capture exposed unhelpful one-observation panels. The corrected
source now supplies same-source career context and real league-cohort views,
without pretending season totals provide a player's individual recent games
or a genuine court shot map. The final recapture verified those broader
populations and the corrected imported-source view. Earlier successful captures
are evidence for their own code revision; they do not erase later observed bugs.

After this local capture, a label-only change propagates the archive's
`ongoing_partial` source status into query metadata and chart footnotes.
The local screenshots establish the recorded analytical/interaction checks;
CI renders and package reports will provide evidence for that final label
revision. The latest executed full local suite recorded here remains
175 tests plus 26 subtests; any later run must be reported from its actual log.

The F1 primary-source audit in [F1_SOURCE_AUDIT.md](evidence/F1_SOURCE_AUDIT.md)
verified the pinned ZIP against its asset hash and matched all 27,687 seed
point values. The source has 8,592 non-null points and 19,095 null points,
with zero explicit point zeros. Unknown points remain unknown. A mean of
recorded point values therefore describes that measured subset, not every
race start. Explicit source zero preservation has controlled provider tests.

## Known limits and submission readiness

Coverage remains uneven: bundled NBA starts in 2022; a requestable old season
is not a successful historical download. OpenFootball supplies clubs, not
Ronaldo's individual full career. Squiggle supplies AFL teams. Optional AFL
player source rights remain unverified for redistribution. F1 race history
does not contain complete telemetry. Real photos are available only where
identity/licence metadata pass checks. See [DATA_SOURCES.md](DATA_SOURCES.md).

No trusted code signing, notarisation or visible clean-machine manual install
is asserted. Windows and macOS need their own final package reports. The
assessment ZIP must contain the matching committed source, permitted data,
actual evidence, instructions and verified artifacts. The student's own
review/modification, references, teacher-shared progress and independent
validation remain required. This file must be updated from actual evidence
before describing the final beta as release-verified or submission-ready.
