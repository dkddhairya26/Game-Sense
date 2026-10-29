"""Package tracked source and verified public installers for the project ZIP.

The archive is made from Git, never from a recursive workspace copy: personal
downloads, API contact settings, caches and build folders are excluded.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TAG = 'v0.6.0-beta.1'
EXPECTED = {
    'GameSenseSetup-Windows.exe': '1e6fe0a434ef2e53a73e42f8322f676b4c654a111520b0005a8b4dc729ed8491',
    'GameSense-macOS.dmg': '0deef44c0cbecb5137dbd47919ede6b2be6a9cc13c2da426b013eb8550bafafb',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default=TAG, help='Git source snapshot; installers remain the stated public release')
    parser.add_argument('--output', type=Path, default=ROOT / 'output' / 'Dhiraj Dhairya - Project.zip')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Refusing to replace an existing submission ZIP: ' + str(args.output))
    for name, expected in EXPECTED.items():
        with (ROOT / 'output' / name).open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != expected:
            raise ValueError('Installer does not match the published release: ' + name)
    source_sha = subprocess.check_output(['git','rev-parse',args.ref],cwd=ROOT,text=True).strip()
    source_zip = subprocess.check_output(['git','archive','--format=zip',args.ref],cwd=ROOT)
    reports = ['SHA256SUMS-Windows.txt','SHA256SUMS-macOS.txt','build-report-Windows.json',
               'build-report-macOS.json','package-check-Windows.json','package-check-macOS.json',
               'test-results-Windows.xml','test-results-macOS.xml']
    start = f'''GAMESENSE 0.6 PREVIEW — PROJECT PACKAGE

Windows x64: open installers/GameSenseSetup-Windows.exe.
macOS: open installers/GameSense-macOS.dmg, then copy the app to Applications.
The Mac build is for Apple Silicon; bundled dependencies require macOS 14+.
Both packages are unsigned previews; the Mac build is not notarised.
End users do not need Python, Git, VS Code or terminal commands.

The app opens with permitted real F1 results and recent NBA season statistics.
Football downloads use the provider's local research terms. AFL downloads are
team results, not individual player statistics. Historical coverage is incomplete
and is shown in the app. No fictional demo records are mixed with real history.

Source and documentation: source/
Actual platform tests, install/startup reports and checksums: verification/
Source snapshot: {source_sha}
Public installers: https://github.com/dkddhairya26/Game-Sense/releases/tag/{TAG}

Read source/docs/AI_ASSISTANCE.md and ASSESSMENT_ALIGNMENT.md before submission.
The student must review the work, retain development evidence, and write their
own personal reflection and supervised validation response.

No personal archive, contact email, API cache or development environment is
included in this package. Data rights and image credits accompany the source.
'''
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as target:
        target.writestr('START_HERE.txt', start)
        with zipfile.ZipFile(io.BytesIO(source_zip)) as source:
            for entry in source.infolist():
                if not entry.is_dir():
                    target.writestr('source/' + entry.filename, source.read(entry))
        for name in EXPECTED:
            target.write(ROOT / 'output' / name, 'installers/' + name, compress_type=zipfile.ZIP_STORED)
        for name in reports:
            target.write(ROOT / 'output' / name, 'verification/' + name)
        target.writestr('verification/RELEASE_MANIFEST.json', json.dumps({'tag': TAG, 'source_commit':source_sha, 'installer_sha256':EXPECTED},indent=2))
    with zipfile.ZipFile(args.output) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError('ZIP integrity check failed: ' + bad)
        names = archive.namelist()
        if any('/.git/' in name or '/artifacts/' in name or 'archive.sqlite3' in name for name in names):
            raise ValueError('Private workspace content entered the archive')
    print(str(args.output))
    print(f'{args.output.stat().st_size:,} bytes; ZIP integrity and installer checksums verified.')


if __name__ == '__main__':
    main()
