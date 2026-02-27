import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Categorical

class RLAgent(nn.Module):
    def __init__(self, board_size=30):
        super(RLAgent, self).__init__()
        self.board_size = board_size

        self.conv1 = nn.Conv2d(3, 32, kernel_size=5, padding=2)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=5, padding=2)
        self.conv3 = nn.Conv2d(64, 32, kernel_size=3, padding=1)
        self.conv_final = nn.Conv2d(32, 1, kernel_size=3, padding=1)

        self.heuristic_conv = nn.Conv2d(3, 1, kernel_size=3, padding=1, bias=False)
        self._initialize_heuristic()

        self.deep_scale = nn.Parameter(torch.tensor(0.01))

    def _initialize_heuristic(self):
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
        self.heuristic_conv.weight.data = adjacency_filter.unsqueeze(0)

    def forward(self, x):
        deep_features = F.relu(self.conv1(x))
        deep_features = F.relu(self.conv2(deep_features))
        deep_features = F.relu(self.conv3(deep_features))
        deep_logits = self.conv_final(deep_features)

        heuristic_logits = self.heuristic_conv(x)

        logits = heuristic_logits + self.deep_scale * deep_logits
        return logits.view(-1, self.board_size * self.board_size)

    def select_action(self, state, valid_moves_mask):
        state = state.unsqueeze(0)
        logits = self.forward(state).squeeze(0)

        logits[~valid_moves_mask] = -float('inf')

        probs = F.softmax(logits, dim=-1)

        m = Categorical(probs)
        action = m.sample()

        return action.item(), m.log_prob(action)
