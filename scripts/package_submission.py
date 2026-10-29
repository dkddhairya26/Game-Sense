"""Create a reviewable assessment package from a named Git snapshot.

Source comes from ``git archive``, not a recursive workspace copy: private
archives, credentials, caches and development environments must stay local.
Installer checksums and successful target-platform reports are required when
including installers. A source-only ZIP is explicitly labelled as such.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TAG = "v0.10.0-beta.1"
PLATFORMS = {"Windows": "GameSenseSetup-Windows.exe", "macOS": "GameSense-macOS.dmg"}
DOCUMENTS = (
    "README.md", "USER_GUIDE.md", "TECHNICAL_DOCUMENTATION.md", "DATA_SOURCES.md",
    "ALGORITHMS.md", "TEST_REPORT.md", "PROPOSAL_ALIGNMENT.md",
    "DESIGN_DECISIONS.md", "REFERENCES.md", "REFLECTION_EVIDENCE.md",
)


def _safe_source_path(name: str) -> bool:
    """Use path components, so a harmless filename cannot escape the archive."""
    path = PurePosixPath(name)
    forbidden = {".git", ".qa", ".venv", "venv", "__pycache__", "node_modules",
                 "http", "output", "dist", "build"}
    return not (path.is_absolute() or ".." in path.parts
                or forbidden.intersection(path.parts)
                or path.name == ".env" or path.name.startswith(".env.")
                or path.suffix.lower() in {".sqlite", ".sqlite3", ".db", ".pyc", ".pem", ".key"})


def _checksum_file(path: Path, installer: str) -> str:
    """Read the build's checksum; never substitute a previous release's hash."""
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([a-fA-F0-9]{64})\s+\*?(.+)", line.strip())
        if match and Path(match[2]).name == installer:
            return match[1].lower()
    raise ValueError(f"No SHA-256 for {installer} in {path.name}")


def verified_installers(artifacts: Path, version: str, source_commit: str):
    """Check both OS artifacts and retain the reports supporting that claim."""
    checksums, reports = {}, []
    for platform, name in PLATFORMS.items():
        checks = artifacts / f"SHA256SUMS-{platform}.txt"
        expected = _checksum_file(checks, name)
        with (artifacts / name).open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError("Installer does not match build checksum: " + name)
        build_path = artifacts / f"build-report-{platform}.json"
        build = json.loads(build_path.read_text(encoding="utf-8"))
        if build.get("version") != version or not build.get("installer_created"):
            raise ValueError("Build version does not match requested release: " + platform)
        if build.get("sha256") != expected:
            raise ValueError("Build report does not describe this installer checksum: " + platform)
        if build.get("source_commit") != source_commit:
            raise ValueError("Installer and requested source snapshot have different commits: " + platform)
        package_path = artifacts / f"package-check-{platform}.json"
        package = json.loads(package_path.read_text(encoding="utf-8"))
        # Each nested smoke report must explicitly record a successful run.
        smoke_reports = package.get("application_reports", [])
        if not package.get("production_installer_tested") or not smoke_reports or not all(r.get("success") for r in smoke_reports):
            raise ValueError("Missing successful native package report: " + platform)
        checksums[name] = expected
        reports.extend([checks, build_path, package_path])
        junit = artifacts / f"test-results-{platform}.xml"
        if not junit.is_file():
            raise FileNotFoundError("Missing target-platform test evidence: " + str(junit))
        test_report = ET.parse(junit).getroot()
        if test_report.findall('.//failure') or test_report.findall('.//error') or not test_report.findall('.//testcase'):
            raise ValueError("Target-platform test evidence is empty or contains failures: " + platform)
        reports.append(junit)
    return checksums, reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD", help="Committed Git source snapshot")
    parser.add_argument("--tag", default=DEFAULT_TAG)
    parser.add_argument("--artifacts", type=Path, default=ROOT / "output")
    parser.add_argument("--evidence", type=Path, help="Explicit directory of reviewed PNG/JSON/XML/CSV/MD/TXT evidence")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "Dhiraj Dhairya - Project.zip")
    parser.add_argument("--source-only", action="store_true", help="Omit installers; do not claim native packages are included")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refusing to replace an existing submission ZIP: " + str(args.output))
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", args.tag):
        raise ValueError("Use a separately versioned release tag")
    version = args.tag[1:].split("-", 1)[0]
    source_sha = subprocess.check_output(["git", "rev-parse", args.ref], cwd=ROOT, text=True).strip()
    source_zip = subprocess.check_output(["git", "archive", "--format=zip", args.ref], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(source_zip)) as source:
        source_names = [e.filename for e in source.infolist() if not e.is_dir()]
        missing = [name for name in DOCUMENTS if name not in source_names]
        if missing:
            raise ValueError("Required documents absent from committed snapshot: " + ", ".join(missing))
        unsafe = [name for name in source_names if not _safe_source_path(name)]
        if unsafe:
            raise ValueError("Private/generated content tracked in source: " + ", ".join(unsafe[:10]))
    checksums, reports = ({}, []) if args.source_only else verified_installers(args.artifacts, version, source_sha)
    manifest = {"tag": args.tag, "source_commit": source_sha,
                "installer_sha256": checksums, "source_only": args.source_only,
                "manual_interactive_installation_verified": False,
                "student_review_record": "Student must complete their own review; not supplied by automation."}
    package_kind = "SOURCE AND EVIDENCE ONLY — NO INSTALLERS" if args.source_only else "SOURCE, EVIDENCE AND VERIFIED NATIVE INSTALLERS"
    start = f"""GAMESENSE {args.tag} — {package_kind}

Source and documentation: source/README.md and source/USER_GUIDE.md.
Actual test logs and screenshots, where supplied: verification/.
Exact source snapshot: {source_sha}
Release reference: https://github.com/dkddhairya26/Game-Sense/releases/tag/{args.tag}
The reference alone does not establish that a release has been published.

Windows x64 installer, if included: installers/GameSenseSetup-Windows.exe.
macOS Apple Silicon image, if included: installers/GameSense-macOS.dmg.
The Mac build requires macOS 14+; no Intel Mac package is promised.
Unsigned beta packages are not trusted-code-signed or notarised.
End users do not need Python when installing the native packages.

Read DATA_SOURCES.md for the distinction between club match records,
player seasons and optional restricted downloads. Missing values are never
evidence of zero performance. Cached data remain usable offline.

Read PROPOSAL_ALIGNMENT.md and REFLECTION_EVIDENCE.md before assessment use.
These files contain AI-assisted engineering evidence. The student must
critically review and modify assisted work, retain teacher-shared progress,
and supply their own personal reflection. The supervised validation is No AI;
no answers for that task have been written in this package.

No personal archive, contact email setting, API cache or environment is included.
Dataset and photograph attribution accompanies the source.
"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as target:
        target.writestr("START_HERE.txt", start)
        with zipfile.ZipFile(io.BytesIO(source_zip)) as source:
            for entry in source.infolist():
                if not entry.is_dir():
                    target.writestr("source/" + entry.filename, source.read(entry))
        for name in checksums:
            target.write(args.artifacts / name, "installers/" + name, compress_type=zipfile.ZIP_STORED)
        for report in reports:
            target.write(report, "verification/" + report.name)
        if args.evidence:
            evidence = args.evidence.resolve(strict=True)
            permitted = {".png", ".json", ".xml", ".csv", ".md", ".txt"}
            for item in sorted(evidence.rglob("*")):
                if item.is_file() and item.suffix.lower() in permitted:
                    relative = item.relative_to(evidence).as_posix()
                    if not _safe_source_path(relative):
                        raise ValueError("Unsafe evidence path: " + relative)
                    target.write(item, "verification/evidence/" + relative)
        target.writestr("verification/RELEASE_MANIFEST.json", json.dumps(manifest, indent=2))
    with zipfile.ZipFile(args.output) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError("ZIP integrity check failed: " + bad)
    with args.output.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    print(str(args.output))
    print(f"{args.output.stat().st_size:,} bytes; SHA-256 {digest}; ZIP integrity checked.")


if __name__ == "__main__":
    main()
