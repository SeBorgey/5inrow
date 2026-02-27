import sys
import time
import threading
from network import GameClient
from minimax_bot import MinimaxAgent

BOARD_SIZE = 30

def make_bot_move(client, agent, board, my_id):
    x, y = agent.get_best_move(board, my_id)

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

    agent = MinimaxAgent(board_size=BOARD_SIZE)

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
