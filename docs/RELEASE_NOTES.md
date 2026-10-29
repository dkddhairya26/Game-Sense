# GameSense 0.7.0 — Real History & Visual Analytics Preview

This is a new native Windows/macOS **preview**, not a claim of universal
historical sports coverage. Only tested release assets should be published.

## What's new

- Six simultaneous, distinct sport-specific visualisations on every dashboard,
  plus an independent customizable deep-dive plot with hover/export features.
- Official NBA Stats optional on-demand connector, capable of requesting
  1946–47 onward historical player-season averages when NBA.com permits the
  network request. This does **not** add older seasons to the bundled database.
- API-Football (API-Sports) authenticated, user-key-only integration for
  competition player statistics, ID-verified player searching, and available
  player-season history. Account pricing, years and league coverage depend
  on provider terms. Player photos are not republished from the provider.
- Free, direct Cristiano Ronaldo **Portugal 2022 World Cup** event-data action
  from StatsBomb Open Data. This provides real recorded match events, not a
  complete Manchester United / Madrid / Juventus / Al Nassr career.
- Direct historical-data discovery actions on sport dashboards; improved
  explicit unavailable-data states and real source attribution.
- Additional provider regression fixtures, verification for Windows/macOS
  packaging, and privacy-conscious handling of API keys.

## What is not solved

- The bundled source archive retains its genuinely available data: F1DB race
  records from 1950 to provider release; BoxScore Lab NBA player seasons
  from 2022–23 onward. Those older NBA and Ronaldo club seasons must be
  requested and actually returned by an approved provider.
- No guaranteed data for all NBA seasons back to 1946 if NBA.com rejects
  requests. No complete historical player records for every football league.
- AFL historical downloads remain club-match results only: full athlete
  statistics need a correctly licensed AFL provider or user import.
- No invented event coordinates, shots, telemetry, stats or photographs.
- These packages are unsigned preview builds. Manual clean-machine
  Windows/macOS installation and API accounts still require user verification.

**Do not confuse mocked provider unit tests with successful real API access.**
See docs/HISTORY_V07.md for the specific connectors, terms, verification
checklist, and explicit data source limitations.

The new preview is published only after both platforms build and pass the
automated native application/package startup checks; those checks cannot
guarantee the remote sports data providers are accessible from a user's IP.
