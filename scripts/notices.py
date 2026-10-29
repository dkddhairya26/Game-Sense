"""Retain installed dependency licence texts with every frozen distribution.

Qt/PySide6 are shipped as replaceable dynamic libraries in the onedir bundle.
This notice does not choose a licence for the user's own application code.
"""
from __future__ import annotations
import importlib.metadata as metadata
from pathlib import Path
import re
import sys

PACKAGES = ('PySide6', 'PySide6_Addons', 'PySide6_Essentials', 'shiboken6',
            'pandas', 'numpy', 'matplotlib', 'openpyxl', 'Pillow', 'python-dateutil',
            'pytz', 'tzdata', 'contourpy', 'cycler', 'fonttools', 'kiwisolver',
            'packaging', 'pyparsing', 'six', 'et-xmlfile', 'certifi')


def generate(root: Path) -> Path:
    destination = root / 'assets' / 'licenses'
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('LGPL-3.0.txt', 'GPL-3.0.txt'):
        if not (destination / name).is_file():
            raise FileNotFoundError(f'Missing vendored Qt licence text: {name}')
    output = ['GameSense third-party software notices',
              'Generated from the build environment; retain these notices with the application.',
              '', 'Qt for Python / PySide6 and Shiboken are used under the available LGPLv3 terms.',
              'The complete LGPLv3 and accompanying GPLv3 texts are in this folder.',
              'Qt libraries remain dynamically linked and replaceable in the onedir bundle.',
              'Source/rebuild instructions: https://code.qt.io/cgit/pyside/pyside-setup.git/',
              'Qt source: https://code.qt.io/cgit/qt/qtbase.git/',
              'See QT_REDISTRIBUTION.md for replacement and source-version details.',
              'No restriction on reverse engineering for debugging modifications to LGPL-covered',
              'libraries is imposed by GameSense. Third-party rights remain with their owners.', '']
    for name in PACKAGES:
        try:
            distribution = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        package_name = distribution.metadata.get('Name', name)
        licence = distribution.metadata.get('License-Expression') or distribution.metadata.get('License') or 'See included licence text'
        output.extend(['=' * 76, f'{package_name} {distribution.version}',
                       f'Licence metadata: {licence}',
                       'Project URLs: ' + '; '.join(distribution.metadata.get_all('Project-URL') or []), ''])
        for item in distribution.files or []:
            if not re.search(r'(license|copying|notice)', item.name, re.I):
                continue
            source = Path(distribution.locate_file(item))
            if not source.is_file():
                continue
            try:
                content = source.read_text(encoding='utf-8')
            except (OSError, UnicodeError):
                continue
            output.extend([f'--- {package_name}: {item} ---', content, ''])
    for source in (Path(sys.base_prefix) / 'LICENSE.txt', Path(sys.base_prefix) / 'LICENSE'):
        if source.is_file():
            output.extend(['=' * 76, 'Python runtime ' + sys.version,
                           source.read_text(encoding='utf-8'), ''])
            break
    target = destination / 'THIRD_PARTY_NOTICES.txt'
    target.write_text('\n'.join(output), encoding='utf-8')
    qt_version = metadata.version('PySide6')
    (destination / 'QT_REDISTRIBUTION.md').write_text(f'''# Qt dynamic library notices

This build uses PySide6 {qt_version} and its corresponding Qt libraries. The
installed distribution metadata offers LGPL-3.0-only as a licence option.
GameSense uses that option for eligible included Qt modules. Included commercial
licence reference files describe an alternative option and do not assert that a
commercial Qt licence has been purchased.

The onedir Windows package keeps Qt DLLs, PySide6 extension modules and Shiboken
in the installed `_internal` tree. The macOS bundle keeps libraries/frameworks in
`Contents/Frameworks`. These components are dynamically linked, not statically
embedded into the GameSense executable. Users may inspect and replace compatible
libraries or rebuild them; preserve matching Qt/PySide6/Shiboken ABI versions and
the plugin layout. Work on a copy of the installed folder. Changing a macOS bundle
requires a new local signature before startup. GameSense imposes no prohibition
on reverse engineering necessary to debug modifications to these LGPL libraries.

Source for the corresponding release is available from the Qt Project:

- https://code.qt.io/cgit/pyside/pyside-setup.git/?h={qt_version}
- https://code.qt.io/cgit/qt/qtbase.git/?h=v{qt_version}
- https://download.qt.io/official_releases/QtForPython/
- https://download.qt.io/archive/qt/
- Build instructions: https://doc.qt.io/qtforpython-6/building_from_source/index.html

Keep the included LGPL-3.0.txt, GPL-3.0.txt and THIRD_PARTY_NOTICES.txt with copies
of the application. Release maintainers must retain the exact corresponding
source/version information and meet the applicable licence obligations when
redistributing binaries. This notice does not promise that arbitrary replacement
libraries are binary compatible or assign a licence to GameSense's own code.
''', encoding='utf-8')
    return target


if __name__ == '__main__':
    print(generate(Path(__file__).resolve().parents[1]))
