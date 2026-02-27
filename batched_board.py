import torch

class BatchedBoard:
    def __init__(self, batch_size, size=30, win_length=5, device="cpu"):
        self.batch_size = batch_size
        self.size = size
        self.win_length = win_length
        self.device = device

        self.grid = torch.zeros((batch_size, size, size), dtype=torch.long, device=device)
        self.done = torch.zeros(batch_size, dtype=torch.bool, device=device)
        self.winner = torch.zeros(batch_size, dtype=torch.long, device=device)

    def make_move(self, actions_flat, player):
        active_mask = ~self.done

        y = actions_flat // self.size
        x = actions_flat % self.size

        batch_indices = torch.arange(self.batch_size, device=self.device)

        valid = (self.grid[batch_indices, y, x] == 0) & active_mask
        self.grid[batch_indices[valid], y[valid], x[valid]] = player

        wins = self.check_win(player) & valid
        self.winner[wins] = player
        self.done[wins] = True

        empty_count = (self.grid == 0).sum(dim=(1, 2))
        draws = (empty_count == 0) & active_mask & ~wins
        self.done[draws] = True

        return valid

    def check_win(self, player):
        player_board = (self.grid == player).float().unsqueeze(1)

        kernel_v = torch.ones((1, 1, self.win_length, 1), device=self.device)
        conv_v = torch.nn.functional.conv2d(player_board, kernel_v, padding=(self.win_length // 2, 0))

        kernel_h = torch.ones((1, 1, 1, self.win_length), device=self.device)
        conv_h = torch.nn.functional.conv2d(player_board, kernel_h, padding=(0, self.win_length // 2))

        kernel_d1 = torch.eye(self.win_length, device=self.device).view(1, 1, self.win_length, self.win_length)
        conv_d1 = torch.nn.functional.conv2d(player_board, kernel_d1, padding=self.win_length // 2)

        kernel_d2 = torch.fliplr(torch.eye(self.win_length, device=self.device)).view(1, 1, self.win_length, self.win_length)
        conv_d2 = torch.nn.functional.conv2d(player_board, kernel_d2, padding=self.win_length // 2)

        m_v = (conv_v >= self.win_length).view(self.batch_size, -1).any(dim=1)
        m_h = (conv_h >= self.win_length).view(self.batch_size, -1).any(dim=1)
        m_d1 = (conv_d1 >= self.win_length).view(self.batch_size, -1).any(dim=1)
        m_d2 = (conv_d2 >= self.win_length).view(self.batch_size, -1).any(dim=1)

        return m_v | m_h | m_d1 | m_d2
