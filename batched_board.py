import torch

class BatchedBoard:
    def __init__(self, batch_size, size=30, win_length=5, device="cpu"):
        self.batch_size = batch_size
        self.size = size
        self.win_length = win_length
        self.device = device
        
        # Grid shape: (batch_size, size, size)
        # 0: Empty, 1: P1, 2: P2, 3: P3
        self.grid = torch.zeros((batch_size, size, size), dtype=torch.long, device=device)
        
        # Boolean masks keeping track of finished games in the batch
        self.done = torch.zeros(batch_size, dtype=torch.bool, device=device)
        self.winner = torch.zeros(batch_size, dtype=torch.long, device=device) # 0 means no winner
        
    def reset(self):
        self.grid.zero_()
        self.done.zero_()
        self.winner.zero_()
        
    def make_move(self, actions_flat, player):
        # actions_flat is (batch_size,) containing indices in [0, size*size - 1]
        active_mask = ~self.done
        
        # We only apply moves for environments that are not done
        y = actions_flat // self.size
        x = actions_flat % self.size
        
        batch_indices = torch.arange(self.batch_size, device=self.device)
        
        # Valid moves mask
        valid = (self.grid[batch_indices, y, x] == 0) & active_mask
        
        # Apply valid moves
        self.grid[batch_indices[valid], y[valid], x[valid]] = player
        
        # Check wins only for environments that just moved
        wins = self.check_win(x, y, player) & valid
        
        self.winner[wins] = player
        self.done[wins] = True
        
        # Check draws
        empty_count = (self.grid == 0).sum(dim=(1, 2))
        draws = (empty_count == 0) & active_mask & ~wins
        self.done[draws] = True
        
        return valid
        
    def check_win(self, x_batch, y_batch, player):
        """
        Check win for the last placed piece in vectorized form.
        x_batch, y_batch are (batch_size,)
        Returns boolean tensor of shape (batch,)
        """
        batch_indices = torch.arange(self.batch_size, device=self.device)
        wins = torch.zeros(self.batch_size, dtype=torch.bool, device=self.device)
        
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        
        for dx, dy in directions:
            count = torch.ones(self.batch_size, dtype=torch.long, device=self.device)
            
            # Check forward
            for i in range(1, self.win_length):
                nx = x_batch + dx * i
                ny = y_batch + dy * i
                
                valid_bounds = (nx >= 0) & (nx < self.size) & (ny >= 0) & (ny < self.size)
                
                # We need to gather safely. For out of bounds, we can just use 0 index 
                # but mask the result out using valid_bounds
                safe_nx = torch.clamp(nx, 0, self.size - 1)
                safe_ny = torch.clamp(ny, 0, self.size - 1)
                
                match = (self.grid[batch_indices, safe_ny, safe_nx] == player) & valid_bounds
                count += match.long()
                
                # Optimization: if match is false, we technically should stop counting for that batch element
                # Vectorizing the "break" is tricky, but for N=5 we can just compute it exactly.
                # Actually, 5 in a row must be contiguous.
                # Let's count contiguously:
            
        # A fully correct contiguous check in PyTorch natively for the whole batch is complex but feasible.
        # Since we just placed at x, y, we can do convolution or simple shifting.
        # Let's use convolution on the specific player's board.
        player_board = (self.grid == player).float().unsqueeze(1) # (B, 1, H, W)
        
        # Vertical
        kernel_v = torch.ones((1, 1, self.win_length, 1), device=self.device)
        conv_v = torch.nn.functional.conv2d(player_board, kernel_v, padding=(self.win_length//2, 0))
        
        # Horizontal
        kernel_h = torch.ones((1, 1, 1, self.win_length), device=self.device)
        conv_h = torch.nn.functional.conv2d(player_board, kernel_h, padding=(0, self.win_length//2))
        
        # Main diagonal
        kernel_d1 = torch.eye(self.win_length, device=self.device).view(1, 1, self.win_length, self.win_length)
        conv_d1 = torch.nn.functional.conv2d(player_board, kernel_d1, padding=self.win_length//2)
        
        # Anti diagonal
        kernel_d2 = torch.fliplr(torch.eye(self.win_length, device=self.device)).view(1, 1, self.win_length, self.win_length)
        conv_d2 = torch.nn.functional.conv2d(player_board, kernel_d2, padding=self.win_length//2)
        
        # A win occurs if any of these convolutions reaches win_length
        m_v = (conv_v >= self.win_length).view(self.batch_size, -1).any(dim=1)
        m_h = (conv_h >= self.win_length).view(self.batch_size, -1).any(dim=1)
        m_d1 = (conv_d1 >= self.win_length).view(self.batch_size, -1).any(dim=1)
        m_d2 = (conv_d2 >= self.win_length).view(self.batch_size, -1).any(dim=1)
        
        wins = m_v | m_h | m_d1 | m_d2
        return wins
