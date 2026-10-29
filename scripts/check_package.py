"""Exercise a built application or a newly installed package in an isolated folder.

This checks native startup and install/uninstall plumbing. It does not replace a
person testing the visible application on a clean target machine.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def smoke(executable: Path, user_data: Path) -> dict:
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen", GAMESENSE_DATA_DIR=str(user_data))
    # The exhaustive ~25-screen visual suite runs separately against source.
    # Installed-app QA focuses on representative sport pages plus a required
    # full-history EPL/Championship club-profile regression (still real Qt).
    subprocess.run([str(executable), "--smoke-test", "--package-smoke"],
                   env=environment, check=True, timeout=210)
    report = json.loads((user_data / 'smoke-results.json').read_text(encoding='utf-8'))
    if not report.get('success') or not report.get('native_qt') or not report.get('screens'):
        raise RuntimeError('Packaged application did not produce a successful native screen report')
    clubs = report.get('club_checks') or []
    if not clubs or not any(x.get('success') for x in clubs):
        raise RuntimeError('Installed app did not verify a real cross-league club profile')
    return report


def registration_snapshot(qa=False) -> dict:
    import winreg
    identity = '{B246EE84-A56D-4BB0-9C35-851205C768D9}' if qa else '{6F0C5A20-41B6-4DB4-B5D9-A9BFA85A7201}'
    key = 'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\' + identity + '_is1'
    registrations = {}
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view) as entry:
                    values = {}
                    for field in ('DisplayName', 'DisplayVersion', 'InstallLocation', 'UninstallString'):
                        try:
                            values[field] = winreg.QueryValueEx(entry, field)[0]
                        except FileNotFoundError:
                            pass
                    registrations[str(hive) + ':' + str(view)] = values
            except FileNotFoundError:
                pass
    return registrations


def assert_no_registered_installation(qa=False) -> None:
    """Do not replace a real user's uninstall registration during a local check."""
    if registration_snapshot(qa=qa):
        raise RuntimeError('A GameSense installation is already registered. Use --application or test the installer on a clean account/machine.')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--application", type=Path)
    parser.add_argument("--installer", type=Path)
    parser.add_argument("--qa-installer", type=Path, help="Test an isolated GameSenseSetup-Windows-QA.exe built with /DGameSenseQA=1")
    parser.add_argument("--report", type=Path, default=Path("output/package-check.json"))
    args = parser.parse_args()
    if sum(bool(value) for value in (args.application, args.installer, args.qa_installer)) != 1:
        parser.error("Choose exactly one of --application, --installer or --qa-installer")
    if args.qa_installer and (sys.platform != 'win32' or args.qa_installer.name != 'GameSenseSetup-Windows-QA.exe'):
        parser.error("--qa-installer requires the Windows QA compiler output named GameSenseSetup-Windows-QA.exe")
    installer = args.installer or args.qa_installer
    checks = []
    reports = []
    with tempfile.TemporaryDirectory(prefix="gamesense-install-check-") as folder:
        base = Path(folder)
        user_data = base / "user-data"
        user_data.mkdir()
        sentinel = user_data / "keep-user-data.txt"
        sentinel.write_text("User data must survive uninstall.", encoding="utf-8")
        if args.application:
            reports.append(smoke(args.application.resolve(), user_data))
            checks.append("packaged_native_startup")
        elif sys.platform == "win32":
            assert_no_registered_installation(qa=bool(args.qa_installer))
            production_before = registration_snapshot() if args.qa_installer else None
            application = base / "GameSense"
            subprocess.run([str(installer.resolve()), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                            "/NORESTART", "/SP-", f"/DIR={application}"], check=True, timeout=180)
            executable = application / "GameSense.exe"
            if not executable.is_file():
                raise RuntimeError("Installer did not create GameSense.exe")
            if args.qa_installer:
                reference = Path(__file__).resolve().parents[1] / 'dist' / 'GameSense' / 'GameSense.exe'
                with executable.open('rb') as handle:
                    installed_hash = hashlib.file_digest(handle, 'sha256').hexdigest()
                with reference.open('rb') as handle:
                    reference_hash = hashlib.file_digest(handle, 'sha256').hexdigest()
                if installed_hash != reference_hash:
                    raise RuntimeError('QA installer executable differs from the current production application build')
                checks.append('qa_executable_matches_production_build')
            checks.append("silent_install")
            try:
                reports.append(smoke(executable, user_data))
                checks.append("installed_native_startup")
            finally:
                subprocess.run([str(application / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                                "/NORESTART"], check=True, timeout=120)
            deadline = time.monotonic() + 10
            while executable.exists() and time.monotonic() < deadline:
                time.sleep(.1)
            if executable.exists():
                raise RuntimeError("Uninstaller left the application executable")
            if not sentinel.is_file():
                raise RuntimeError("Uninstaller removed user data")
            checks.extend(["silent_uninstall", "user_data_preserved"])
            if args.qa_installer:
                if registration_snapshot() != production_before:
                    raise RuntimeError('Existing production install registration changed during QA')
                checks.append('existing_production_registration_preserved')
        elif sys.platform == "darwin":
            mount = base / "mounted"
            mount.mkdir()
            subprocess.run(["hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", str(mount),
                            str(installer.resolve())], check=True, timeout=90)
            try:
                reports.append(smoke(mount / "GameSense.app" / "Contents" / "MacOS" / "GameSense", user_data))
                checks.extend(["dmg_mount", "mounted_native_startup"])
            finally:
                subprocess.run(["hdiutil", "detach", str(mount)], check=True, timeout=90)
        else:
            parser.error("Installer checks require Windows or macOS")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({"passed": checks, "application_reports": reports,
                                      "installer_kind": 'isolated_qa' if args.qa_installer else 'production' if args.installer else 'application_only',
                                      "production_installer_tested": bool(args.installer),
                                      "manual_interactive_installation_tested": False,
                                      "code_signature_verified": False}, indent=2), encoding="utf-8")
    print("Passed:", ", ".join(checks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
