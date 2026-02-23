import tkinter as tk
from tkinter import messagebox
import threading
import queue
from game_logic import Board
from network import GameServer, GameClient

CELL_SIZE = 20
GRID_SIZE = 30

class GameGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("3-Player Tic-Tac-Toe")
        self.root.geometry("600x600")

        self.board = Board(size=GRID_SIZE)
        self.client = GameClient()
        self.started = False
        self.my_id = None
        self.msg_queue = queue.Queue()
        self.server = None

        self.setup_menu()
        
        # Start queue processing
        self.root.after(100, self.process_queue)

    def setup_menu(self):
        self.clear_frame()
        
        frame = tk.Frame(self.root)
        frame.pack(expand=True)

        tk.Label(frame, text="3-Player Network Game", font=("Arial", 20)).pack(pady=20)
        
        self.host_entry = tk.Entry(frame, width=20)
        self.host_entry.insert(0, "127.0.0.1")
        self.host_entry.pack(pady=5)
        
        tk.Button(frame, text="Host Game", command=self.host_game, width=20, height=2).pack(pady=5)
        tk.Button(frame, text="Join Game", command=self.join_game, width=20, height=2).pack(pady=5)

    def clear_frame(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def host_game(self):
        self.server = GameServer()
        threading.Thread(target=self.server.start, daemon=True).start()
        # Connect to localhost
        self.connect_to_game("127.0.0.1")

    def join_game(self):
        ip = self.host_entry.get()
        self.connect_to_game(ip)

    def connect_to_game(self, ip):
        if self.client.connect(ip):
            self.setup_board_ui()
            threading.Thread(target=self.receive_loop, daemon=True).start()
        else:
            messagebox.showerror("Error", "Could not connect to server")

    def setup_board_ui(self):
        self.clear_frame()
        
        # Status Bar
        self.status_label = tk.Label(self.root, text="Waiting for players...", font=("Arial", 12))
        self.status_label.pack(side=tk.TOP, fill=tk.X)

        # Canvas Frame with Scrollbars
        frame = tk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(frame, bg="white", scrollregion=(0, 0, GRID_SIZE*CELL_SIZE, GRID_SIZE*CELL_SIZE))
        
        h_scroll = tk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        v_scroll = tk.Scrollbar(frame, orient=tk.VERTICAL, command=self.canvas.yview)
        
        self.canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.draw_grid()
        self.canvas.bind("<Button-1>", self.on_click)

    def draw_grid(self):
        for i in range(GRID_SIZE + 1):
            self.canvas.create_line(0, i * CELL_SIZE, GRID_SIZE * CELL_SIZE, i * CELL_SIZE, fill="lightgray")
            self.canvas.create_line(i * CELL_SIZE, 0, i * CELL_SIZE, GRID_SIZE * CELL_SIZE, fill="lightgray")

    def on_click(self, event):
        if not self.started:
            return

        # Get canvas coordinates accounting for scroll
        x = int(self.canvas.canvasx(event.x) // CELL_SIZE)
        y = int(self.canvas.canvasy(event.y) // CELL_SIZE)

        # Send move to server
        self.client.send({"type": "MOVE", "x": x, "y": y})

    def draw_symbol(self, x, y, player):
        cx, cy = x * CELL_SIZE + CELL_SIZE/2, y * CELL_SIZE + CELL_SIZE/2
        r = CELL_SIZE / 3
        
        if player == 1: # Cross (X) - Red
            self.canvas.create_line(cx-r, cy-r, cx+r, cy+r, width=2, fill="red")
            self.canvas.create_line(cx+r, cy-r, cx-r, cy+r, width=2, fill="red")
        elif player == 2: # Circle (O) - Blue
            self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, width=2, outline="blue")
        elif player == 3: # Triangle (Δ) - Green
            self.canvas.create_polygon(cx, cy-r, cx-r, cy+r, cx+r, cy+r, fill="", outline="green", width=2)

    def receive_loop(self):
        while True:
            messages = self.client.receive_messages()
            if messages is None:
                # Connection lost
                break
            
            for msg in messages:
                self.msg_queue.put(msg)

    def process_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                self.handle_message(msg)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

    def handle_message(self, msg):
        msg_type = msg.get("type")
        
        if msg_type == "INIT":
            self.my_id = msg["player_id"]
            self.root.title(f"3-Player Tic-Tac-Toe - Player {self.my_id}")
            
        elif msg_type == "START":
            self.started = True
            self.status_label.config(text=msg["message"])
            
        elif msg_type == "UPDATE":
            x, y, player = msg["x"], msg["y"], msg["player"]
            self.board.grid[y][x] = player
            self.draw_symbol(x, y, player)
            
            next_turn = msg["next_turn"]
            status = f"Player {next_turn}'s Turn"
            if self.board.check_win(x, y, player):
                status = f"Player {player} WINS!"
                messagebox.showinfo("Game Over", f"Player {player} Wins!")
                self.started = False
                
            self.status_label.config(text=status)
            
        elif msg_type == "ERROR":
            messagebox.showwarning("Warning", msg["message"])
