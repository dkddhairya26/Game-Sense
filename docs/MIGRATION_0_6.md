# 0.6 preview migration from the public 0.5 source

This preview is prepared on a separate branch whose parent is the existing public
`main` commit `51cbbb8da1b990222e0ac6f5e8bdc954d9c46d5b`. Existing 0.4 and 0.5
release assets are preserved. The development workspace originally contained an
older checkout, so the remote source was reviewed before preparing this branch.

The new indexed `Archive` replaces the old `history.py` catalogue and
`DownloadWorker` protocol. Provider metadata, paging, immediately committed
batches, cancellation, caching and resumability now have dedicated archive and
HTTP tests. Tests and the screenshot script tied to the retired widget/provider
APIs are replaced by those regression checks and `app.py --smoke-test`.

The useful 0.5 import normalizer and legacy `storage.py` are retained. The importer
now preserves explicit record grain and uses the new canonical shooting fields;
ambiguous column mappings are rejected. The old NBA weighted-season-average
regression is retained in `tests/test_statistics.py`: 10 points per game over
10 games plus 30 over 30 games produces 1,000 points and 25 points per game,
not an unweighted 20. New provider season totals use their actual game counts.

The new desktop uses a separate user-data archive. It does not delete the legacy
`~/GameSenseData/gamesense.sqlite3`. Export permitted legacy records and import
them through Historical Records, keeping their season-average metadata. Exported
record identities are isolated when reimported so imports cannot overwrite the
original provider's records. Legacy storage functions remain available to read
the original file.

The former unrestricted NBA.com archive downloader is replaced by explicitly
licensed BoxScore Lab records. Its five-season scope is narrower and is stated
in the interface and documentation. The MIT licence for API client software is
not treated as permission to redistribute or compile the league's full data.
F1DB adds a distributable historical F1 seed; StatsBomb adds local research-only
football events. AFL remains team-result scope unless a licensed player dataset
is imported. These are explicit coverage limits, not completed all-era claims.

Generated Python bytecode is removed from version control. Source verification
and native Windows/macOS builds run in the preview workflow; publication is a
separate step after checking the actual platform results.
