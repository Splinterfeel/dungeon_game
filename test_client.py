import asyncio
import json
import uuid
import requests
import websockets

BASE_URL = "http://127.0.0.1:8000"


PLAYERS = [
    {
        "id": str(uuid.uuid4())
    }
]


# ======================
# REST
# ======================

def create_lobby() -> str:
    response = requests.post(
        f"{BASE_URL}/lobbies",
        json={"players": PLAYERS},
    )
    return response.json()["lobby_id"]


# ======================
# WebSocket
# ======================

async def play(lobby_id, player_id):
    ws_url = f"ws://127.0.0.1:8000/ws/{lobby_id}/{player_id}"

    async with websockets.connect(ws_url) as websocket:
        print("Connected to game server")

        # Отправим тестовое движение
        move_action = {
            "type": "MOVE",
            "cell": {"x": 5, "y": 5},
            "ends_turn": False
        }

        await websocket.send(json.dumps(move_action))
        print("Sent MOVE")

        # # Слушаем обновления
        # while True:
        #     message = await websocket.recv()
        #     data = json.loads(message)

        #     if data["type"] == "state_update":
        #         print("\n=== STATE UPDATE ===")
        #         print(json.dumps(data["payload"], indent=2))


# ======================
# Запуск
# ======================

if __name__ == "__main__":
    print("Creating lobby...")
    lobby_id = create_lobby()
    print("Lobby ID:", lobby_id)
    player_id = PLAYERS[0]["id"]
    print("Player ID:", player_id)

    asyncio.run(play(lobby_id, player_id))
