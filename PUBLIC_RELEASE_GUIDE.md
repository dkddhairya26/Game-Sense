# GameSense — real public distribution

This repository contains the desktop app source, **automated Windows and macOS installer builds**, and a public download website. **It is not itself a published public release.** The installers are generated on GitHub-hosted Windows/macOS runners, not in this ZIP.

## One-time setup
1. Create a public GitHub repository named `GameSense` under an account you control.
2. Upload all files in this folder **including `.github`** to the repository root, or push them with Git.
3. Edit `docs/release-config.js` and set `repository: 'YOUR_USERNAME/GameSense'`.
4. In GitHub repository Settings → Pages, choose **GitHub Actions** as the source.
5. Commit to `main`. The `Publish GameSense download page` workflow deploys the website at `https://YOUR_USERNAME.github.io/GameSense/` (unless you configure a custom domain).
6. In Actions, run `Build public installers` with **Run workflow** for a first build. Download both build artifacts from the workflow run to test them.
7. On a Windows computer, install and test `GameSenseSetup-Windows.exe`. On a Mac, open and test `GameSense-macOS.dmg`. Validate startup, imported datasets, and all four sport screens.
8. Once tested, create a GitHub Release with tag `v0.2.0` and **publish it first**. The release workflow is triggered by pushing tags, so if you create the tag via GitHub Releases, the jobs will build and attach installer assets to that release. Do not advertise the download page before the release assets appear.
9. The website's buttons link to the latest release assets. Test both links in an incognito browser.

## Security and production limitations
- The Mac DMG is **unsigned and not notarised**. Gatekeeper may block it. Proper public Mac distribution requires Apple Developer ID signing and notarisation on a Mac, plus protected CI secrets and extra workflow steps.
- The Windows installer is **unsigned**. SmartScreen may warn users. Code signing improves trust.
- No automatic updates, analytics backend, account system, or live sports data feed is included.
- Current included sports statistics are **fictional demo data** or user-imported data, not a complete historical dataset.
- CI builds need to be tested on the target OS. Workflow success alone does not prove the app runs correctly.
- Distribution of third-party sports data may require permission or licences.
- The public page is not live until you publish the repository and enable Pages.

## Build and release outputs
- Windows: `GameSenseSetup-Windows.exe` — installer with Start Menu and optional desktop shortcut.
- macOS: `GameSense-macOS.dmg` — disk image containing `GameSense.app` and an Applications shortcut.

## Future production work
Obtain appropriate sports-data licences and build verified API importers, add signed installers, Mac notarisation, automatic updates, error reporting, accessibility checks, and release testing.
