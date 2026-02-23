import sys
import subprocess
import time

def run_client(name, x, y, role):
    import tkinter as tk
    from gui import GameGUI
    
    root = tk.Tk()
    root.geometry(f"500x600+{x}+{y}")
    app = GameGUI(root)
    
    app.name_entry.delete(0, tk.END)
    app.name_entry.insert(0, name)
    
    if role == "host":
        root.after(500, app.host_game)
    else:
        root.after(1500, app.join_game)
        
    root.mainloop()

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
