"""GameSense native desktop entry point and reproducible packaged startup check."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import traceback


def main():
    parser = argparse.ArgumentParser(description='GameSense sports intelligence desktop')
    parser.add_argument('--smoke-test', action='store_true', help='Render major screens offline, write a report, and exit')
    parser.add_argument('--screenshots', type=Path, help='Save rendered native window screenshots during the smoke test')
    args = parser.parse_args()
    if args.smoke_test:
        os.environ['GAMESENSE_OFFLINE'] = '1'
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication
    from gamesense.archive import data_directory
    app = QApplication([sys.argv[0]])
    app.setApplicationName('GameSense')
    app.setApplicationVersion('0.8.0')
    app.setOrganizationName('GameSense')
    # Qt's offscreen platform does not enumerate Windows fonts. Load the system
    # face explicitly for reproducible screenshot QA; no font is redistributed.
    if not QFontDatabase.families() and sys.platform == 'win32':
        fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
        for name in ('segoeui.ttf', 'segoeuib.ttf', 'arial.ttf'):
            if (fonts / name).exists():
                QFontDatabase.addApplicationFont(str(fonts / name))
    report_path = data_directory() / 'smoke-results.json'
    unhandled = []
    def report_error(kind, value, tb):
        detail = ''.join(traceback.format_exception(kind, value, tb))
        unhandled.append(detail)
        error_path = data_directory() / 'error.log'
        error_path.parent.mkdir(parents=True, exist_ok=True)
        with error_path.open('a', encoding='utf-8') as stream:
            stream.write(detail + '\n')
        if not args.smoke_test:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(None, 'GameSense encountered a problem', str(value) + '\n\nDetails were saved to ' + str(error_path))
    sys.excepthook = report_error
    try:
        from gamesense.window import GameSenseWindow
        window = GameSenseWindow()
        window.show()
    except Exception:
        if args.smoke_test:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps({'success': False, 'error': traceback.format_exc()}, indent=2), encoding='utf-8')
            return 1
        raise
    if args.smoke_test:
        pages = [('home','Soccer','overview')]
        for sport in ('Soccer','NBA','AFL','F1'):
            pages += [('dashboard',sport,sport.lower()+'-dashboard'),('profiles',sport,sport.lower()+'-profile')]
        pages += [('profiles','Soccer','soccer-shot-map'),('profiles','F1','f1-grid-comparison'),('profiles','F1','f1-pit-stops')]
        pages += [(route,'F1',route) for route in ('teams','compare','leaders','explorer','downloads','settings','about')]
        pages += [('dashboard','NBA','nba-compact')]
        results = []
        def step():
            if window.initializing:
                QTimer.singleShot(100, step)
                return
            if not pages:
                bundled_root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
                cc0_seed = bundled_root / 'data' / 'seed_soccer_cc0.jsonl.gz'
                if cc0_seed.exists():
                    real_club_rows = window.archive.count('Soccer',provider='openfootball')
                    if real_club_rows < 7500:
                        unhandled.append(
                            f'Historical football starter missing from local archive: '
                            f'expected >=7,500 real club rows, found {real_club_rows:,}.')
                search_checks = []
                examples = {'Soccer':('statsbomb:5503','Lionel Messi'), 'NBA':('nba:2544','LeBron James'), 'AFL':('squiggle:team:4','Collingwood'), 'F1':('f1db:lewis-hamilton','Lewis Hamilton')}
                for sport, (identity, query) in examples.items():
                    if window.archive.count(sport, competitor_id=identity):
                        matches = window.archive.search(sport, query)
                        search_checks.append({'query':query,'success':identity in matches['competitor_id'].tolist()})
                report = {'success': all(r['success'] for r in results + search_checks) and not unhandled, 'search_checks':search_checks, 'unhandled_errors': unhandled, 'native_qt': True, 'offline': True, 'screens': results,
                          'coverage': {s:window.archive.stats(s) for s in ('Soccer','NBA','AFL','F1')}}
                report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
                app.exit(0 if report['success'] else 1)
                return
            route, sport, name = pages.pop(0)
            try:
                window.resize(1040, 760) if name.endswith('compact') else window.resize(1440, 960)
                window.sport.setCurrentText(sport)
                # Exercise an actually recognisable identity when present.
                if route == 'profiles':
                    target = {'F1':'Lewis Hamilton','NBA':'LeBron James','Soccer':'Lionel Messi','AFL':'Collingwood'}[sport]
                    index = window.athlete.findText(target, __import__('PySide6.QtCore', fromlist=['Qt']).Qt.MatchFlag.MatchContains)
                    if sport == 'Soccer' and index < 0:
                        index = window.athlete.findData('statsbomb:5503')
                    if index >= 0:
                        window.athlete.setCurrentIndex(index)
                window.navigate(route)
                if route == 'profiles':
                    mode = {'soccer-shot-map':'Shot map', 'f1-grid-comparison':'Grid vs finish', 'f1-pit-stops':'Pit-stop timeline'}.get(name, 'Season trend')
                    window.profile_mode.setCurrentText(mode)
                app.processEvents()
                if args.screenshots:
                    args.screenshots.mkdir(parents=True, exist_ok=True)
                    path = args.screenshots / (name + '.png')
                    if not window.grab().save(str(path)):
                        raise RuntimeError('Failed to save screenshot ' + str(path))
                results.append({'screen':name, 'success':True})
            except Exception:
                results.append({'screen':name, 'success':False, 'error':traceback.format_exc()})
            QTimer.singleShot(60, step)
        QTimer.singleShot(100, step)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
