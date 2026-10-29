# Building and reviewing the GameSense 0.6.0 preview

The repository is `dkddhairya26/Game-Sense`; its public download page is `https://dkddhairya26.github.io/Game-Sense/`. Source changes, a local package, CI artifacts and a published release are distinct states. Only actual published installer assets enable the page's download buttons.

Remote review found newer existing public releases than the local starting
checkout, including v0.4.0-beta.1 and v0.5.0-beta.1. Preserve those releases and
reconcile this work through a separate branch/review. These prepared page edits
have not been deployed, and the local 0.6.0 preview does not replace the published
version. A prerelease tag such as `v0.6.0-beta.1` is supported by the workflow.

## Local build

Install the dependencies from `requirements.txt` on the target OS. For a standalone application folder run `python scripts/build.py`. For the installer run `python scripts/build.py --installer`.

Windows needs Inno Setup 6. The build checks `GAMESENSE_ISCC`, `tools/inno/ISCC.exe`, PATH and normal installation locations. It does not silently install a compiler. `build_exe_windows.bat` produces `dist/GameSense/`; `build_windows.bat` produces `output/GameSenseSetup-Windows.exe`. Distribute the full folder if using the executable build, since its dependencies live beside it.

On a Mac, `bash build_macos.sh` builds `dist/GameSense.app` and `output/GameSense-macOS.dmg`. `hdiutil` places the app and an Applications shortcut inside a fresh staging directory. An existing DMG is not overwritten. The app has a local ad-hoc signature for bundle integrity, not an Apple Developer ID signature or notarisation. This Windows workstation cannot prove the macOS build succeeds.

If a production GameSense installation already exists, the package checker
refuses to overwrite its uninstall registration. Compile an isolated QA installer
with `tools/inno/ISCC.exe /DGameSenseQA=1 installer/GameSense.iss`, then run
`python scripts/check_package.py --qa-installer output/GameSenseSetup-Windows-QA.exe`.
The QA build uses a distinct AppId, name, directory and shortcut names. Its
installed executable must match the production build's SHA-256. The report
explicitly identifies a QA installation rather than claiming the production
installer was installed; it also checks that the existing production registry
entry is preserved. Keep the QA package out of public release assets.

Build outputs include a SHA-256 file and a JSON build report. `installer_created: true` means the packaging command produced that file; `installation_tested: false` is deliberately separate. Version 0.6.0 is set in `scripts/build.py` and the Inno script. Windows gets executable/installer version resources; macOS gets bundle version metadata. Original app icons are generated from retained geometric drawing code.

The bundle includes generated third-party notices and the Qt LGPL/GPL texts in
`assets/licenses`. Qt is kept dynamically linked in the directory bundle, with
source-version and replacement instructions in `QT_REDISTRIBUTION.md`. Preserve
these notices and review the exact versions in the generated dependency record
when redistributing a package.

## Required release review

1. Run the complete automated suite and review provider/portrait rights and attribution. Do not bundle a private cache, restricted dataset or unlicensed team logo. Inspect the actual bundled `data/` content and its source manifests.
2. Generate and visually inspect the major app screens at multiple sizes. Exercise search, season changes, profiles, comparisons, team views, charts, exports, downloads, cancellation and offline mode.
3. Run `python scripts/check_package.py --installer output/GameSenseSetup-Windows.exe` on Windows or the equivalent DMG command on a Mac. The check report distinguishes automated startup from manual review. A source-mode pass does not prove the frozen app works.
4. Test the visible installer and application on clean target machines without Python or a development environment. Verify Start Menu/desktop shortcuts, launch, user-data persistence and uninstallation. On macOS, copy into Applications and test the copied app.
5. Review actual source coverage. Do not describe team-level AFL games as athlete records or promise telemetry/complete player history that the provider does not supply.
6. Obtain Windows code signing and Apple Developer ID/notarisation credentials if trusted signed public distribution is required. No paid account or credential is assumed by these scripts.
7. Record the version, commit, test results, build reports and checksums. Review limitations in the release notes.

Unsigned Windows builds can trigger SmartScreen and unsigned/unnotarised Mac builds can be blocked by Gatekeeper. This is a material release limitation, not proof that a download is unsafe or that the package has been tested.

## GitHub Actions

`Verify preview desktop packages` runs on pull requests or manual dispatch. It
tests, renders source screenshots, builds Windows/macOS installers and checks
packaged startup on clean hosted runners, retaining artifacts and reports. It
does not create a release, merge a branch or deploy the public page. Use it to
review this preview against existing remote work before deciding on publication.

`Build and verify desktop installers` can be run manually for artifacts or triggered by a tag such as `v0.6.0`. Tagged versions must match the build script version. Each platform installs dependencies, runs tests, builds an installer and checks installed/mounted startup. Both successful jobs upload artifacts and reports.

After both jobs succeed for a version tag, a final job creates a **draft** GitHub Release with those exact assets. It fails if the release already exists rather than replacing working downloads. This keeps publication reviewable and avoids advertising half-built platform packages. Review the draft and reports, then publish after target-platform checks. A manual build does not create a public release.

The workflow's API permissions and repository access must exist on GitHub. No workflow success or publication is inferred just because the YAML is present. Do not force-push, delete existing releases or use `--clobber` to resolve a release collision; choose an appropriate new version instead.

## Download page

`docs/release-config.js` names the actual repository and preserves the existing
public `v0.5.0-beta.1` selection. The page queries that configured tag and enables
a platform button only when the corresponding asset is returned:

- `GameSenseSetup-Windows.exe`
- `GameSense-macOS.dmg`

Buttons use GitHub's returned `browser_download_url`; no guessed download URL is advertised as working. If the API is unavailable, rate limited or missing an asset, the page keeps that platform unavailable and links to the releases page. An older latest release can remain available until the new draft is published.

After a reviewed new release has actually been published, explicitly update the
configured tag. A local preview build does not change the public selection.
Alternatively, an empty tag opts into latest-release discovery. In that mode,
if GitHub reports no stable release, the page checks published release entries
for an actual preview installer and clearly labels prerelease downloads as
previews. Drafts are never offered. This matters for repositories whose public
versions are currently beta releases.

For GitHub Pages, set the repository Pages source to GitHub Actions. `.github/workflows/pages.yml` deploys `docs/` from `main`. Publishing the page or a release requires authorized remote access; these local edits do not claim that deployment has happened.

Primary packaging references: [PyInstaller usage](https://pyinstaller.org/en/stable/usage.html), [PyInstaller bundle/spec options](https://pyinstaller.org/en/stable/spec-files.html) and [Inno Setup nonadministrative installs](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm).
