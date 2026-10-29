# References and attribution

Harvard-style engineering reference list. Access dates describe checks made
for the AI-assisted engineering work, not sources claimed to have been
personally read by the student. The student should review references used
in their own submitted explanation and follow the school's precise format.

## Supplied assessment sources

- Dhiraj, D.K. (2026) *GameSense Independent Study Tertiary: Project Proposal*.
  Semester 2. Supplied PDF, particularly proposal, deliverables, data-driven
  responsibilities and milestones, pp. 1–7. Original filename:
  `Copy_of_Dhiraj_Dhairya_-_Independent_Study_2026_-_Project_Proposal_1_.pdf`.
- St Mary MacKillop College (2026) *Year 12 Digital Technologies T, Semester 2:
  Task 2 Major Project*. Edited 17 August. Supplied PDF, task-specific
  instructions and 70-mark rubric. Original filename:
  `26S2IT_12DigTechT_AT2_Project CANVAS (1).pdf`.

## Statistical data and image sources

- API-Sports (2026) *API-Football documentation*.
  Available at: https://www.api-football.com/documentation-v3
  (Accessed: 29 October 2026; integration inspected in repository).
- API-Sports (2026) *Terms of service*.
  Available at: https://www.api-football.com/terms
  (Accessed: 29 October 2026).
- BoxScore Lab (2026) *Free NBA data downloads*.
  Available at: https://boxscorelab.com/downloads/
  (Accessed: 29 October 2026). CC BY 4.0; bundled snapshot assembled
  28 October 2026. Rates and counts reflect its recorded source coverage.
- F1DB contributors (2026) *F1DB: Formula 1 database*, release v2026.18.0
  used by bundled snapshot.
  Available at: https://github.com/f1db/f1db
  Licence: https://github.com/f1db/f1db/blob/main/LICENSE
  (Accessed: 29 October 2026). Credit Marcel Overdijk and contributors;
  CC BY 4.0. GameSense renames fields and joins results/identity/event tables.
- Hudl/StatsBomb (2026) *StatsBomb Open Data*.
  Available at: https://github.com/hudl/open-data
  (Accessed: 29 October 2026). Consult the repository's current licence and
  acknowledgement requirements before publishing analyses or data.
- Jolpica contributors (n.d.) *jolpica-f1*.
  Available at: https://github.com/jolpica/jolpica-f1
  (Integration/terms inspected in GameSense source, 29 October 2026).
- Kareen, A. (n.d.) *AFL Data Analysis*.
  Available at: https://github.com/akareen/AFL-Data-Analysis
  (Accessed: 29 October 2026). Research compilation attributes data to AFL
  Tables. MIT software permission is not treated as independent verification
  of rights over the underlying third-party statistics.
- NBA (n.d.) *Terms of Use*.
  Available at: https://www.nba.com/terms-of-use
  (Integration/terms link inspected in GameSense source, 29 October 2026).
- OpenFootball contributors (2026) *football.json*.
  Available at: https://github.com/openfootball/football.json
  Licence: https://raw.githubusercontent.com/openfootball/football.json/master/LICENSE.md
  (Accessed: 29 October 2026). CC0 1.0; GameSense converts completed
  fixtures to two attributed club-perspective match records.
- Squiggle (n.d.) *Squiggle API*.
  Available at: https://api.squiggle.com.au/
  (Accessed: 29 October 2026). Basic AFL fixtures/results, not advanced
  Champion Data or player box scores.
- Swar and nba_api contributors (n.d.) *nba_api*.
  Available at: https://github.com/swar/nba_api
  (Integration inspected in GameSense source, 29 October 2026). MIT client
  software does not grant redistribution rights over NBA statistical content.
- Wikimedia contributors (2026) *GameSense bundled portrait source files*.
  Individual authors/licences/source links are listed in
  [data/portraits/ATTRIBUTION.md](data/portraits/ATTRIBUTION.md) and adjacent
  JSON manifests. Images retrieved 28 October 2026; no AI face generation.
- MediaWiki contributors (n.d.) *API:Imageinfo*.
  Available at: https://www.mediawiki.org/wiki/API:Imageinfo
  (Implementation reference in `gamesense/images.py`).
- Wikidata contributors (n.d.) *Wikidata:Data access*.
  Available at: https://www.wikidata.org/wiki/Wikidata:Data_access
  (Implementation reference in `gamesense/images.py`).

## Implementation tools

- Matplotlib development team (n.d.) *Embedding in Qt*.
  Available at: https://matplotlib.org/stable/gallery/user_interfaces/embedding_in_qt_sgskip.html
  (Implementation reference; native Qt canvas used in `charts.py`).
- NumPy developers (n.d.) *numpy.average*.
  Available at: https://numpy.org/doc/stable/reference/generated/numpy.average.html
  (Weighted-average API used by the calculations).
- pandas development team (n.d.) *pandas documentation*.
  Available at: https://pandas.pydata.org/docs/
  (Dataframe, conversion, grouping and import APIs used by the application).
- PyInstaller development team (n.d.) *Using PyInstaller*.
  Available at: https://pyinstaller.org/en/stable/usage.html
  (Implementation reference in `scripts/build.py`).
- Qt Project (n.d.) *Qt for Python documentation*.
  Available at: https://doc.qt.io/qtforpython-6/
  (Native widgets, models, signals and worker APIs used by the application).
- SQLite contributors (n.d.) *Appropriate uses for SQLite*.
  Available at: https://www.sqlite.org/whentouse.html
  (Technical rationale: local application data storage).
- JRSoftware (n.d.) *Inno Setup Help*.
  Available at: https://jrsoftware.org/ishelp/
  (Windows installer script/build reference).

Library licence texts and Qt redistribution information are generated with
native packages. Use of a library is not a claim that the whole application
was copied from its example code. The experimental rating weights/reference
scales are GameSense design choices, documented in `ratings.py` and
[ALGORITHMS.md](ALGORITHMS.md), not attributed as official league formulae.

## AI assistance

- OpenAI (2026) *Codex: AI assistance reviewing, refining and testing
  GameSense code, native interface, packaging and engineering documentation*.
  Interactive development session, 29 October 2026; earlier assistance
  recorded in [docs/AI_ASSISTANCE.md](docs/AI_ASSISTANCE.md).

Retain the actual prompts, diffs and review decisions. The student must
critically evaluate/modify assisted content under Component 1 AI Collaboration
conditions. No personal learning experience or supervised No AI validation
response is generated by these references.
