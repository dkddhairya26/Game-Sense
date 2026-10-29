# Verification record — 0.6.0 preview

Updated 29 October 2026. New public preview **v0.6.0-beta.1** was published after
both native platform checks passed. Final release evidence is recorded below;
earlier local/CI results are retained as development history.

## Automated source checks

The main engineering session reports the reviewed preview snapshot passed:
**76 tests plus 26 subtests**. The suite covers data validation, analytical
calculations, archive identity/idempotence/coverage, provider normalization,
portrait licence/cache handling and native chart rendering. These figures are
recorded from the executed suite, not from counting requested features.

Native offline smoke testing produced **20 successful screen cases** and
**zero unhandled errors**. The result was independently read from the local
`artifacts/qa/smoke-results.json`: `success: true`, `native_qt: true`,
`offline: true`. Twenty PNG screenshots are present in `.qa/screenshots/`.
The current source report also records four passing real-identity searches:
Lionel Messi, LeBron James, Collingwood and Lewis Hamilton. These checks apply to
the downloaded local test archive; a fresh bundled archive has fewer sources.

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

The preliminary isolated QA installer also passed. Its actual
`output/package-check-Windows-QA.json` records a matching production executable
hash, silent install, native startup, silent uninstall, user-data preservation and
preservation of the existing production uninstall registration. All 20 installed
screen cases passed with zero unhandled errors. The report explicitly says
`installer_kind: isolated_qa` and `production_installer_tested: false`.

That initial local build predates later importer/calculation/search changes.
The final reviewed snapshot was subsequently rebuilt and verified by native CI
on both operating systems, as described below. Optimized packaging collects
Matplotlib data plus the explicit QtAgg backend and excludes unused SciPy, Arrow
and notebook modules. The final CI artifacts are evidence for that reviewed
snapshot; the earlier local package is not. macOS was built on GitHub's native
Mac runner, not on this Windows workstation.

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
without creating or publishing a release. The tag-driven release workflow
implements the user's publication request by publishing a new prerelease after
both platform checks succeed, with `--latest=false` and an existing-release guard.
Manual dispatch does not publish. No remote CI success is inferred from
configuration alone.

Pull request #1 reviews branch `codex/gamesense-0-6-preview`, snapshot
`8a77952`. Its actual cross-platform verification run is
https://github.com/dkddhairya26/Game-Sense/actions/runs/40802119873.
The previous run `40801779395` was cancelled when superseded by this common-name
search fix; it is not recorded as a successful build or a dependency failure.
At the first monitoring check, both OS jobs were installing dependencies.
The native Mac job subsequently completed successfully. Its actual log records
`76 passed` and `26 subtests passed`, successful source screenshots, DMG creation,
hdiutil image verification, and `Passed: dmg_mount, mounted_native_startup`.

The Mac job is `123212581869`; artifact `12865909562` is named
`GameSense-preview-macOS`. The artifact ZIP is 83,445,853 bytes with SHA-256
`c3c2be76f27ced3795f5cb0913ebf8875a2f8bcec590bc492a05dd10809468d0`.
The **DMG itself** has SHA-256
`bc56d6abba553b9004b78bef5b95335e94420fc8313e5c5bd40f7b6b80ba5458`.
The package remains unsigned by a trusted Developer ID and not notarised; manual
clean-machine interaction remains unverified.

The Windows job `123212582138` also completed successfully. Its log records
`76 passed` and `26 subtests passed`, successful native screenshots and installer
creation, then `Passed: silent_install, installed_native_startup,
silent_uninstall, user_data_preserved`. This is an actual production-identity
installation on a clean Windows runner, separate from the local isolated QA test.

Windows artifact `12866418491` is named `GameSense-preview-Windows`. Its ZIP is
68,466,735 bytes with SHA-256
`52c07280cf08d453b93cded41d15ccb7000e704bde6a34cd28fd2867a3b53dae`.
The **Windows installer itself** has SHA-256
`5d2a302f4f9a0bf94f24564e6d7713fb6aa7a87e6cf60a44b0c58c349d47eed7`.
Both platform artifacts correspond to source commit
`8a77952249fe828252a74efb1f03ff5b84f2e502`.

These hashes identify the verification-run files. A subsequent release build can
have different bytes; use the SHA256SUMS files accompanying that release when
checking its downloads. Both automated platform checks passed. Trusted signing,
notarisation and manual interactive clean-machine tests remain unverified.

## Final published release — commit 920f3af

Release workflow
[40803379902](https://github.com/dkddhairya26/Game-Sense/actions/runs/40803379902)
completed both package jobs and `publish-preview` successfully. The source tag
resolves to `920f3af279130b24c933e81da624eeb72c888b79`, incorporating the final
roster sizing, initial leaderboard order, explorer column order and chart spacing
fixes. Runtime code was frozen before these builds.

The GitHub release API independently confirmed release `427385422`,
`draft: false`, `prerelease: true`, published 29 October 2026, with all ten assets
uploaded. Public release:
https://github.com/dkddhairya26/Game-Sense/releases/tag/v0.6.0-beta.1.

| Public installer | Bytes | SHA-256 |
| --- | ---: | --- |
| `GameSenseSetup-Windows.exe` | 66,985,434 | `1e6fe0a434ef2e53a73e42f8322f676b4c654a111520b0005a8b4dc729ed8491` |
| `GameSense-macOS.dmg` | 83,978,163 | `0deef44c0cbecb5137dbd47919ede6b2be6a9cc13c2da426b013eb8550bafafb` |

The release includes corresponding SHA256SUMS, build reports, package-check
reports and JUnit results. Windows job `123216479904` logged 76 passing tests plus
26 subtests and passed silent install, installed native startup, uninstall and
user-data preservation. Mac job `123216479668` logged the same test counts and
passed DMG mount and mounted native startup. Publication job `123217733368`
succeeded after those package checks. Existing v0.4/v0.5 releases were not
overwritten; the new release does not change latest stable.

Final release-run artifacts are Windows `12867212065` and Mac `12866853924`.
These ZIP artifacts are separate from the public installer files and hashes
listed above.

The final Mac log explicitly reports `EXE target arch: arm64`, using the native
macOS 26 arm64 runner. Qt 6.12 and NumPy 2.5.4 wheel tags require macOS 14+.
Therefore the package is labelled **Apple Silicon, macOS 14+ dependency
requirement**, with startup **tested on macOS 26**. Intel compatibility and startup
on every earlier supported version are not claimed. Developer ID signing,
notarisation and manual interactive clean-machine checks remain unverified.

The actual final page JavaScript passed **ten offline cases**. The two real
published installers enable; missing assets/platforms, untrusted hosts, draft
responses, unfinished/zero-byte uploads, missing tags, rate limits and invalid
configuration leave the relevant downloads disabled. The test also verified the
pinned v0.6.0-beta.1 endpoint and explicit Windows x64 / Mac Apple Silicon labels.
