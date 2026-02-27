import sys
import os
import json
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPolygonF
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QComboBox, QPushButton, QMessageBox)

GRID_SIZE = 30

class ReplayBoardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.viewer = parent
        self.setMinimumSize(400, 400)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(event.rect(), QColor("white"))
        w = self.width()
        h = self.height()
        self.viewer.cell_size = min(w, h) / GRID_SIZE
        self.viewer.draw_board(painter)

class ReplayViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Система просмотра реплеев")
        self.resize(700, 700)
        self.cell_size = 20
        self.current_epoch_data = None
        self.current_game_index = -1
        self.current_game_moves = []
        self.current_move_index = 0
        self.auto_play_timer = QTimer(self)
        self.auto_play_timer.timeout.connect(self.next_move)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.load_epochs)
        self.refresh_timer.start(5000)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.setup_ui()
        self.load_epochs()

    def setup_ui(self):
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Эпоха:"))
        self.epoch_cb = QComboBox()
        self.epoch_cb.currentIndexChanged.connect(self.on_epoch_selected)
        controls_layout.addWidget(self.epoch_cb)
        controls_layout.addWidget(QLabel("Партия:"))
        self.game_cb = QComboBox()
        self.game_cb.currentIndexChanged.connect(self.on_game_selected)
        controls_layout.addWidget(self.game_cb)
        self.main_layout.addLayout(controls_layout)
        self.board_widget = ReplayBoardWidget(self)
        self.main_layout.addWidget(self.board_widget, stretch=1)
        self.status_label = QLabel("Ожидание выбора реплея...")
        self.main_layout.addWidget(self.status_label)
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("Предыдущий ход")
        self.prev_btn.clicked.connect(self.prev_move)
        nav_layout.addWidget(self.prev_btn)
        self.next_btn = QPushButton("Следующий ход")
        self.next_btn.clicked.connect(self.next_move)
        nav_layout.addWidget(self.next_btn)
        self.auto_btn = QPushButton("Автопроигрывание")
        self.auto_btn.setCheckable(True)
        self.auto_btn.clicked.connect(self.toggle_auto)
        nav_layout.addWidget(self.auto_btn)
        self.speed_cb = QComboBox()
        self.speed_cb.addItems(["Медленная", "Нормальная", "Быстрая"])
        self.speed_cb.setCurrentIndex(1)
        self.speed_cb.currentIndexChanged.connect(self.update_speed)
        nav_layout.addWidget(QLabel("Скорость:"))
        nav_layout.addWidget(self.speed_cb)
        self.main_layout.addLayout(nav_layout)

    def load_epochs(self):
        if not os.path.exists("replays"):
            os.makedirs("replays")
        files = [f for f in os.listdir("replays") if f.endswith(".json")]

        def epoch_num(f):
            name = f.split(".")[0]
            if name.startswith("epoch_"):
                try:
                    return int(name.split("_")[1])
                except Exception:
                    return 0
            return 0

        files.sort(key=epoch_num)

        current_epoch_path = None
        if self.epoch_cb.count() > 0 and self.epoch_cb.currentIndex() >= 0:
            current_epoch_path = self.epoch_cb.currentData()

        if len(files) == self.epoch_cb.count():
            return

        self.epoch_cb.blockSignals(True)
        self.epoch_cb.clear()
        new_index = 0
        for i, f in enumerate(files):
            self.epoch_cb.addItem(f"Эпоха {epoch_num(f)}", f)
            if f == current_epoch_path:
                new_index = i
        self.epoch_cb.setCurrentIndex(new_index)
        self.epoch_cb.blockSignals(False)

        if current_epoch_path is None and files:
            self.on_epoch_selected(0)

    def on_epoch_selected(self, index):
        if index < 0:
            return
        file_name = self.epoch_cb.itemData(index)
        path = os.path.join("replays", file_name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.current_epoch_data = json.load(f)
            self.game_cb.blockSignals(True)
            self.game_cb.clear()
            games = self.current_epoch_data.get("games", [])
            winners = self.current_epoch_data.get("winners", [])
            for i in range(len(games)):
                w = winners[i] if i < len(winners) else 0
                winner_text = "Ничья" if w == 0 else f"Победитель {w}"
                self.game_cb.addItem(f"Партия {i+1} ({winner_text})", i)
            self.game_cb.blockSignals(False)
            if games:
                self.on_game_selected(0)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить файл: {e}")

    def on_game_selected(self, index):
        if index < 0 or not self.current_epoch_data:
            return
        self.current_game_index = index
        self.current_game_moves = self.current_epoch_data["games"][index]
        self.current_move_index = 0
        if self.auto_btn.isChecked():
            self.auto_play_timer.stop()
            self.start_auto_timer()
        else:
            self.auto_play_timer.stop()
            self.auto_btn.setChecked(False)
            self.auto_btn.setText("Автопроигрывание")
        self.update_board()

    def prev_move(self):
        if self.current_move_index > 0:
            self.current_move_index -= 1
            self.update_board()

    def next_move(self):
        if self.current_move_index < len(self.current_game_moves):
            self.current_move_index += 1
            self.update_board()
        elif self.auto_btn.isChecked():
            self.next_game()

    def next_game(self):
        if not self.current_epoch_data:
            return
        games = self.current_epoch_data.get("games", [])
        if self.current_game_index + 1 < len(games):
            self.game_cb.setCurrentIndex(self.current_game_index + 1)
        else:
            self.toggle_auto()

    def update_speed(self):
        if self.auto_btn.isChecked():
            self.auto_play_timer.stop()
            self.start_auto_timer()

    def start_auto_timer(self):
        speeds = [500, 150, 50]
        self.auto_play_timer.start(speeds[self.speed_cb.currentIndex()])

    def toggle_auto(self):
        if self.auto_btn.isChecked():
            if self.current_move_index >= len(self.current_game_moves):
                self.next_game()
                if not self.auto_btn.isChecked():
                    return
            self.auto_btn.setText("Остановить")
            self.start_auto_timer()
        else:
            self.auto_btn.setText("Автопроигрывание")
            self.auto_play_timer.stop()

    def update_board(self):
        moves = len(self.current_game_moves)
        self.status_label.setText(f"Ход {self.current_move_index} из {moves}")
        self.board_widget.update()

    def draw_board(self, painter):
        painter.setPen(QPen(QColor("lightgray"), 1))
        for i in range(GRID_SIZE + 1):
            painter.drawLine(0, int(i * self.cell_size), int(GRID_SIZE * self.cell_size), int(i * self.cell_size))
            painter.drawLine(int(i * self.cell_size), 0, int(i * self.cell_size), int(GRID_SIZE * self.cell_size))

        moves_to_draw = self.current_game_moves[:self.current_move_index]

        if moves_to_draw:
            last_move = moves_to_draw[-1]
            p, x, y = last_move
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("yellow")))
            painter.drawRect(QtCore.QRectF(x * self.cell_size, y * self.cell_size, self.cell_size, self.cell_size))

        for move in moves_to_draw:
            p, x, y = move
            self.draw_symbol(painter, x, y, p)

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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ReplayViewer()
    window.show()
    sys.exit(app.exec())
