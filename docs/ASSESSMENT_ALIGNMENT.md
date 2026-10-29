# Assessment and proposal alignment

This is an engineering evidence guide, prepared with AI assistance on 28 October 2026. It does not supply answers for the supervised validation task or invent the student's own reflections.

## Supplied task requirements

The supplied `26S2IT_12DigTechT_AT2_Project CANVAS (1).pdf` identifies **Major Project**, Independent Study (1.0), worth 40%, due **30 October 2026**. Component 1 requires delivery of the project proposed in Task 1, submitted as one ZIP named `SURNAME Firstname – Project.zip`, containing the completed project, source/assets, a working version where possible and access instructions.

The task-specific AI scale for Component 1 is **Level 3, AI Collaboration**: the student must critically evaluate and modify AI-assisted content. The user states that updated assessment conditions permit AI assistance. This project therefore records that help transparently; it does not assert that generated work was independently authored by the student. The student's teacher-approved conditions remain their assessment record.

Component 2 is a separate **No AI** supervised validation: 30 minutes, individual silent work, and 300 words. That component has not been written or answered here.

## Actual marking criteria and evidence

| Rubric criterion | Marks | Relevant project evidence | Student action still required |
| --- | --- | --- | --- |
| Alignment with the original proposal and identified problem; justified design modifications | 10 | Proposal-to-implementation mapping below; technical report architecture and limitations | Explain the choices in their own words and verify the final application addresses the target audience. |
| Critical use of data/information to solve problems and justify technology decisions | 15 | Provider provenance, explicit missing values, stable identities, incremental SQLite storage, correct aggregation | Examine the actual source coverage and explain why the selected data and methods were appropriate. |
| Controlled application of technology to create a functional, high-quality solution | 20 | Native app, four sport modes, searching, comparisons, figures, background downloads and packaging | Run the final artifact, retain screenshots and verify each claimed feature. |
| Explanatory code comments: purpose, functionality, appropriateness and source references | 15 | Module docstrings and comments on identity, transactions, licensing, missing data and aggregation; source links | Review and understand the code, expand explanations where needed and reference borrowed material accurately. |
| Insightful personal reflection on planning, time management, strategies, problem solving and skill development | 10 | Development log and real testing records provide factual evidence | Write their own reflection during the permitted conditions. No generated personal reflection is provided. |
| Total | **70** | | |

## Mapping to the original GameSense proposal

| Original commitment | Implementation approach and evaluation |
| --- | --- |
| Four sports: soccer, basketball, AFL and F1 | Shared interface with separate metrics and sport presentation. Check real stored coverage separately for every sport. |
| Sports data → validation → processing → calculation → analysis → visualisation | Provider normalization/import validation → indexed archive → analytical functions → profiles/comparisons → chart module. |
| Sports selection and team/player/competitor selection | Navigation and identity-based search. A team-level source is labelled as a team; it is not offered as invented player statistics. |
| Historical sporting data | Provider-backed historical downloads and a local archive, with transparent gaps and source attribution. “All available” is bounded by each provider's actual catalogue. |
| Validation and cleaning | Required columns, date checks, duplicate handling, numerical conversion and missing-value preservation. |
| Different calculations for each sport | Explicit metric interpretation, additive totals versus rates/positions and labelled experimental rating formulas. |
| Recent form, averages, performance graphs and comparisons | Shared mathematical helpers, time-series and comparison figures; verify with manually checkable examples. |
| Clear labels, filters and understandable graphs | Sport/season/identity controls, chart explanations, empty states and source coverage. |
| Testing evidence and documentation | Tests, generated screenshots, package check reports and technical report; retain actual output rather than claiming a planned check passed. |
| Python, Pandas, Plotly and Streamlit | Python/Pandas retained; PySide6/Qt and Matplotlib replace Streamlit/Plotly to meet the updated native desktop installation requirement. This is a justified delivery change, not a change in the core analytical problem. |
| Ethical data use and clear experimental ratings | Source/licence metadata, approved portraits, rights-aware bundling, explicit metric coverage and nonofficial custom ratings. |

## Submission preparation

1. Keep the original proposal, teacher-approved AI conditions and development evidence. The supplied task requires a progress Google Doc shared with the teacher; this repository is additional evidence and does not claim that sharing has happened.
2. Review every change and replace any generated explanation that does not reflect the student's understanding.
3. Run the final automated tests and visible application. Include genuine screenshots and the actual test/build reports.
4. Include Python source, permitted assets/datasets, README, technical report, source references, AI assistance record and a verified installer where available. Exclude `.git`, development environments, personal caches and unlicensed downloaded content.
5. Name the final submission ZIP according to the task's required surname/firstname format. Do not label an untested package as verified.

Sources: supplied assessment PDF, pages 1–3 of task instructions/rubric (plus coversheet and conditions), and supplied *GameSense Independent Study Tertiary* proposal, especially proposal, deliverables, data-driven responsibilities and milestones. The task PDF contains older general AI statements alongside the task-specific collaboration scale; use the task-specific and teacher-updated permission record without presenting any generated content as independent authorship.
