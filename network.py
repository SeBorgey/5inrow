import socket
import threading
import json
import time

PORT = 5555
BUFFER_SIZE = 4096

class GameServer:
    def __init__(self, host='0.0.0.0', port=PORT):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen(3)
        self.clients = [] # [(conn, addr), ...]
        self.player_ids = {} # conn -> player_id (1, 2, 3)
        self.player_names = {} # player_id -> name
        self.current_turn = 1
        self.game_started = False
        self.lock = threading.Lock()
        print(f"Server started on {host}:{port}")

    def start(self):
        print("Waiting for players...")
        while len(self.clients) < 3:
            conn, addr = self.server.accept()
            with self.lock:
                if len(self.clients) >= 3:
                    conn.close()
                    continue
                
                player_id = len(self.clients) + 1
                self.clients.append(conn)
                self.player_ids[conn] = player_id
                print(f"Player {player_id} connected from {addr}")
                
                # Send initialization data to client
                self.send_to_client(conn, {"type": "INIT", "player_id": player_id})
                
                if len(self.clients) == 3:
                    print("All 3 players connected. Waiting for names...")
            
            threading.Thread(target=self.handle_client, args=(conn,)).start()

    def handle_client(self, conn):
        player_id = self.player_ids[conn]
        buffer = ""
        while True:
            try:
                data = conn.recv(BUFFER_SIZE)
                if not data:
                    break
                
                buffer += data.decode()
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if not line: continue
                    
                    try:
                        message = json.loads(line)
                    except json.JSONDecodeError:
                        print(f"Server JSON Error: {line}")
                        continue

                    if message["type"] == "SET_NAME":
                        with self.lock:
                            self.player_names[player_id] = message.get("name", f"Player {player_id}")
                            if len(self.player_names) == 3 and not self.game_started:
                                self.game_started = True
                                self.broadcast({
                                    "type": "START", 
                                    "message": "Game Started! Player 1's Turn", 
                                    "current_turn": 1,
                                    "names": self.player_names
                                })
                        continue
                        
                    if message["type"] == "RESTART":
                        if player_id == 1:
                            with self.lock:
                                self.current_turn = 1
                                self.game_started = True
                                self.broadcast({
                                    "type": "RESTART_GAME",
                                    "message": "Game Restarted! Player 1's Turn",
                                    "current_turn": 1
                                })
                        continue

                    if message["type"] == "MOVE":
                        if not self.game_started:
                            continue
                            
                        if self.current_turn != player_id:
                            self.send_to_client(conn, {"type": "ERROR", "message": "Not your turn!"})
                            continue

                        # Broadcast move to all
                        x, y = message["x"], message["y"]
                        # Update turn
                        self.current_turn = (self.current_turn % 3) + 1
                        
                        response = {
                            "type": "UPDATE",
                            "x": x,
                            "y": y,
                            "player": player_id,
                            "next_turn": self.current_turn
                        }
                        self.broadcast(response)
                    
            except Exception as e:
                print(f"Error handling player {player_id}: {e}")
                break
        
        print(f"Player {player_id} disconnected")
        with self.lock:
            if conn in self.clients:
                self.clients.remove(conn)
                del self.player_ids[conn]
                if player_id in self.player_names:
                    del self.player_names[player_id]
        conn.close()

    def send_to_client(self, conn, message):
        try:
            conn.send((json.dumps(message) + "\n").encode())
        except:
            pass

    def broadcast(self, message):
        data = (json.dumps(message) + "\n").encode()
        for client in self.clients:
            try:
                client.send(data)
            except:
                pass

class GameClient:
    def __init__(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.player_id = None
        self.buffer = ""
        
    def connect(self, host, port=PORT):
        try:
            self.client.connect((host, port))
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def send(self, data):
        try:
            self.client.send((json.dumps(data) + "\n").encode())
        except Exception as e:
            print(f"Send error: {e}")

    # Renamed to make it clear it yields messages
    def receive_messages(self):
        try:
            data = self.client.recv(BUFFER_SIZE)
            if not data:
                return None
            
            self.buffer += data.decode()
            messages = []
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                if line:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        print(f"Client JSON Error: {line}")
            return messages
        except Exception as e:
            print(f"Receive error: {e}")
            return None
