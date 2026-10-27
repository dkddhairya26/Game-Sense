"""Entry point for the GameSense Windows desktop application."""
import sys
from PySide6.QtWidgets import QApplication
from gamesense.window import GameSenseWindow

def main():
    app = QApplication(sys.argv)
    window = GameSenseWindow()
    window.show()
    return app.exec()

if __name__ == '__main__':
    raise SystemExit(main())
