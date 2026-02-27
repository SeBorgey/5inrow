import sys
import time
import torch
import threading
from network import GameClient
from rl_agent import RLAgent

BOARD_SIZE = 30

def make_bot_move(client, agent, board, my_id):
    state = torch.zeros((3, BOARD_SIZE, BOARD_SIZE), dtype=torch.float32)
    valid_mask = torch.zeros(BOARD_SIZE * BOARD_SIZE, dtype=torch.bool)

    other_1 = (my_id % 3) + 1
    other_2 = (other_1 % 3) + 1

    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            val = board[y][x]
            if val == my_id:
                state[0, y, x] = 1.0
            elif val == other_1:
                state[1, y, x] = 1.0
            elif val == other_2:
                state[2, y, x] = 1.0

            if val == 0:
                valid_mask[y * BOARD_SIZE + x] = True

    if not valid_mask.any():
        return

    with torch.no_grad():
        logits = agent(state.unsqueeze(0)).squeeze(0)
        logits[~valid_mask] = -float('inf')
        probs = torch.nn.functional.softmax(logits, dim=-1)
        action = torch.argmax(probs).item()

    y = action // BOARD_SIZE
    x = action % BOARD_SIZE

    def send_delayed():
        time.sleep(0.5)
        client.send({"type": "MOVE", "x": x, "y": y})

    threading.Thread(target=send_delayed, daemon=True).start()


def main():
    ip = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"

    client = GameClient()
    if not client.connect(ip):
        print("Bot failed to connect to", ip)
        return

    agent = RLAgent(board_size=BOARD_SIZE)
    try:
        agent.load_state_dict(torch.load("rl_model.pth", map_location="cpu"))
        print("Bot loaded rl_model.pth")
    except Exception as e:
        print(f"Could not load rl_model.pth: {e}")
        return

    agent.eval()

    my_id = None
    board = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]

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
                board = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
                if msg.get("current_turn") == my_id:
                    make_bot_move(client, agent, board, my_id)

if __name__ == "__main__":
    main()
