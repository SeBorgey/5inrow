import sys
import time
import torch
import random
import threading
from network import GameClient
from rl_agent import RLAgent

def make_bot_move(client, agent, board, my_id):
    # Reconstruct state: (3, H, W)
    H, W = 30, 30
    state = torch.zeros((3, H, W), dtype=torch.float32)
    valid_mask = torch.zeros((H * W), dtype=torch.bool)
    
    other_1 = (my_id % 3) + 1
    other_2 = (other_1 % 3) + 1
    
    for y in range(H):
        for x in range(W):
            val = board[y][x]
            if val == my_id:
                state[0, y, x] = 1.0
            elif val == other_1:
                state[1, y, x] = 1.0
            elif val == other_2:
                state[2, y, x] = 1.0
            
            if val == 0:
                valid_mask[y * W + x] = True
            
    if not valid_mask.any():
        return
        
    with torch.no_grad():
        state_batch = state.unsqueeze(0)
        logits = agent(state_batch).squeeze(0)
        logits[~valid_mask] = -float('inf')
        probs = torch.nn.functional.softmax(logits, dim=-1)
        action = torch.argmax(probs).item()
        
    y = action // W
    x = action % W
    
    # Send move slightly delayed to be realistic
    def send_delayed():
        time.sleep(0.5)
        client.send({"type": "MOVE", "x": x, "y": y})
        
    threading.Thread(target=send_delayed, daemon=True).start()


def main():
    if len(sys.argv) > 1:
        ip = sys.argv[1]
    else:
        ip = "127.0.0.1"

    client = GameClient()
    if not client.connect(ip):
        print("Bot failed to connect to", ip)
        return
        
    device = torch.device("cpu")
    agent = RLAgent(board_size=30).to(device)
    try:
        agent.load_state_dict(torch.load("rl_model.pth", map_location=device))
        print("Bot loaded rl_model.pth")
    except Exception as e:
        print(f"Could not load rl_model.pth: {e}")
        return
        
    agent.eval()
    
    my_id = None
    started = False
    board = [[0 for _ in range(30)] for _ in range(30)]
    
    while True:
        messages = client.receive_messages()
        if messages is None:
            break
            
        for msg in messages:
            msg_type = msg.get("type")
            if msg_type == "INIT":
                my_id = msg["player_id"]
                client.send({"type": "SET_NAME", "name": f"Bot {my_id}"})
            elif msg_type == "START":
                started = True
                if msg.get("current_turn") == my_id:
                    make_bot_move(client, agent, board, my_id)
            elif msg_type == "UPDATE":
                x, y, player = msg["x"], msg["y"], msg["player"]
                board[y][x] = player
                if msg.get("next_turn") == my_id:
                    make_bot_move(client, agent, board, my_id)
            elif msg_type == "SKIP_TURN":
                if msg.get("next_turn") == my_id:
                    make_bot_move(client, agent, board, my_id)
            elif msg_type == "RESTART_GAME":
                started = True
                board = [[0 for _ in range(30)] for _ in range(30)]
                if msg.get("current_turn") == my_id:
                    make_bot_move(client, agent, board, my_id)

if __name__ == "__main__":
    main()
