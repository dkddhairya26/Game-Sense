# GameSense v0.9.0 Beta — Real Club Profiles Across Leagues

**Native Windows and macOS desktop application.** This beta fixes the exact
reported bug: selecting Aston Villa in the Premier League previously produced
a blank athlete profile and no graphs, despite real football club results being
in the archive.

## Fixed: clubs are clubs, not players

- **Real club profile:** A club displays **matches played, wins, draws,
  losses, goals scored, goals conceded, goal difference and recorded
  league-match points**, with proper labels. AFL teams instead show points
  scored and conceded. The app does not invent player-specific goals, assists
  or xG from a club match score.
- **League-by-league season history:** A club's real match results are grouped
  by **season AND competition**, with a table of W/D/L, for/against,
  difference and observed match points. A separate **Match results** tab
  contains dated fixtures, opponents, scores and source URLs.
- **Full club career switch:** Choose a team in one league/year and explore
  its *other downloaded seasons and competitions*. Turn the switch off to
  analyse only the selected league/year.
- **Stable club IDs:** The earlier app gave "Aston Villa" (older years)
  and "Aston Villa FC" (recent years) different IDs, and also split a team
  across domestic divisions. New conservative country-scoped identities
  reconcile these known aliases and preserve existing historical records
  during upgrade; no user archive must be deleted.
- **No more misleading empty identities:** The picker only lists clubs and
  players actually present in the selected league/year. Profiles for known
  clubs retain their full history when the full-history option is enabled.
- **Teams & Rosters:** Displays real team score summaries, season-by-league
  performance and match logs. Rosters are shown only if an independent
  player-level dataset actually supplies them.

## More real historical football results

- The no-key CC0 OpenFootball starter now requests **2010–11 through
  2026–27**, including *only completed observed matches*. Upstream league-year
  availability varies; missing files do not produce invented games.
- In addition to the English Premier League, La Liga, Bundesliga, Serie A,
  Ligue 1, Eredivisie and Portuguese Primeira Liga, the source also includes
  supported second-tier leagues: the **English Championship, Spanish Segunda,
  German 2. Bundesliga, Italian Serie B and French Ligue 2**.
- This matters for club histories such as Aston Villa competing in the
  Championship before returning to the Premier League. The automatic
  installer startup check specifically exercises that club's real
  multi-competition profile and a nonempty chart.
- Upgrades preserve the previous NBA/F1 archive, AFL results, optional
  player-level downloads, user imports and user settings.

## Source details and limits

OpenFootball's [football.json](https://github.com/openfootball/football.json)
is the **CC0** source for club matches. It provides real match scores for the
published league files but **not** match lineups, individual player goals,
assists or xG. Player-career history requires permitted athlete-specific
providers such as the separately configured optional API-Football or
selected StatsBomb Open Data competitions.

AFL's [Squiggle](https://api.squiggle.com.au/) supplies **club match
results**; the optional separate AFL player research archive is **NOT
prebundled**, because its original AFL Tables-derived source rights need
independent verification. NBA and F1 provider limitations remain unchanged.
No provider guarantees every person, league, season or statistic in history.

## Release verification

GitHub Actions generates the published CC0 starter **from upstream completed
fixtures**, runs the regression test suite and real Qt screenshot checks,
then creates native Windows and Mac packages. Automatic packaging is blocked
if a CC0 starter is sparse, the application fails to render the real Aston
Villa EPL/Championship history, or either installer fails the native packaged
startup check. No installer is digitally code-signed in this beta; manual
clean-machine testing is still recommended.
