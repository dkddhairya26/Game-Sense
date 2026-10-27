# GameSense Desktop — Cross-Platform Prototype v2

A native desktop application for Windows and macOS, developed with PySide6, Pandas, Matplotlib and SQLite. The app has four distinct sport themes, custom vector field/court/oval/track art, rankings, comparisons, season filtering, charts, data import/export, and clearly labelled **fictional** offline demonstration data.

## Run from source (developer only)

Install Python 3.11–3.13, then from this folder:

```sh
python -m pip install -r requirements.txt
python app.py
```

On Windows, `py` may be used instead of `python`.

## Create a public desktop build

**Windows:** Run `build_windows.bat` on Windows. The output is `dist/GameSense/` containing `GameSense.exe` plus bundled dependencies. Distribute the *entire* folder, not just the executable. For a proper installer, use Inno Setup to wrap the folder and add shortcuts.

**macOS:** Run `bash build_macos.sh` on a Mac with Python installed. The output is `dist/GameSense.app`. macOS builds must be produced on macOS. For distribution outside your machine, Apple code signing and notarization are normally needed to avoid Gatekeeper warnings.

**Important:** This source ZIP is **not** a ready-made Windows or macOS installer. Builds must be created and tested on each target OS. The final installer and macOS app have not been built or verified here.

## Data

The included offline records are fictional demonstrations, not real player results. Use the import button to supply CSV or Excel datasets. The data pipeline cleans invalid/missing records, and the application stores imports in a local SQLite database. Data-source licensing, real historical coverage, online synchronization, public-release security and software signing remain future work.

## Public release checklist

1. Validate each real data provider's terms and coverage.
2. Build and smoke-test the Windows and macOS packages on those operating systems.
3. Bundle an installer and add an application icon, versioning, and uninstall support.
4. Sign and notarize packages where appropriate; publish SHA-256 checksums.
5. Test on a clean machine without Python or VS Code.

## Credits

The GUI is written using PySide6 (Qt for Python). The visualization uses Matplotlib. Data processing uses Pandas. See each dependency's license before redistribution.
