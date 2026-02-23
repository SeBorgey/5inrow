import tkinter as tk
from tkinter import messagebox
import threading
import queue
from game_logic import Board
from network import GameServer, GameClient

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
        self.my_name = ""
        self.player_names = {}
        self.msg_queue = queue.Queue()
        self.server = None
        self.cell_size = 20
        self.last_move = None

        self.setup_menu()
        
        # Start queue processing
        self.root.after(100, self.process_queue)

    def setup_menu(self):
        self.clear_frame()
        
        frame = tk.Frame(self.root)
        frame.pack(expand=True)

        tk.Label(frame, text="3-Player Network Game", font=("Arial", 20)).pack(pady=20)
        
        tk.Label(frame, text="Player Name:").pack(pady=2)
        self.name_entry = tk.Entry(frame, width=20)
        self.name_entry.insert(0, "Player")
        self.name_entry.pack(pady=5)
        
        tk.Label(frame, text="Server IP:").pack(pady=2)
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
        self.my_name = self.name_entry.get() or "Player"
        self.connect_to_game(ip)

    def connect_to_game(self, ip):
        if self.client.connect(ip):
            self.setup_board_ui()
            threading.Thread(target=self.receive_loop, daemon=True).start()
        else:
            messagebox.showerror("Error", "Could not connect to server")

    def setup_board_ui(self):
        self.clear_frame()
        
        # Players Top Frame
        self.top_frame = tk.Frame(self.root, bg="#f0f0f0")
        self.top_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        self.player_labels = {}
        
        # Status Bar
        self.status_label = tk.Label(self.root, text="Waiting for players...", font=("Arial", 12))
        self.status_label.pack(side=tk.TOP, fill=tk.X)

        # Canvas Frame 
        frame = tk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(frame, bg="white")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas.bind("<Configure>", self.on_canvas_resize)
        self.canvas.bind("<Button-1>", self.on_click)

    def update_top_frame(self, next_turn):
        for widget in self.top_frame.winfo_children():
            widget.destroy()
            
        for player_id in range(1, 4):
            # Check player specific info
            color = ["black", "red", "blue", "green"][player_id]
            bg_color = "lightyellow" if player_id == next_turn else "#f0f0f0"
            font_weight = "bold" if player_id == next_turn else "normal"
            name = self.player_names.get(str(player_id), f"Player {player_id}")
            
            lbl = tk.Label(self.top_frame, text=f"P{player_id}: {name}", fg=color, bg=bg_color, font=("Arial", 10, font_weight), borderwidth=2, relief="groove", padx=10, pady=5)
            lbl.pack(side=tk.LEFT, padx=5, expand=True)

        # Adds a Restart Button for host if game has started
        if self.my_id == 1 and self.started:
            tk.Button(self.top_frame, text="Restart", command=self.send_restart).pack(side=tk.RIGHT, padx=5)

    def send_restart(self):
        self.client.send({"type": "RESTART"})

    def on_canvas_resize(self, event):
        # Dynamically resize cell size to fit window
        self.cell_size = min(event.width, event.height) / GRID_SIZE
        self.redraw_board()

    def redraw_board(self):
        self.canvas.delete("all")
        self.draw_grid()
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                if self.board.grid[y][x] != 0:
                    self.draw_symbol(x, y, self.board.grid[y][x])
        
        # Draw last move highlight on top of pieces
        if self.last_move:
            self.draw_last_move_highlight()

    def draw_grid(self):
        for i in range(GRID_SIZE + 1):
            self.canvas.create_line(0, i * self.cell_size, GRID_SIZE * self.cell_size, i * self.cell_size, fill="lightgray")
            self.canvas.create_line(i * self.cell_size, 0, i * self.cell_size, GRID_SIZE * self.cell_size, fill="lightgray")

    def on_click(self, event):
        if not self.started:
            return

        # Get canvas coordinates proportional to cell_size
        x = int(self.canvas.canvasx(event.x) // self.cell_size)
        y = int(self.canvas.canvasy(event.y) // self.cell_size)

        # Send move to server
        self.client.send({"type": "MOVE", "x": x, "y": y})

    def draw_last_move_highlight(self):
        x, y = self.last_move
        cx, cy = x * self.cell_size + self.cell_size/2, y * self.cell_size + self.cell_size/2
        r = self.cell_size / 2.2
        self.canvas.create_rectangle(cx-r, cy-r, cx+r, cy+r, width=2, outline="#ffdb58") # Highlight box

    def draw_symbol(self, x, y, player):
        cx, cy = x * self.cell_size + self.cell_size/2, y * self.cell_size + self.cell_size/2
        r = self.cell_size / 3
        
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
            self.client.send({"type": "SET_NAME", "name": self.my_name})
            self.root.title(f"3-Player Tic-Tac-Toe - Player {self.my_id} ({self.my_name})")
            
        elif msg_type == "START":
            self.started = True
            self.player_names = msg.get("names", {})
            self.status_label.config(text=msg["message"])
            self.update_top_frame(msg.get("current_turn", 1))
            
        elif msg_type == "UPDATE":
            x, y, player = msg["x"], msg["y"], msg["player"]
            self.board.grid[y][x] = player
            self.last_move = (x, y)
            
            self.redraw_board()
            
            next_turn = msg["next_turn"]
            status = f"Player {next_turn}'s Turn"
            
            if self.board.check_win(x, y, player):
                status = f"{self.player_names.get(str(player), f'Player {player}')} WINS!"
                self.status_label.config(text=status)
                self.update_top_frame(next_turn)
                messagebox.showinfo("Game Over", f"{self.player_names.get(str(player), f'Player {player}')} Wins!")
                self.started = False
            else:
                self.status_label.config(text=status)
                self.update_top_frame(next_turn)
                
        elif msg_type == "RESTART_GAME":
            self.started = True
            self.board = Board(size=GRID_SIZE)
            self.last_move = None
            self.status_label.config(text=msg["message"])
            self.update_top_frame(msg.get("current_turn", 1))
            self.redraw_board()
            
        elif msg_type == "ERROR":
            messagebox.showwarning("Warning", msg["message"])
