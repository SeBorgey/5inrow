def evaluate_line(count, open_ends):
    if count >= 5: return 100000
    if count == 4:
        if open_ends == 2: return 10000
        if open_ends == 1: return 1000
    if count == 3:
        if open_ends == 2: return 1000
        if open_ends == 1: return 100
    if count == 2:
        if open_ends == 2: return 100
        if open_ends == 1: return 10
    if count == 1:
        if open_ends == 2: return 10
        if open_ends == 1: return 1
    return 0

def evaluate_player(board, player, size):
    score = 0
    def process_line(line):
        nonlocal score
        count = 0
        open_before = False
        for cell in line:
            if cell == player:
                count += 1
            elif cell == 0:
                if count > 0:
                    score += evaluate_line(count, (1 if open_before else 0) + 1)
                    count = 0
                open_before = True
            else:
                if count > 0:
                    score += evaluate_line(count, (1 if open_before else 0))
                    count = 0
                open_before = False
        if count > 0:
            score += evaluate_line(count, (1 if open_before else 0))

    for y in range(size):
        process_line(board[y])
    for x in range(size):
        process_line([board[y][x] for y in range(size)])
    for d in range(-size + 1, size):
        line = [board[x - d][x] for x in range(size) if 0 <= x - d < size]
        if line: process_line(line)
    for d in range(2 * size - 1):
        line = [board[d - x][x] for x in range(size) if 0 <= d - x < size]
        if line: process_line(line)
    return score

def evaluate_state(board, my_id, other1, other2, size):
    my_score = evaluate_player(board, my_id, size)
    o1_score = evaluate_player(board, other1, size)
    o2_score = evaluate_player(board, other2, size)
    return my_score - max(o1_score, o2_score) * 1.5

def has_neighbor(board, x, y, radius, size):
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            ny, nx = y + dy, x + dx
            if 0 <= ny < size and 0 <= nx < size and (ny != y or nx != x):
                if board[ny][nx] != 0: return True
    return False

def get_possible_moves(board, size):
    moves = []
    min_x, min_y, max_x, max_y = size, size, -1, -1
    for y in range(size):
        for x in range(size):
            if board[y][x] != 0:
                if x < min_x: min_x = x
                if y < min_y: min_y = y
                if x > max_x: max_x = x
                if y > max_y: max_y = y
    if max_x == -1: return [(size // 2, size // 2)]
    min_x = max(0, min_x - 2)
    max_x = min(size - 1, max_x + 2)
    min_y = max(0, min_y - 2)
    max_y = min(size - 1, max_y + 2)
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            if board[y][x] == 0 and has_neighbor(board, x, y, 2, size):
                moves.append((x, y))
    return moves

class MinimaxAgent:
    def __init__(self, board_size=30):
        self.size = board_size

    def get_best_move(self, board, my_id):
        other1 = (my_id % 3) + 1
        other2 = (other1 % 3) + 1
        moves = get_possible_moves(board, self.size)
        if not moves: return self.size // 2, self.size // 2

        scored_moves = []
        for x, y in moves:
            board[y][x] = my_id
            score = evaluate_state(board, my_id, other1, other2, self.size)
            board[y][x] = 0
            scored_moves.append((score, x, y))
        
        scored_moves.sort(reverse=True, key=lambda m: m[0])
        best_score = -float('inf')
        best_move = (scored_moves[0][1], scored_moves[0][2])

        for base_score, x, y in scored_moves[:15]:
            board[y][x] = my_id
            if base_score > 50000:
                board[y][x] = 0
                return x, y
            opp_moves = get_possible_moves(board, self.size)
            worst_score = base_score
            for ox, oy in opp_moves:
                board[oy][ox] = other1
                s1 = evaluate_state(board, my_id, other1, other2, self.size)
                board[oy][ox] = 0
                if s1 < worst_score: worst_score = s1
                
                board[oy][ox] = other2
                s2 = evaluate_state(board, my_id, other1, other2, self.size)
                board[oy][ox] = 0
                if s2 < worst_score: worst_score = s2
                
                if worst_score < best_score: break
            board[y][x] = 0
            if worst_score > best_score:
                best_score = worst_score
                best_move = (x, y)
        return best_move
