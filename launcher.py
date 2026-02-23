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
    
    if role == "host":
        QTimer.singleShot(500, window.host_game)
    else:
        QTimer.singleShot(1500, window.join_game)
        
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Running as a single client
        name = sys.argv[1]
        x = sys.argv[2]
        y = sys.argv[3]
        role = sys.argv[4]
        run_client(name, x, y, role)
    else:
        # Running as the launcher (starts 3 separate processes)
        print("Launching 3 Tic-Tac-Toe clients...")
        python_exe = sys.executable
        
        # We start the host first
        p1 = subprocess.Popen([python_exe, sys.argv[0], "Alice (Host)", "50", "50", "host"])
        
        # Wait a moment for server to start
        time.sleep(1)
        
        p2 = subprocess.Popen([python_exe, sys.argv[0], "Bob", "560", "50", "join"])
        p3 = subprocess.Popen([python_exe, sys.argv[0], "Charlie", "1070", "50", "join"])
        
        # Wait for them to finish
        try:
            p1.wait()
            p2.wait()
            p3.wait()
        except KeyboardInterrupt:
            print("Terminating clients...")
            p1.terminate()
            p2.terminate()
            p3.terminate()
