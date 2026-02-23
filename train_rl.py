import torch
import torch.optim as optim
import time
from rl_agent import RLAgent
from batched_board import BatchedBoard

def batched_get_state(grid, player_id, device):
    """
    grid: (B, H, W)
    Returns: (B, 3, H, W)
    """
    B, H, W = grid.shape
    state = torch.zeros((B, 3, H, W), dtype=torch.float32, device=device)
    
    state[:, 0] = (grid == player_id).float()
    
    other_1 = (player_id % 3) + 1
    other_2 = (other_1 % 3) + 1
    
    state[:, 1] = (grid == other_1).float()
    state[:, 2] = (grid == other_2).float()
    
    return state

def batched_play_games(agent, batch_size, device, board_size=30):
    envs = BatchedBoard(batch_size=batch_size, size=board_size, device=device)
    
    log_probs = {1: [], 2: [], 3: []}
    
    current_player = 1
    
    while not envs.done.all():
        active_mask = ~envs.done
        
        # Valid mask: (B, H*W)
        valid_mask = (envs.grid == 0).view(batch_size, -1)
        
        state = batched_get_state(envs.grid, current_player, device)
        
        # We process the whole batch through the network
        # For done environments, we can pass dummy inputs or just process them and ignore outputs
        with torch.no_grad():
            # (We need gradients for REINFORCE, so actually NO torch.no_grad here)
            pass
            
        # We need to evaluate the agent. We evaluate all environments.
        # select_action must be batched!
        logits = agent(state) # (B, H*W)
        logits[~valid_mask] = -float('inf')
        
        probs = torch.nn.functional.softmax(logits, dim=-1)
        m = torch.distributions.Categorical(probs)
        actions = m.sample() # (B,)
        
        step_log_probs = m.log_prob(actions) # (B,)
        
        envs.make_move(actions, current_player)
        
        # Zero out log probs for environments that are already done before this step
        step_log_probs = step_log_probs * active_mask.float()
        
        log_probs[current_player].append(step_log_probs)
        
        current_player = (current_player % 3) + 1
        
    # Calculate rewards for all environments
    # final_rewards dict will store (B,) reward tensors
    final_rewards = {1: torch.zeros(batch_size, device=device), 
                     2: torch.zeros(batch_size, device=device), 
                     3: torch.zeros(batch_size, device=device)}
                     
    for p in [1, 2, 3]:
        won = (envs.winner == p)
        lost = (envs.winner != 0) & (envs.winner != p)
        final_rewards[p][won] = 1.0
        final_rewards[p][lost] = -1.0
        
    return log_probs, final_rewards, envs.winner

def train():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on device: {device}")
    
    board_size = 30
    agent = RLAgent(board_size=board_size).to(device)
    optimizer = optim.Adam(agent.parameters(), lr=1e-3)
    
    episodes = 1000  # We do fewer episodes because each episode is a batch of games
    batch_games = 128 # Simulating 128 games in parallel on GPU!
    
    print(f"Starting batched RL training loop: {batch_games} games simultaneously...")
    start_time = time.time()
    
    for episode in range(1, episodes + 1):
        log_probs, final_rewards, winners = batched_play_games(agent, batch_games, device, board_size)
        
        # Calculate loss
        policy_loss = []
        for p in [1, 2, 3]:
            r = final_rewards[p].unsqueeze(0) # (1, B)
            if len(log_probs[p]) > 0:
                p_log_probs = torch.stack(log_probs[p]) # (T, B)
                loss_term = -p_log_probs * r # (T, B)
                policy_loss.append(loss_term.sum())
                
        loss = torch.stack(policy_loss).sum() / batch_games
        
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
            
        p1_wins = (winners == 1).sum().item()
        p2_wins = (winners == 2).sum().item()
        p3_wins = (winners == 3).sum().item()
        draws = (winners == 0).sum().item()
        
        elapsed = time.time() - start_time
        print(f"Batch {episode} | P1: {p1_wins}, P2: {p2_wins}, P3: {p3_wins}, Draws: {draws} | Time: {elapsed:.2f}s")
        start_time = time.time()
            
        if episode % 10 == 0:
            torch.save(agent.state_dict(), "rl_model.pth")

if __name__ == "__main__":
    train()
