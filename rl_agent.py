import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Categorical

class RLAgent(nn.Module):
    def __init__(self, board_size=30):
        super(RLAgent, self).__init__()
        self.board_size = board_size
        
        # Deep network for learning complex patterns
        # Inputs: 3 channels (my pieces, player 2, player 3)
        self.conv1 = nn.Conv2d(3, 32, kernel_size=5, padding=2)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=5, padding=2)
        self.conv3 = nn.Conv2d(64, 32, kernel_size=3, padding=1)
        self.conv_final = nn.Conv2d(32, 1, kernel_size=3, padding=1)
        
        # Heuristic prior (direct mapping from input to output)
        # We will use this to explicitly bias the network to play near its own pieces
        self.heuristic_conv = nn.Conv2d(3, 1, kernel_size=3, padding=1, bias=False)
        self._initialize_heuristic()
        
        # Scale for deep features starts small, so the heuristic dictates early play
        self.deep_scale = nn.Parameter(torch.tensor(0.01))

    def _initialize_heuristic(self):
        # We want to place near our own pieces (channel 0)
        # So we create a 3x3 adjacency filter for channel 0, with zero for other channels
        # A value of 5.0 means exp(5.0) ~ 148, making adjacent cells much more likely
        adjacency_filter = torch.tensor([
            [[5.0, 5.0, 5.0],
             [5.0, 0.0, 5.0],
             [5.0, 5.0, 5.0]],
            [[0.0, 0.0, 0.0],
             [0.0, 0.0, 0.0],
             [0.0, 0.0, 0.0]],
            [[0.0, 0.0, 0.0],
             [0.0, 0.0, 0.0],
             [0.0, 0.0, 0.0]]
        ])
        
        # Reshape to (out_channels, in_channels, H, W) -> (1, 3, 3, 3)
        self.heuristic_conv.weight.data = adjacency_filter.unsqueeze(0)
        
        # We can either freeze this heuristic or let it train. We'll let it train so the AI can unlearn it if needed.

    def forward(self, x):
        # x is shape (B, 3, H, W)
        deep_features = F.relu(self.conv1(x))
        deep_features = F.relu(self.conv2(deep_features))
        deep_features = F.relu(self.conv3(deep_features))
        deep_logits = self.conv_final(deep_features)
        
        heuristic_logits = self.heuristic_conv(x)
        
        # Combine deep network and heuristic prior
        logits = heuristic_logits + self.deep_scale * deep_logits
        return logits.view(-1, self.board_size * self.board_size) # Flatten to (B, H*W)

    def select_action(self, state, valid_moves_mask):
        """
        state: (3, H, W) tensor
        valid_moves_mask: (H*W) boolean tensor (True for valid moves)
        """
        state = state.unsqueeze(0) # Add batch dimension -> (1, 3, H, W)
        logits = self.forward(state).squeeze(0) # Remove batch dimension -> (H*W)
        
        # Mask invalid moves by setting their logits to -infinity
        logits[~valid_moves_mask] = -float('inf')
        
        # Softmax to get action probabilities
        probs = F.softmax(logits, dim=-1)
        
        # Sample action from the probability distribution
        m = Categorical(probs)
        action = m.sample()
        
        return action.item(), m.log_prob(action)
