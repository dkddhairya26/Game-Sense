# Factual development evidence and student review prompts

This file is an AI-assisted record of observable engineering work. It is
**not a personal reflection**, does not assert the student's independent
authorship, and does not answer the supervised validation.

## Evidence available

| Fact | Evidence location | What it can establish |
| --- | --- | --- |
| Original proposal chose four sports and a collect/validate/process/calculate/analyse/visualise pipeline | Supplied *GameSense Independent Study Tertiary* PDF, proposal/deliverables/data-driven sections | Original intended problem and requirements |
| Proposed stack included Python/Pandas/Plotly/Streamlit; final delivery uses Qt/Matplotlib desktop | Proposal p. 5; imports in `app.py`, `window.py`, `charts.py`; build scripts | A real design modification requiring the student's own justification |
| v0.9 source preserved before final work | Git tag `v0.9.0-beta.1`, commit `fa44c59`; separate final branch | Starting point and release continuity |
| Baseline suite was actually run | Final-session baseline: 102 tests and 26 chart subtests passed | Existing automated checks passed before final changes, not that every product feature was complete |
| Club names can differ across divisions | `club_identity.py`, archive migration and `test_club_profiles.py` | A specific identity problem and a testable correction |
| Correct averages need observation grain | `metric_summary`, weighted-rate tests and `ALGORITHMS.md` | Why a season-total row cannot be treated as a game |
| Missing statistics are retained as unknown | Import/analytics/ratings tests | Prevents misleading zero scores and partial ratings |
| Imports now expose decisions and database effects | Data Quality Report and `test_data_quality.py` | Observable validation, rejected/duplicate rows, conversions and persistence |
| Ratings are explicit experimental formulas | `ratings.py`, `ALGORITHMS.md`, controlled tests | Weight/reference choices, mathematically checkable output and limitations |
| Source coverage is uneven | `DATA_SOURCES.md` and actual generated manifests | Why unsupported careers/metrics cannot be presented as complete |
| Final tests/screenshots/packages have separate evidence | `TEST_REPORT.md`, `output/` reports, screenshot files and final ZIP manifest when generated | Only the checks that actually ran, their outcomes and remaining uncertainty |

Keep actual prompt transcripts, code diffs, test logs, screenshots and the
teacher-shared progress record. This repository is additional evidence; it
does not prove the required Google Doc has been shared with the teacher.

## Student's own review record

Complete these entries truthfully after reviewing and testing the work.
Unfilled cells are intentional; no review, learning or experience is invented.

| Review item | Student's factual notes and evidence |
| --- | --- |
| Code/algorithms personally understood and manually checked | To be completed by student. |
| AI suggestions modified or rejected, and why | To be completed by student. |
| Final native app flows personally tested | To be completed by student. |
| Data/image sources personally checked | To be completed by student. |
| Remaining defects or limitations observed | To be completed by student. |
| Teacher approval/conditions and shared progress retained | To be completed by student. |

## Prompts for permitted independent evaluation

Use only under the teacher's applicable conditions. These are questions to
consider, not a drafted response:

- Which original requirement can you demonstrate with actual inputs and
  outputs? Which remains limited by the source?
- What does the player-season denominator change, and how did you manually
  verify a result?
- What trade-off followed from delivering a desktop application?
- Which failure did you personally observe, what did you change, and what
  evidence shows the retest result?
- Which AI-assisted parts did you critically evaluate and modify?
- How did prioritising correctness and the deadline affect optional work?
- What would you improve next, and what evidence makes it a priority?

The supplied task identifies **AI Collaboration (Level 3)** for the project
and **No AI** for Component 2 validation. Do not use AI to compose or complete
that supervised component. Retain and cite the assistance actually used.
