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


# Stop the server after tests are done
server_process.terminate()
