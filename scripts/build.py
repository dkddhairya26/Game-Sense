"""Build native GameSense packages on their target operating system.

Uses PyInstaller's documented CLI: https://pyinstaller.org/en/stable/usage.html.
Every subprocess must succeed before an artifact is reported. Signing, testing
installation and publication are separate release actions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.7.0"


def run(command: list[str]) -> None:
    print("Running:", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def generate_assets() -> None:
    """Draw an original monogram; no third-party logo or athlete photo is used."""
    from PIL import Image, ImageDraw
    target = ROOT / "assets"
    target.mkdir(exist_ok=True)
    image = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, 1000, 1000), radius=220, fill="#101b25")
    draw.rounded_rectangle((85, 85, 939, 939), radius=168, outline="#294339", width=12)
    for x, top in [(235, 598), (385, 475), (535, 355), (685, 230)]:
        draw.rounded_rectangle((x, top, x + 105, 790), radius=26, fill="#8de6bd")
    draw.line([(182, 468), (345, 310), (495, 330), (810, 166)], fill="#f4fbf5", width=30)
    draw.ellipse((778, 134, 842, 198), fill="#f4fbf5")
    image.save(target / "gamesense.png")
    image.save(target / "gamesense.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    image.save(target / "gamesense.icns")


def version_resource() -> Path:
    target = ROOT / "build" / "windows-version.txt"
    target.parent.mkdir(exist_ok=True)
    target.write_text('''VSVersionInfo(
  ffi=FixedFileInfo(filevers=(0, 7, 0, 0), prodvers=(0, 7, 0, 0),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'GameSense'),
    StringStruct('FileDescription', 'GameSense Sports Intelligence'),
    StringStruct('FileVersion', '0.7.0'),
    StringStruct('InternalName', 'GameSense'),
    StringStruct('OriginalFilename', 'GameSense.exe'),
    StringStruct('ProductName', 'GameSense'),
    StringStruct('ProductVersion', '0.7.0')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
''', encoding="utf-8")
    return target


def pyinstaller_command() -> list[str]:
    icon = "gamesense.ico" if sys.platform == "win32" else "gamesense.icns"
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
               "--workpath", str(ROOT / 'build' / ('native-' + VERSION)),
               "--windowed", "--onedir", "--name", "GameSense",
               "--icon", str(ROOT / "assets" / icon),
               "--collect-data", "matplotlib", "--collect-all", "nba_api",
               "--hidden-import", "matplotlib.backends.backend_qtagg",
               "--exclude-module", "PyQt5", "--exclude-module", "PyQt6",
               "--exclude-module", "PySide2", "--exclude-module", "tkinter",
               "--exclude-module", "PySide6.QtPdf", "--exclude-module", "PySide6.QtPdfWidgets",
               "--exclude-module", "PySide6.QtWebEngineCore", "--exclude-module", "PySide6.QtWebEngineWidgets",
               "--exclude-module", "scipy", "--exclude-module", "pyarrow",
               "--exclude-module", "IPython", "--exclude-module", "ipykernel",
               "--exclude-module", "jupyter_client", "--exclude-module", "zmq",
               "--exclude-module", "pytest"]
    for folder in ("assets", "data"):
        if (ROOT / folder).is_dir():
            command.extend(["--add-data", f"{ROOT / folder}{os.pathsep}{folder}"])
    if sys.platform == "win32":
        command.extend(["--version-file", str(version_resource())])
    if sys.platform == "darwin":
        command.extend(["--osx-bundle-identifier", "io.github.dkddhairya26.gamesense"])
    command.append(str(ROOT / "app.py"))
    return command


def windows_installer() -> Path:
    candidates = [os.environ.get("GAMESENSE_ISCC"), str(ROOT / "tools" / "inno" / "ISCC.exe"), shutil.which("ISCC.exe"),
                  str(Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe"),
                  str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe")]
    compiler = next((p for p in candidates if p and Path(p).is_file()), None)
    if compiler is None:
        raise RuntimeError("Inno Setup 6 is required for --installer. Install it from https://jrsoftware.org/isinfo.php, or build without --installer.")
    run([compiler, str(ROOT / "installer" / "GameSense.iss")])
    return ROOT / "output" / "GameSenseSetup-Windows.exe"


def macos_installer() -> Path:
    # A fresh staging folder prevents accidental replacement of user data.
    with tempfile.TemporaryDirectory(prefix="gamesense-dmg-") as staging:
        stage = Path(staging)
        shutil.copytree(ROOT / "dist" / "GameSense.app", stage / "GameSense.app", symlinks=True)
        (stage / "Applications").symlink_to("/Applications", target_is_directory=True)
        destination = ROOT / "output" / "GameSense-macOS.dmg"
        if destination.exists():
            raise FileExistsError(f"Refusing to overwrite {destination}; rename the previous package first.")
        run(["hdiutil", "create", "-volname", "GameSense", "-srcfolder", str(stage),
             "-format", "UDZO", str(destination)])
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", action="store_true", help="Also create the target platform installer/disk image")
    parser.add_argument("--dry-run", action="store_true", help="Print packaging command without running PyInstaller")
    parser.add_argument("--assets-only", action="store_true", help="Generate original app icons only")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args()
    if sys.platform not in ("win32", "darwin"):
        parser.error("Build Windows on Windows and macOS on macOS; cross compiling is unsupported.")
    generate_assets()
    from notices import generate as generate_notices
    generate_notices(ROOT)
    if args.assets_only:
        return 0
    command = pyinstaller_command()
    if args.dry_run:
        print(subprocess.list2cmdline(command))
        return 0
    run(command)
    if sys.platform == "darwin":
        bundle = ROOT / "dist" / "GameSense.app"
        plist_path = bundle / "Contents" / "Info.plist"
        with plist_path.open("rb") as handle:
            plist = plistlib.load(handle)
        plist.update(CFBundleShortVersionString=VERSION, CFBundleVersion=VERSION,
                     NSHighResolutionCapable=True)
        with plist_path.open("wb") as handle:
            plistlib.dump(plist, handle)
        # Re-establish the local ad-hoc signature after updating the bundle.
        # This is not an Apple Developer ID signature or notarisation.
        run(["codesign", "--force", "--deep", "--sign", "-", str(bundle)])
    executable = (ROOT / "dist" / "GameSense" / "GameSense.exe" if sys.platform == "win32"
                  else ROOT / "dist" / "GameSense.app" / "Contents" / "MacOS" / "GameSense")
    if not executable.is_file():
        raise FileNotFoundError(f"PyInstaller did not produce {executable}")
    output = ROOT / "output"
    output.mkdir(exist_ok=True)
    artifact = (windows_installer() if sys.platform == "win32" else macos_installer()) if args.installer else executable
    if not artifact.is_file():
        raise FileNotFoundError(f"Missing build output: {artifact}")
    with artifact.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    suffix = "Windows" if sys.platform == "win32" else "macOS"
    (output / f"SHA256SUMS-{suffix}.txt").write_text(f"{digest}  {artifact.name}\n", encoding="ascii")
    report = {"version": VERSION, "platform": platform.platform(), "python": sys.version,
              "artifact": str(artifact.relative_to(ROOT)), "sha256": digest,
              "installer_created": bool(args.installer), "signed": False,
              "installation_tested": False, "published": False}
    (output / f"build-report-{suffix}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Build created: {artifact}\nSHA-256: {digest}\nInstallation testing, signing and publication remain separate steps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
