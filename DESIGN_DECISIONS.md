# Design decisions and observed problems

Factual engineering record prepared with AI assistance, 29 October 2026.
The v0.9 release is preserved; final assessment work starts from tag
`v0.9.0-beta.1` at `fa44c59` on a separate development branch.

| Decision/problem | Chosen approach and reason | Trade-off / evidence |
| --- | --- | --- |
| Native application required after proposal named Streamlit | Retain Python/Pandas, use PySide6/Qt and embedded Matplotlib, package with PyInstaller | End users need no Python/server. Developers must handle Qt workers, resizing, bundled licences and separate OS builds. |
| Four sports measure performance differently | Shared navigation/archive, separate entity-aware analytical functions and rating formulas | Reuse does not imply a universal cross-sport score; `ratings.py` documents fixed references and bias. |
| One local user archive must work offline | SQLite transactions with indexed common fields and JSON sport-specific payloads | No database server; optional metrics need query/processing work and bounded scope explanations. |
| Data downloads can fail midway | Commit batches and record per-source/season state; cancellation preserves previous batches | A saved/complete download status does not prove universal statistical coverage. Provider responses and terms can change. |
| Aston Villa was split by league/name spelling | Country-scoped conservative club aliases and migration of known legacy IDs | Preserves Premier/Championship history without erasing matches. Unknown aliases still need deliberate review; player names are never club IDs. |
| Club score rows previously reached player-only views | Separate club summaries/match logs and compatible entity comparisons | No synthetic individual goals, assists, xG or disposals can be derived from a club result. |
| Season totals were vulnerable to wrong denominators | Preserve record grain, matching games and attempts; recompute weighted rates | Unknown denominators leave values missing. Counted observations/period need to remain visible. |
| Raw weighted ratings lacked a clear scale | Experimental 0–100 formulas using fixed positive references and bounded components; legacy API uses the same new calculation | Predictable interpretation when filters change; reference selection is subjective, role/era/opponent effects remain. |
| Import success was not a sufficient data-use explanation | Data Quality Report counts validation, conversion, rejection, duplicates and persistence | Report categories can overlap; input/duplicate/rejected/valid balance is separate from insertion/update counts. |
| Automatic insights must be verifiable | Deterministic templates over actual observed statistics, period and source | Cannot establish causes or predict results. No result is invented to fill an empty state. |
| Portrait rights and identity can be uncertain | Wikidata sport checks plus acceptable Commons metadata, disk cache and original silhouette | Some athletes have no permissible photo. Photograph availability is independent from statistical coverage. |
| Publicly accessible data are not always redistributable | Bundle permitted F1DB/BoxScore Lab/OpenFootball sources with notices; restrict other sources to explicit local requests | Broad historic player coverage remains limited; paid endpoint access does not automatically grant image/raw-data publication rights. |
| Passing tests previously overstated product readiness | Separate controlled maths, live native flows, screenshot inspection, installer checks and publication verification | Automated success is only evidence for the check actually run. Manual clean-machine testing/signing remain separate. |
| Existing release must remain usable | New branch and separately versioned release; no force-push or asset replacement | Download page updates only after new installer assets can actually be retrieved. |

## Commenting approach

Explanatory docstrings describe what a function consumes/returns and why its
algorithm is appropriate. Comments address important choices: stable keys
instead of names, missing instead of zero, season versus game grain, attempt
weighting, transactions and queued signals. They do not merely restate a
line of Python. External datasets, APIs and libraries are referenced where
used; formulas invented for GameSense are labelled as such.

## Issues that must remain visible

Bundled NBA data do not contain pre-2022 careers. NBA Stats may refuse
requests. OpenFootball provides club scores without individual player stats.
StatsBomb is a selected research catalogue. The AFL research archive has
underlying rights questions and is not redistributed. F1 results are not
complete telemetry. A premium interface cannot cure absent source data;
coverage explanations and honest empty states remain part of the design.

For actual failures, fixes and retests from the final work, see
[TEST_REPORT.md](TEST_REPORT.md). These entries record engineering decisions,
not personal experiences attributed to the student.
