# Verification record — 0.6.0 preview

Updated 29 October 2026. Results describe the local engineering preview; they do
not assert that a new public release or Mac package has been published.

## Automated source checks

The main engineering session reports the first complete automated suite passed:
**58 tests plus 26 subtests**. The suite covers data validation, analytical
calculations, archive identity/idempotence/coverage, provider normalization,
portrait licence/cache handling and native chart rendering. These figures are
recorded from the executed suite, not from counting requested features.

Native offline smoke testing produced **20 successful screen cases** and
**zero unhandled errors**. The result was independently read from the local
`artifacts/qa/smoke-results.json`: `success: true`, `native_qt: true`,
`offline: true`. Twenty PNG screenshots are present in `.qa/screenshots/`.

The cases cover Overview; four sport dashboards and four sport profiles; soccer
shot map; F1 grid/finish comparison; F1 pit-stop timeline; teams; comparisons;
leaderboards; raw records; downloads; preferences; sources/about; and the compact
NBA dashboard. The screenshot run uses 1440 × 960 and 1040 × 760 windows. Successful
rendering does not by itself prove every interactive action or licence decision.

That **source-mode test archive** contained 27,687 F1 race-result records across
77 seasons and 860 driver identities; 2,673 NBA player-season rows across five
seasons and 927 identities; 10,658 AFL team-match records across 27 seasons and 18
clubs; and 35 soccer player-match rows from one locally downloaded match. The
football/AFL downloads are local test data, not an assertion that they are bundled
for redistribution. The shipped seed and its different scope are described in
`data/SOURCE_MANIFEST.json`.

## Packaging state

The first Windows production installer build succeeded: the generated
`GameSenseSetup-Windows.exe` was 116,588,433 bytes. Its build report records version
0.6.0, `installer_created: true`, `signed: false` and `published: false`.
The actual `output/package-check-Windows.json` was independently read: packaged
native startup passed with 20 successful screen cases and no unhandled errors.
That check is explicitly `application_only`; it does not claim the production
installer was installed over the user's existing application.

An optimized final rebuild is required after subsequent importer/calculation
changes. Packaging now collects Matplotlib data plus the explicit QtAgg backend
and excludes unused SciPy, Arrow and notebook modules. Record the final rebuilt
installer's report and hash after it completes, rather than treating the first
build's result as proof of later changes. No macOS build or installation on a Mac
has been performed on this Windows workstation.

An existing installed GameSense version was detected. The local installer checker
therefore protects that installation. The separately compiled QA installer uses
a different AppId, name, shortcut and default directory. Its checker compares the
installed executable with the production build, runs the native screen check,
uninstalls the QA copy and verifies the existing production registration is
unchanged. A QA pass must be labelled as such rather than claiming a production
upgrade was installed over the user's working version.

Review actual `output/build-report-*.json`, `output/package-check-*.json`, hashes
and package files after the build. Code signing, notarisation, visible manual
clean-machine checks and public publication remain distinct release checks.

## Release page logic

The actual page JavaScript was executed in a Node VM with controlled API
responses. Valid published asset URLs enable their buttons; missing assets,
untrusted download hosts and unavailable releases do not. A repository with only
published prereleases can expose an existing installer with an explicit preview
label; a missing platform remains unavailable. This tests link activation logic,
not actual deployment of the changed page.

## Remote preservation and CI

Remote review found published v0.4.0-beta.1 and v0.5.0-beta.1 releases newer than
the starting local checkout. They must be preserved. This 0.6.0 preview is intended
for a separate branch/review, not a force push or an overwrite of those assets.
An independent connected GitHub read confirmed default branch `main`, the Pages
deployment trigger on `main`, and a public download configuration pinned to
`v0.5.0-beta.1`. The prepared config preserves that pinned release; publishing a
new preview requires a deliberate subsequent tag update.

The `Verify preview desktop packages` workflow runs for pull requests or a manual
dispatch, building Windows and macOS artifacts and retaining test/package reports
without creating or publishing a release. The tag-driven workflow creates a new
reviewable draft after both platform checks succeed. No remote CI success is
inferred from configuration alone.
