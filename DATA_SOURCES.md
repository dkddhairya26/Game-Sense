# Data sources and honest coverage

Checked against the v0.9 source and bundled files on **29 October 2026**.
An implemented provider is not proof that a live request succeeds or that its
whole catalogue is downloaded. Actual saved coverage is shown in the Data
manager. Current seasons contain only observations supplied so far.

## Redistributable starter records

The checked `data/seed.jsonl.gz` contains the following real source records.
Counts were obtained by reading the gzip and counting stable IDs, not by
counting image widgets or a hardcoded list of famous athletes.

| Sport/provider | Competition | First/latest recorded season | Seasons | Rows | Distinct competitors | Distinct teams | Grain |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| F1 / F1DB | Formula 1 | 1950 / 2026 | 77 | 27,687 | 860 drivers | 184 constructors | Driver race result with available joined fields |
| NBA / BoxScore Lab | NBA | 2022–23 / 2026–27 | 5 | 2,673 | 927 players across all five years | 30 teams | Player-season totals |

The source snapshot is F1DB **v2026.18.0** and the NBA file was assembled
28 October 2026. It is not a promise that today's upstream response is
identical. The adjacent `data/SOURCE_MANIFEST.json` records attribution and
transformations. Per-season NBA populations are 539 (2022–23), 572 (2023–24),
569 (2024–25), 582 (2025–26) and 411 (2026–27 at the snapshot). **2026–27 is
ongoing; 2026 F1 is also not labelled a completed historical season.**

Windows/macOS builds also generate `data/seed_soccer_cc0.jsonl.gz` from
published OpenFootball league files. The builder requests 2010–11 through
2026–27 for supported top/second divisions and accepts only dated completed
results. Not every league-year file exists. Its generated
`data/SOCCER_SEED_COVERAGE.json` is the evidence for the actual row, season
and league counts in that build; the request range alone is not coverage.
No player roster, individual scorer, assist or xG is inferred from a score.

The actual seed generated on **29 October 2026** contains **108,962
club-perspective rows**, **410 stable club IDs**, **12 leagues** and **17
observed seasons** across all files. Each finished fixture contributes two
club perspectives, not two distinct matches. Raw team-name strings can vary
across years; the stable club-ID count reconciles known aliases.

| Recorded league | First season | Latest season | Observed seasons | Club-perspective rows | Distinct stable club IDs |
| --- | --- | --- | ---: | ---: | ---: |
| English Premier League | 2010–11 | 2026–27 | 17 | 12,260 | 42 |
| EFL Championship | 2010–11 | 2026–27 | 15 | 15,696 | 53 |
| German Bundesliga | 2010–11 | 2026–27 | 17 | 9,864 | 39 |
| German 2. Bundesliga | 2012–13 | 2025–26 | 14 | 8,154 | 41 |
| Spanish La Liga | 2012–13 | 2026–27 | 15 | 10,758 | 42 |
| Spanish Segunda | 2012–13 | 2025–26 | 11 | 9,484 | 62 |
| Italian Serie A | 2013–14 | 2026–27 | 14 | 9,960 | 44 |
| Italian Serie B | 2013–14 | 2025–26 | 10 | 8,368 | 63 |
| French Ligue 1 | 2014–15 | 2026–27 | 13 | 8,562 | 40 |
| French Ligue 2 | 2014–15 | 2025–26 | 9 | 5,964 | 47 |
| Dutch Eredivisie | 2018–19 | 2026–27 | 9 | 4,872 | 35 |
| Portuguese Primeira Liga | 2018–19 | 2026–27 | 9 | 5,020 | 34 |

These counts describe the generated source files, not guaranteed complete
league histories. Upstream holes remain, including missing league-years
within the first/latest range. Active 2026–27 files contain only observed
completed results. Clubs appearing in more than one division occur in more
than one league's count, so the final column is not additive. Every row is
club-level; the player population supplied by this source is unavailable.

The fresh installer contains **no AFL seed**. For final private acceptance
testing, 10,658 previously downloaded Squiggle records were copied into an
isolated QA archive to verify real club charts. They are not redistributed
in the source/installer/assessment data bundle. A fresh AFL screen instead
explains how to retrieve permitted on-demand club results.

| Provider | Available fields | Material missing categories | Permission and attribution |
| --- | --- | --- | --- |
| [F1DB](https://github.com/f1db/f1db) | Race points/positions, grid, recorded qualifying/fastest lap, available pit stops and standings | No complete lap-by-lap speed/sector/tyre telemetry; older measurements vary | [CC BY 4.0](https://github.com/f1db/f1db/blob/main/LICENSE); credit Marcel Overdijk and contributors; renamed/joined fields described in manifest |
| [BoxScore Lab](https://boxscorelab.com/downloads/) | Recorded games, minutes, points/rebounds/assists, counting/shooting totals, supplied derived rates | No pre-2022 player archive in this source; no real shot coordinates; no individual recent-game form from season totals | Provider's [download page](https://boxscorelab.com/downloads/) states CC BY 4.0; credit source and data date |
| [OpenFootball football.json](https://github.com/openfootball/football.json) | Club identities, fixtures, home/away, final scores, observed W/D/L and calculated match points | No player statistics/lineups, xG, shots or official historical points deductions; league files can be partial | [CC0 1.0](https://raw.githubusercontent.com/openfootball/football.json/master/LICENSE.md); provenance retained despite waived attribution requirement |

The default build catalogue includes Premier League, Championship, La Liga,
Segunda, Bundesliga, 2. Bundesliga, Serie A, Serie B, Ligue 1, Ligue 2,
Eredivisie and Primeira Liga. League One/Two and Turkish Süper Lig are
additional provider catalogue entries. The presence of a catalogue entry
does not guarantee a published result file for every year.

## Optional local downloads

These sources are not combined into a publicly redistributed raw-data bundle.
The user must review current terms, account rights and actual responses.

| Sport/source | Implemented request scope | Actual availability/limitations | Rights and credentials |
| --- | --- | --- | --- |
| NBA / NBA Stats via `nba_api` | Historical regular-season player averages; request candidates begin 1946–47; advanced request from 1996 where supplied | NBA endpoints can block requests. A successful old-season response is necessary before claiming Michael Jordan/Kobe/Shaq history. Missing old metrics remain missing. No playoff completeness claim. | NBA-controlled statistics; `nba_api` software MIT is not a licence to redistribute NBA content. [NBA terms](https://www.nba.com/terms-of-use), [client project](https://github.com/swar/nba_api). |
| Soccer / StatsBomb Open Data | Its actual competition catalogue and event-derived player records with genuine coordinates | Selected competitions, not every league. The Ronaldo action requests Portugal's 2022 World Cup observations, not his full club career. | [Source/terms](https://github.com/hudl/open-data); research/noncommercial constraints and attribution apply. No raw seed bundled. |
| Soccer / API-Football | Search stable player profiles, permitted career seasons and league/player aggregates | Plan- and endpoint-dependent coverage. No guarantee of every Sporting/Manchester United/Real/Juventus/Al Nassr/Portugal season. Transfers retain separate team/league rows. | User's own memory-only API key; account limits and [terms](https://www.api-football.com/terms) apply. Underlying publication/image rights are not assumed. No shared credentials or paid subscription is included. |
| AFL / Squiggle | Published completed team-match results, goals, behinds, scores and fixtures | Club-level data only. No player disposals, tackles, Inside 50s or private Champion Data measures. Actual supported years depend on catalogue. | [API requirements](https://api.squiggle.com.au/); contact email required in User-Agent. Private local download; no email hardcoded in distribution. |
| AFL / AFL Data Analysis research archive | Opt-in player-game files from the repository's stated 1897–2025 scope | Earliest years lack many fields. Some rows lack real calendar dates and carry explicit season sort markers. A historical year list does not prove every player's fields are complete. | [Research repository](https://github.com/akareen/AFL-Data-Analysis) MIT software; original AFL Tables-derived data rights remain to be checked independently. Never bundled into a public installer. |
| F1 / Jolpica | Alternative historical race results | Separate source IDs and terms; duplicate overlapping observations must not be added to F1DB totals | [Jolpica project](https://github.com/jolpica/jolpica-f1); CC BY-NC-SA terms differ from F1DB; local optional source. |

The optional AFL importer supports real recorded kicks, handballs, disposals,
marks, tackles, goals, behinds and other supplied fields. It never infers
disposals from club scores. Source access and data ownership are separate;
an MIT repository licence alone does not establish rights over third-party
statistical content.

## Photographs and source separation

The checked bundle has **six distinct licensed photographs**: Lewis Hamilton,
Max Verstappen, LeBron James, Stephen Curry, Michael Jordan and Lionel Messi.
[Portrait attribution](data/portraits/ATTRIBUTION.md) and adjacent manifests
record authors, individual licences, stable IDs, source URLs and checksums.
Hamilton has an additional cache identity for the alternative F1 provider.

On-demand portraits require a unique sport-relevant Wikidata identity and
acceptable Commons rights metadata. Missing or ambiguous photos use an
original silhouette. A licensed Jordan photo does not mean Jordan statistics
are included. Commercial API photo URLs are not copied on the assumption
that a statistics subscription grants image rights.

## Data interpretation limits

- Source IDs prevent same-name people being merged. Club aliases are
  conservative, country-scoped and specific to club entities.
- An absent value means unrecorded/unavailable. A source's explicit zero is
  retained. Ratings require all of their component values.
- A season-total record is not one match. Rates and positions are not
  additive, and career percentages use recorded attempts where possible.
- A total derived from a bounded query describes that displayed subset.
  It must not be advertised as a verified all-time career total.
- Championships can have rule changes, dropped scores or deductions. The
  app's sum of recorded match/race points is not automatically an official
  final table or championship total.
- Importing or caching data does not grant redistribution rights. Submission
  packaging excludes personal databases, API caches and unlicensed downloads.

See [REFERENCES.md](REFERENCES.md) for source references and
[TEST_REPORT.md](TEST_REPORT.md) for checks actually completed in this session.
