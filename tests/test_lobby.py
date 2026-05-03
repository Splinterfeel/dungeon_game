import subprocess
import time
from fastapi.testclient import TestClient
from main import app
from uuid import UUID

# Start the FastAPI server in a separate process
server_process = subprocess.Popen(["uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"])

# Wait for the server to start
time.sleep(5)

client = TestClient(app)


def test_create_lobby():
    response = client.post("/lobbies", json={
        "players_num": 2,
        "created_by_player_id": "123e4567-e89b-12d3-a456-426614174000"
        }
    )
    assert response.status_code == 200
    assert "lobby_id" in response.json()


def test_connect_to_nonexistent_lobby():
    nonexistent_lobby_id = UUID("123e4567-e89b-12d3-a456-426614174000")
    response = client.post("/connect_lobby", json={
            "lobby_id": str(nonexistent_lobby_id),
            "player": {"id": "123e4567-e89b-12d3-a456-426614174000"}
        }
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Lobby not found"}


def test_join_lobby():
    resp = client.post("/lobbies", json={
        "players_num": 2,
        "created_by_player_id": "123e4567-e89b-12d3-a456-426614174000"
        }
    )
    response = client.post("/connect_lobby", json={
            "lobby_id": resp.json()["lobby_id"],
            "player": {"id": "123e4567-e89b-12d3-a456-426614174000"}
        }
    )
    assert response.status_code == 200
    assert response.json()["detail"] == "player connected"


def test_connect_to_full_lobby():
    # Create a lobby with 2 players
    resp = client.post("/lobbies", json={
        "players_num": 1,
        "created_by_player_id": "123e4567-e89b-12d3-a456-426614174000"
    })
    lobby_id = resp.json()["lobby_id"]

    # Connect the 1st player to fill the lobby
    client.post("/connect_lobby", json={
        "lobby_id": lobby_id,
        "player": {"id": "123e4567-e89b-12d3-a456-426614174001"}
    })

    # Try to connect the 2nd player to the full lobby
    response = client.post("/connect_lobby", json={
        "lobby_id": lobby_id,
        "player": {"id": "123e4567-e89b-12d3-a456-426614174002"}
    })
    assert response.status_code == 200
    assert response.json()["detail"] == "lobby full"


# Stop the server after tests are done
server_process.terminate()
