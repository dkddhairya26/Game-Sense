# Proposal and rubric evidence checklist

This is an AI-assisted engineering audit, not a predicted mark or a personal
reflection. It uses the supplied *GameSense Independent Study Tertiary*
proposal (Dhiraj, 2026) and the supplied task's actual rubric (St Mary
MacKillop College, 2026). The deadline is **30 October 2026**.

The original question is how a single digital platform can process and
visualise different sporting data to compare performance and identify
meaningful trends. The final product retains that analytical purpose while
delivering a PySide6 desktop application instead of the proposed
Streamlit/browser application.

## Original requirements mapped to evidence

| Proposal commitment | Code/functionality | Automated evidence | Evaluation and boundary |
| --- | --- | --- | --- |
| Four sports and sport selection | `window.py`, `analytics.SPORTS`, provider registry | `test_analytics.py::test_all_sports_demo`; chart rendering checks | All four modes exist; real archive coverage differs and demo records are explicitly separate. |
| Team/player/competitor selection | Stable `competitor_id`, archive search, profiles and club aliases | `test_club_profiles.py` identity/filter/migration cases; `test_statistics.py` same-name test | Club and athlete statistics must remain separate; fuzzy similarity is not identity proof. |
| Historical sporting data | Source-attributed SQLite records, downloadable provider catalogues and starter manifests | `test_archive.py`, `test_extra_providers.py`, generated coverage manifests | Bundled NBA is recent-only; requestable old years are not verified downloaded history. |
| Data validation and cleaning | `prepare_import`, `validate_import`, `import_dataset` and exported quality report | `test_data_quality.py`, `test_importers.py`, `test_analytics.py` | Optional missing values stay missing; essential invalid rows and impossible scores are reported. |
| Sport-specific calculated statistics | `metric_summary`, `club_summary`, `performance_summary` | `test_statistics.py`, `test_club_profiles.py`, `test_final_analytics.py` | Season totals use games denominators; percentages and positions are not summed. |
| Recent form and streaks | Club last-five/ten, venue summaries/streaks; rating history/recent summary | `test_final_analytics.py` controlled W/D/L/rating examples | Season-only rows are labelled seasons rather than recent games. |
| Performance ratings | `ratings.py`, 0–100 experimental formulas and in-app explanation | `test_final_analytics.py` required-components, reference and season-grain cases | Fixed references/weights are explained choices; no official, role- or era-adjusted claim. |
| Comparison of competitors | Same-sport/entity selection, shared metrics and comparison charts | Analytical denominator tests plus actual UI acceptance evidence when captured | Different sources or sample sizes need visible context; incomplete data cannot become zero. |
| Graphs, labels and filtering | Simultaneous sport panels, custom deep-dive, hover, season/competition filters | `test_images_charts.py`, `test_extra_providers.py` dashboard structure, native screenshots | A successful widget creation is weaker evidence than inspecting populated charts and their values. |
| Export selected results | Figure PNG, plotted CSV and Data Quality Report JSON | Chart/export and pipeline report-export tests | Export preserves the scope and provenance of the selected observations. |
| Automatic summaries (optional) | `insights.py` deterministic observed-statistic templates | `test_final_analytics.py` source/period and result tests | Describes data only; no inferred causes, predictive claims or invented commentary. |
| Ethical sources and limitations | Provider metadata, `DATA_SOURCES.md`, portrait licences/manifests | Licence/fallback tests, source scope tests, submission exclusions | Restricted API/research data are not copied into public starter bundles. |
| Testing and documentation | Unit/regression tests, native smoke/screenshots, installer reports and this evidence set | `TEST_REPORT.md` and actual output artifacts | A test count alone cannot prove product completion or classroom usability. |

## Rubric checklist

| Criterion | Marks | Evidence to inspect | Current verification limit / student's action |
| --- | ---: | --- | --- |
| Alignment with proposal and problem; justified modifications | 10 | This mapping; `DESIGN_DECISIONS.md`; actual four-sport app | Student should assess the target need in their own words and explain the desktop delivery change. |
| Critical thinking and data/information used to solve problems | 15 | `DATA_SOURCES.md`; grain-aware calculations; quality report; alias migration and controlled tests | Inspect actual source coverage, analyse why the correction matters, and identify remaining bias. |
| Quality/effectiveness of finished product | 20 | Profiles, compatible comparisons, multi-chart dashboards, real screenshots, packaged startup/install reports | Run the exact final native installer and verify search/filter/resize/offline flows; implementation alone does not satisfy this criterion. |
| Explanatory comments | 15 | Module/function docstrings in archive, provider base, importers, analytics, ratings, insights, club identity and charts | Comments explain purpose, algorithms, missing data, transactions, background workers and trade-offs. Student must understand/review assisted code and borrowed references. |
| Reflection/development process | 10 | Git history, actual test failures/corrections, `REFLECTION_EVIDENCE.md`, retained prompts/screenshots | Student must provide their own truthful account under the teacher's permitted conditions; no personal response is generated. |
| Total | **70** | Evidence links, not an asserted score | Assessment judgement belongs to the teacher. |

The rubric's final reflection item is assessed through the separate supervised
validation component. This repository supplies factual engineering evidence,
not answers to that component.

## Technology change and scope

The proposal names Python, Pandas, Plotly and Streamlit. Python/Pandas remain;
PySide6/Qt and Matplotlib now provide a native application with ordinary
Windows/macOS installation, local persistence and embedded interactive charts.
This change addresses the updated public desktop requirement. It increases
packaging, thread-safety, installer and platform-testing work; it does not
remove the promised collect/clean/calculate/compare/visualise pipeline.

The proposal lists predictions and richer automatic summaries as optional,
conditional on the core product working. No prediction system is claimed.
Priorities are mathematical correctness, working profiles, understandable
comparisons, quality reporting, evidence and reliable packages.

## Submission and academic integrity

The task requires a single ZIP named `SURNAME Firstname – Project.zip` with
source/assets, the working product where possible and access instructions.
Use `scripts/package_submission.py` only after committing reviewed source and
collecting matching verified packages. Check the final ZIP's manifest and
integrity; keep restricted local data and credentials out.

The task-specific Component 1 scale is **AIAS 3: AI Collaboration**. It requires
critical evaluation and modification of AI-assisted content. The supplied
general policies also require references and retained progress in a Google
Doc shared with the teacher. This repository does not claim that the student's
review or teacher sharing has occurred. Component 2 is **No AI**, a separate
30-minute individual validation. No response for it is supplied.

Review [REFLECTION_EVIDENCE.md](REFLECTION_EVIDENCE.md) and
[docs/AI_ASSISTANCE.md](docs/AI_ASSISTANCE.md), retain the actual prompts and
outputs, and complete the student's review record honestly.
