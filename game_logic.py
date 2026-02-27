class Board:
    def __init__(self, size=100, win_length=5):
        self.size = size
        self.win_length = win_length
        self.grid = [[0 for _ in range(size)] for _ in range(size)]
        self.winner = None

    def make_move(self, x, y, player):
        if self.is_valid_move(x, y):
            self.grid[y][x] = player
            if self.check_win(x, y, player):
                self.winner = player
            return True
        return False

    def is_valid_move(self, x, y):
        return (0 <= x < self.size and
                0 <= y < self.size and
                self.grid[y][x] == 0 and
                self.winner is None)

    def check_win(self, x, y, player):
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]

        for dx, dy in directions:
            count = 1

            for i in range(1, self.win_length):
                nx, ny = x + dx * i, y + dy * i
                if 0 <= nx < self.size and 0 <= ny < self.size and self.grid[ny][nx] == player:
                    count += 1
                else:
                    break

            for i in range(1, self.win_length):
                nx, ny = x - dx * i, y - dy * i
                if 0 <= nx < self.size and 0 <= ny < self.size and self.grid[ny][nx] == player:
                    count += 1
                else:
                    break

            if count >= self.win_length:
                return True

        return False
