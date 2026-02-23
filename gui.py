import sys
import threading
import queue
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QMessageBox, QFrame)
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPolygonF
from game_logic import Board
from network import GameServer, GameClient

GRID_SIZE = 30

class BoardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.game_gui = parent
        self.setMinimumSize(400, 400)

    def paintEvent(self, event):
        if not self.game_gui or not self.game_gui.started:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Fill background
        painter.fillRect(event.rect(), QColor("white"))

        # cell_size is min(width, height) / GRID_SIZE
        w = self.width()
        h = self.height()
        self.game_gui.cell_size = min(w, h) / GRID_SIZE
        
        self.game_gui.draw_board(painter)

    def mousePressEvent(self, event):
        if not self.game_gui or not self.game_gui.started:
            return
            
        x = int(event.position().x() // self.game_gui.cell_size)
        y = int(event.position().y() // self.game_gui.cell_size)
        
        if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE:
            self.game_gui.client.send({"type": "MOVE", "x": x, "y": y})

class GameGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3-Player Tic-Tac-Toe")
        self.resize(600, 600)
        
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                color: #000000;
            }
            QPushButton {
                background-color: #e0e0e0;
                border: 1px solid #999999;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #999999;
                padding: 4px;
                border-radius: 4px;
            }
        """)

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

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.setup_menu()
        
        # Start queue processing
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.process_queue)
        self.timer.start(100)

    def clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.clear_layout(item.layout())

    def setup_menu(self):
        self.clear_layout(self.main_layout)
        
        menu_frame = QFrame()
        menu_layout = QVBoxLayout(menu_frame)
        menu_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title = QLabel("3-Player Network Game")
        font = title.font()
        font.setPointSize(20)
        title.setFont(font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        menu_layout.addWidget(title)
        
        menu_layout.addSpacing(20)
        
        menu_layout.addWidget(QLabel("Player Name:"))
        self.name_entry = QLineEdit("Player")
        self.name_entry.setFixedWidth(200)
        menu_layout.addWidget(self.name_entry, alignment=Qt.AlignmentFlag.AlignCenter)
        
        menu_layout.addSpacing(10)
        
        menu_layout.addWidget(QLabel("Server IP:"))
        self.host_entry = QLineEdit("127.0.0.1")
        self.host_entry.setFixedWidth(200)
        menu_layout.addWidget(self.host_entry, alignment=Qt.AlignmentFlag.AlignCenter)
        
        menu_layout.addSpacing(20)
        
        self.host_btn = QPushButton("Host Game")
        self.host_btn.setFixedSize(200, 40)
        self.host_btn.clicked.connect(self.host_game)
        menu_layout.addWidget(self.host_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.join_btn = QPushButton("Join Game")
        self.join_btn.setFixedSize(200, 40)
        self.join_btn.clicked.connect(self.join_game)
        menu_layout.addWidget(self.join_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.main_layout.addWidget(menu_frame)

    def host_game(self):
        self.my_name = self.name_entry.text() or "Player"
        self.server = GameServer()
        threading.Thread(target=self.server.start, daemon=True).start()
        # Connect to localhost
        self.connect_to_game("127.0.0.1")

    def join_game(self):
        ip = self.host_entry.text()
        self.my_name = self.name_entry.text() or "Player"
        self.connect_to_game(ip)

    def connect_to_game(self, ip):
        if self.client.connect(ip):
            self.setup_board_ui()
            threading.Thread(target=self.receive_loop, daemon=True).start()
        else:
            QMessageBox.critical(self, "Error", "Could not connect to server")

    def setup_board_ui(self):
        self.clear_layout(self.main_layout)
        
        # Players Top Frame
        self.top_frame = QFrame()
        self.top_frame.setStyleSheet("background-color: #f0f0f0;")
        self.top_layout = QHBoxLayout(self.top_frame)
        self.main_layout.addWidget(self.top_frame)
        
        # Status Bar
        self.status_label = QLabel("Waiting for players...")
        font = self.status_label.font()
        font.setPointSize(12)
        self.status_label.setFont(font)
        self.main_layout.addWidget(self.status_label)

        # Canvas Frame 
        self.canvas = BoardWidget(self)
        self.main_layout.addWidget(self.canvas, stretch=1)

    def update_top_frame(self, next_turn):
        self.clear_layout(self.top_layout)
            
        colors = ["black", "red", "blue", "green"]
        for player_id in range(1, 4):
            color = colors[player_id]
            bg_color = "lightyellow" if player_id == next_turn else "#f0f0f0"
            font_weight = "bold" if player_id == next_turn else "normal"
            name = self.player_names.get(str(player_id), f"Player {player_id}")
            
            lbl = QLabel(f"P{player_id}: {name}")
            lbl.setStyleSheet(f"""
                QLabel {{
                    color: {color};
                    background-color: {bg_color};
                    font-weight: {font_weight};
                    border: 2px groove gray;
                    padding: 5px 10px;
                }}
            """)
            self.top_layout.addWidget(lbl)

        self.top_layout.addStretch()

        if self.my_id == 1 and self.started:
            restart_btn = QPushButton("Restart")
            restart_btn.clicked.connect(self.send_restart)
            self.top_layout.addWidget(restart_btn)

    def send_restart(self):
        self.client.send({"type": "RESTART"})

    def draw_board(self, painter):
        self.draw_grid(painter)
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                if self.board.grid[y][x] != 0:
                    self.draw_symbol(painter, x, y, self.board.grid[y][x])
        
        if self.last_move:
            self.draw_last_move_highlight(painter)

    def draw_grid(self, painter):
        painter.setPen(QPen(QColor("lightgray"), 1))
        
        for i in range(GRID_SIZE + 1):
            # Horizontal lines
            painter.drawLine(
                int(0), int(i * self.cell_size),
                int(GRID_SIZE * self.cell_size), int(i * self.cell_size)
            )
            # Vertical lines
            painter.drawLine(
                int(i * self.cell_size), int(0),
                int(i * self.cell_size), int(GRID_SIZE * self.cell_size)
            )

    def draw_last_move_highlight(self, painter):
        x, y = self.last_move
        cx = x * self.cell_size + self.cell_size / 2
        cy = y * self.cell_size + self.cell_size / 2
        r = self.cell_size / 2.2
        
        painter.setPen(QPen(QColor("#ffdb58"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QtCore.QRectF(cx - r, cy - r, r * 2, r * 2))

    def draw_symbol(self, painter, x, y, player):
        cx = x * self.cell_size + self.cell_size / 2
        cy = y * self.cell_size + self.cell_size / 2
        r = self.cell_size / 3
        
        if player == 1: # Cross (X) - Red
            painter.setPen(QPen(QColor("red"), 2))
            painter.drawLine(QtCore.QPointF(cx - r, cy - r), QtCore.QPointF(cx + r, cy + r))
            painter.drawLine(QtCore.QPointF(cx + r, cy - r), QtCore.QPointF(cx - r, cy + r))
        elif player == 2: # Circle (O) - Blue
            painter.setPen(QPen(QColor("blue"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QtCore.QPointF(cx, cy), r, r)
        elif player == 3: # Triangle (Δ) - Green
            painter.setPen(QPen(QColor("green"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            polygon = QPolygonF([
                QtCore.QPointF(cx, cy - r),
                QtCore.QPointF(cx - r, cy + r),
                QtCore.QPointF(cx + r, cy + r)
            ])
            painter.drawPolygon(polygon)

    def receive_loop(self):
        while True:
            messages = self.client.receive_messages()
            if messages is None:
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

    def handle_message(self, msg):
        msg_type = msg.get("type")
        
        if msg_type == "INIT":
            self.my_id = msg["player_id"]
            self.client.send({"type": "SET_NAME", "name": self.my_name})
            self.setWindowTitle(f"3-Player Tic-Tac-Toe - Player {self.my_id} ({self.my_name})")
            
        elif msg_type == "START":
            self.started = True
            self.player_names = msg.get("names", {})
            self.status_label.setText(msg["message"])
            self.update_top_frame(msg.get("current_turn", 1))
            self.canvas.update()
            
        elif msg_type == "UPDATE":
            x, y, player = msg["x"], msg["y"], msg["player"]
            self.board.grid[y][x] = player
            self.last_move = (x, y)
            
            self.canvas.update()
            
            next_turn = msg["next_turn"]
            status = f"Player {next_turn}'s Turn"
            
            if self.board.check_win(x, y, player):
                status = f"{self.player_names.get(str(player), f'Player {player}')} WINS!"
                self.status_label.setText(status)
                self.update_top_frame(next_turn)
                QMessageBox.information(self, "Game Over", f"{self.player_names.get(str(player), f'Player {player}')} Wins!")
                self.started = False
            else:
                self.status_label.setText(status)
                self.update_top_frame(next_turn)
                
        elif msg_type == "RESTART_GAME":
            self.started = True
            self.board = Board(size=GRID_SIZE)
            self.last_move = None
            self.status_label.setText(msg["message"])
            self.update_top_frame(msg.get("current_turn", 1))
            self.canvas.update()
            
        elif msg_type == "ERROR":
            QMessageBox.warning(self, "Warning", msg["message"])

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = GameGUI()
    window.show()
    sys.exit(app.exec())
