# Development evidence log

## 28 October 2026 — audited baseline

The starting repository identifies itself as a cross-platform prototype v2. It had a native PySide6 interface, five fictional competitors per sport, a small set of fixed metrics, four basic views, local replace-all SQLite imports and one rolling custom-rating line chart. The NBA and F1 artwork keys did not match the application's actual sport keys, so those themes could fall back to soccer. The release page repository was blank. Windows/macOS workflows could overwrite release assets and did not prove installed startup.

The user's updated request prioritizes real historical data, real licensed portraits, deeper interactive figures, detailed profiles, responsive background work and actual native installer delivery. The supplied proposal and task were read to retain the common data-processing pipeline, four-sport scope, clear calculations, source ethics and testing evidence.

## 28 October 2026 — implementation work

Parallel engineering work covers an indexed historical archive and provider transport, native interface and analytical correctness, licensed Wikimedia portrait loading and native charts, plus release scripts/documentation. SQLite stores committed batches and provider/season coverage. Portrait requests require explicit licence evidence. Charts use observed measurements; field decorations are not presented as real event locations.

Release scripts now generate original icons, version metadata and SHA-256 reports, create native packages only on their target OS and offer isolated package checks. The workflow assembles a new draft release only after both platform jobs succeed and refuses to overwrite an existing release. The public page checks GitHub's returned assets before enabling a platform download.

## Evidence and outcomes

This section records performed checks only; it must not be read as proof of planned checks.

| Check | Result/evidence |
| --- | --- |
| Read both supplied PDFs | Completed using PySide6 QtPdf text extraction; task and proposal requirements are mapped in `ASSESSMENT_ALIGNMENT.md`. |
| Generate original application icons | Completed with `python scripts/build.py --assets-only`; `assets/gamesense.png`, `.ico` and `.icns` generated. |
| Inspect Windows packaging command | Completed with `python scripts/build.py --dry-run`; no package was built by that command. |
| Download page activation logic | Actual page JavaScript evaluated in a Node VM: both valid published assets activate; missing assets, an untrusted download URL and a missing release leave buttons inactive. |
| Windows Inno Setup availability at initial audit | Not found in PATH or the default Program Files (x86) location. A later installer build requires the compiler to be installed. |
| Automated application/analytics/provider/chart tests | Final source suite: 58 tests plus 26 subtests passed, as reported by the main engineering session. |
| Native screens and screenshots | Current `artifacts/qa/smoke-results.json` independently read: success=true, 20 successful cases, zero unhandled errors. Twenty screenshots present in `.qa/screenshots/`; includes 1440×960 and compact1040×760 rendering. |
| Native executable/installer builds | First Windows build succeeded: production installer 116,588,433 bytes, unsigned/unpublished. Optimized rebuild pending subsequent source changes; final hash/report must be checked. |
| Packaged native startup | `output/package-check-Windows.json` independently read: application_only check passed, 20 screens, zero unhandled errors. Production install not claimed; isolated QA check separate. |
| macOS build and installation on a Mac | Not performed on this Windows workstation. CI configuration is provided; no successful Mac run is claimed. |
| Public release publication | Not performed by the documentation/packaging work. Existing working releases were not replaced. |
| Clean machine manual tests or student personal review | Not performed or inferred. |

Keep real command outputs, screenshots, source manifests, teacher-shared progress evidence and the student's own review alongside this record. Use version control history to distinguish code creation from subsequent verification and personal modifications.

## 29 October 2026 — resumed release preparation

The Windows Inno Setup compiler is now present in `tools/inno/ISCC.exe`, obtained
and verified by the main engineering session. Qt LGPL/GPL texts were downloaded
from GNU/the Qt Project's official source. Packaging now generates dependency
licence notices and Qt dynamic-library replacement/source-version guidance.
The app remains a directory bundle with replaceable Qt libraries; the build
excludes unused QtPdf and QtWebEngine Python modules. Installer results must be
recorded after the actual build and checks complete.

The final source test and screen results are recorded in `VERIFICATION.md`.
The first Windows production build succeeded and packaged startup passed.
After subsequent importer/calculation changes, an optimized final rebuild is
required; the initial build is not evidence for unbuilt later code.
Existing public 0.4/0.5 releases and the installed application are preserved.
The isolated QA installer uses a separate identity for install/uninstall checks.
A pull-request/manual Windows/macOS verification workflow now produces review
artifacts without requiring a release tag or publishing a release.

An independent connected GitHub read confirmed `main` is the default branch and
the public page configuration pins `v0.5.0-beta.1`. That pinned selection is
preserved in the prepared configuration. The page supports explicit release
tags; latest/prerelease discovery is used only when a reviewer chooses an empty
tag. The Pages workflow remains a main-branch deployment and has not been run by
this work.
