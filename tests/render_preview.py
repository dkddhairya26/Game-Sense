"""Create genuine Qt screenshots and verify all four sport views without a display."""
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from gamesense.window import GameSenseWindow

app = QApplication([])
window = GameSenseWindow()
window.resize(1470, 920)
window.show()
folder = Path("previews")
folder.mkdir(exist_ok=True)
for sport in ("Soccer", "NBA", "AFL", "F1"):
    window.change_sport(sport)
    app.processEvents()
    assert window.kpi_widgets[0].text() != "—", sport
    assert window.metric.count() > 0, sport
    target = folder / ("GameSense-" + sport.replace(" ", "-") + ".png")
    assert window.grab().save(str(target)), target
    print(sport, "OK", target)
window.close()
