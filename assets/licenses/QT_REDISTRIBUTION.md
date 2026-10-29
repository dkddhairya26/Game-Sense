# Qt dynamic library notices

This build uses PySide6 6.12.0 and its corresponding Qt libraries. The
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

- https://code.qt.io/cgit/pyside/pyside-setup.git/?h=6.12.0
- https://code.qt.io/cgit/qt/qtbase.git/?h=v6.12.0
- https://download.qt.io/official_releases/QtForPython/
- https://download.qt.io/archive/qt/
- Build instructions: https://doc.qt.io/qtforpython-6/building_from_source/index.html

Keep the included LGPL-3.0.txt, GPL-3.0.txt and THIRD_PARTY_NOTICES.txt with copies
of the application. Release maintainers must retain the exact corresponding
source/version information and meet the applicable licence obligations when
redistributing binaries. This notice does not promise that arbitrary replacement
libraries are binary compatible or assign a licence to GameSense's own code.
