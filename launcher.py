import sys
import subprocess
import time

def run_client(name, x, y, role):
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    from gui import GameGUI

    app = QApplication(sys.argv)
    window = GameGUI()
    window.setGeometry(int(x), int(y), 500, 600)
    window.name_entry.setText(name)

    delay = 500 if role == "host" else 1500
    action = window.host_game if role == "host" else window.join_game
    QTimer.singleShot(delay, action)

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_client(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print("Launching 3 Tic-Tac-Toe clients...")
        python_exe = sys.executable
        p1 = subprocess.Popen([python_exe, sys.argv[0], "Alice (Host)", "50", "50", "host"])
        time.sleep(1)
        p2 = subprocess.Popen([python_exe, sys.argv[0], "Bob", "560", "50", "join"])
        p3 = subprocess.Popen([python_exe, sys.argv[0], "Charlie", "1070", "50", "join"])
        try:
            p1.wait()
            p2.wait()
            p3.wait()
        except KeyboardInterrupt:
            print("Terminating clients...")
            p1.terminate()
            p2.terminate()
            p3.terminate()
