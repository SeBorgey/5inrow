import sys
from PyQt6.QtWidgets import QApplication
from gui import GameGUI

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GameGUI()
    window.show()
    sys.exit(app.exec())
