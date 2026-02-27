import sys
import threading
import queue
import subprocess
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import Qt, QTimer
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
        painter.fillRect(event.rect(), QColor("white"))
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
            QWidget { background-color: #ffffff; color: #000000; }
            QPushButton { background-color: #e0e0e0; border: 1px solid #999999; padding: 6px 12px; border-radius: 4px; }
            QPushButton:hover { background-color: #d0d0d0; }
            QLineEdit { background-color: #ffffff; border: 1px solid #999999; padding: 4px; border-radius: 4px; }
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
        self.last_moves = {}
        self.absolute_last_move_player = None
        self.time_limit = 15
        self.time_remaining = 15
        self.sound_enabled = True
        self.turn_timer = QTimer(self)
        self.turn_timer.timeout.connect(self.tick_timer)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.setup_menu()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.process_queue)
        self.timer.start(100)

    def tick_timer(self):
        if self.started and self.time_remaining > 0:
            self.time_remaining -= 1
            self.timer_label.setText(f"Time: {self.time_remaining}s")

    def toggle_sound(self):
        self.sound_enabled = not self.sound_enabled
        self.sound_btn.setText("Sound: ON" if self.sound_enabled else "Sound: OFF")

    def play_turn_sound(self, next_turn):
        if self.sound_enabled and next_turn == self.my_id:
            QApplication.beep()

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
        menu_layout.addSpacing(10)
        menu_layout.addWidget(QLabel("Turn Time Limit (s) [Host only]:"))
        self.time_entry = QLineEdit("15")
        self.time_entry.setFixedWidth(200)
        menu_layout.addWidget(self.time_entry, alignment=Qt.AlignmentFlag.AlignCenter)
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
        try:
            time_limit = int(self.time_entry.text())
            if time_limit <= 0:
                time_limit = 15
        except ValueError:
            time_limit = 15
        self.server = GameServer(time_limit=time_limit)
        threading.Thread(target=self.server.start, daemon=True).start()
        self.connect_to_game("127.0.0.1")

    def join_game(self):
        ip = self.host_entry.text()
        self.my_name = self.name_entry.text() or "Player"
        self.connect_to_game(ip)

    def connect_to_game(self, ip):
        if self.client.connect(ip):
            self.connected_ip = ip
            self.setup_lobby_ui()
            threading.Thread(target=self.receive_loop, daemon=True).start()
        else:
            QMessageBox.critical(self, "Error", "Could not connect to server")

    def setup_lobby_ui(self):
        self.clear_layout(self.main_layout)
        self.lobby_frame = QFrame()
        self.lobby_layout = QVBoxLayout(self.lobby_frame)
        self.lobby_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        title = QLabel("Game Lobby")
        font = title.font()
        font.setPointSize(20)
        title.setFont(font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lobby_layout.addWidget(title)
        self.lobby_layout.addSpacing(20)
        self.players_list_label = QLabel("Waiting for players...")
        font.setPointSize(14)
        self.players_list_label.setFont(font)
        self.players_list_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lobby_layout.addWidget(self.players_list_label)
        self.lobby_layout.addStretch()
        self.host_controls = QFrame()
        host_layout = QHBoxLayout(self.host_controls)
        host_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.add_bot_btn = QPushButton("Add Bot (RL)")
        self.add_bot_btn.setFixedSize(150, 40)
        self.add_bot_btn.clicked.connect(self.add_bot_to_lobby)
        host_layout.addWidget(self.add_bot_btn)
        self.start_game_btn = QPushButton("Start Game")
        self.start_game_btn.setFixedSize(150, 40)
        self.start_game_btn.clicked.connect(self.send_start_game)
        self.start_game_btn.setEnabled(False)
        host_layout.addWidget(self.start_game_btn)
        self.lobby_layout.addWidget(self.host_controls)
        self.host_controls.setVisible(False)
        self.main_layout.addWidget(self.lobby_frame)

    def add_bot_to_lobby(self):
        subprocess.Popen([sys.executable, "bot_client.py", getattr(self, "connected_ip", "127.0.0.1")])

    def send_start_game(self):
        self.client.send({"type": "START_GAME"})

    def setup_board_ui(self):
        self.clear_layout(self.main_layout)
        self.top_frame = QFrame()
        self.top_frame.setStyleSheet("background-color: #f0f0f0;")
        self.top_layout = QHBoxLayout(self.top_frame)
        self.main_layout.addWidget(self.top_frame)
        self.status_bar_frame = QFrame()
        self.status_bar_layout = QHBoxLayout(self.status_bar_frame)
        self.main_layout.addWidget(self.status_bar_frame)
        self.status_label = QLabel("Waiting for players...")
        font = self.status_label.font()
        font.setPointSize(12)
        self.status_label.setFont(font)
        self.status_bar_layout.addWidget(self.status_label)
        self.status_bar_layout.addStretch()
        self.timer_label = QLabel("Time: --")
        self.timer_label.setFont(font)
        self.timer_label.setStyleSheet("color: red; font-weight: bold;")
        self.status_bar_layout.addWidget(self.timer_label)
        self.sound_btn = QPushButton("Sound: ON" if self.sound_enabled else "Sound: OFF")
        self.sound_btn.clicked.connect(self.toggle_sound)
        self.status_bar_layout.addWidget(self.sound_btn)
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
        self.draw_last_move_highlight(painter)
        self.draw_grid(painter)
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                if self.board.grid[y][x] != 0:
                    self.draw_symbol(painter, x, y, self.board.grid[y][x])

    def draw_grid(self, painter):
        painter.setPen(QPen(QColor("lightgray"), 1))
        for i in range(GRID_SIZE + 1):
            painter.drawLine(0, int(i * self.cell_size), int(GRID_SIZE * self.cell_size), int(i * self.cell_size))
            painter.drawLine(int(i * self.cell_size), 0, int(i * self.cell_size), int(GRID_SIZE * self.cell_size))

    def draw_last_move_highlight(self, painter):
        for player, move in self.last_moves.items():
            if not move:
                continue
            x, y = move
            painter.setPen(Qt.PenStyle.NoPen)
            if player == self.absolute_last_move_player:
                painter.setBrush(QBrush(QColor("yellow")))
            else:
                painter.setBrush(QBrush(QColor("#fcf6c7")))
            painter.drawRect(QtCore.QRectF(x * self.cell_size, y * self.cell_size, self.cell_size, self.cell_size))

    def draw_symbol(self, painter, x, y, player):
        cx = x * self.cell_size + self.cell_size / 2
        cy = y * self.cell_size + self.cell_size / 2
        r = self.cell_size / 3
        if player == 1:
            painter.setPen(QPen(QColor("red"), 2))
            painter.drawLine(QtCore.QPointF(cx - r, cy - r), QtCore.QPointF(cx + r, cy + r))
            painter.drawLine(QtCore.QPointF(cx + r, cy - r), QtCore.QPointF(cx - r, cy + r))
        elif player == 2:
            painter.setPen(QPen(QColor("blue"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QtCore.QPointF(cx, cy), r, r)
        elif player == 3:
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
            if self.my_id == 1 and hasattr(self, 'host_controls'):
                self.host_controls.setVisible(True)

        elif msg_type == "LOBBY_UPDATE":
            players = msg.get("players", [])
            text = "Connected Players:\n\n"
            for p in players:
                text += f"Player {p['id']}: {p['name']} (IP: {p['ip']})\n"
            if hasattr(self, 'players_list_label'):
                self.players_list_label.setText(text)
            if hasattr(self, 'add_bot_btn'):
                self.add_bot_btn.setEnabled(len(players) < 3)
                self.start_game_btn.setEnabled(len(players) == 3)

        elif msg_type == "START":
            self.setup_board_ui()
            self.started = True
            self.player_names = msg.get("names", {})
            self.status_label.setText(msg["message"])
            self.time_limit = msg.get("time_limit", 15)
            self.time_remaining = self.time_limit
            self.timer_label.setText(f"Time: {self.time_remaining}s")
            self.turn_timer.start(1000)
            self.update_top_frame(msg.get("current_turn", 1))
            self.canvas.update()
            self.play_turn_sound(msg.get("current_turn", 1))

        elif msg_type == "UPDATE":
            x, y, player = msg["x"], msg["y"], msg["player"]
            self.board.grid[y][x] = player
            self.last_moves[player] = (x, y)
            self.absolute_last_move_player = player
            self.time_limit = msg.get("time_limit", 15)
            self.time_remaining = self.time_limit
            self.timer_label.setText(f"Time: {self.time_remaining}s")
            self.canvas.update()
            next_turn = msg["next_turn"]
            if self.board.check_win(x, y, player):
                winner_name = self.player_names.get(str(player), f'Player {player}')
                self.status_label.setText(f"{winner_name} WINS!")
                self.update_top_frame(next_turn)
                self.started = False
                self.turn_timer.stop()
                if self.my_id == 1:
                    self.client.send({"type": "GAME_OVER"})
                QMessageBox.information(self, "Game Over", f"{winner_name} Wins!")
            else:
                self.status_label.setText(f"Player {next_turn}'s Turn")
                self.update_top_frame(next_turn)
                self.play_turn_sound(next_turn)

        elif msg_type == "SKIP_TURN":
            next_turn = msg["next_turn"]
            self.status_label.setText(msg["message"])
            self.update_top_frame(next_turn)
            self.time_remaining = self.time_limit
            self.timer_label.setText(f"Time: {self.time_remaining}s")
            self.play_turn_sound(next_turn)

        elif msg_type == "RESTART_GAME":
            self.started = True
            self.board = Board(size=GRID_SIZE)
            self.last_moves = {}
            self.absolute_last_move_player = None
            self.status_label.setText(msg["message"])
            self.time_limit = msg.get("time_limit", 15)
            self.time_remaining = self.time_limit
            self.timer_label.setText(f"Time: {self.time_remaining}s")
            self.turn_timer.start(1000)
            self.update_top_frame(msg.get("current_turn", 1))
            self.canvas.update()
            self.play_turn_sound(msg.get("current_turn", 1))

        elif msg_type == "ERROR":
            QMessageBox.warning(self, "Warning", msg["message"])

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = GameGUI()
    window.show()
    sys.exit(app.exec())
