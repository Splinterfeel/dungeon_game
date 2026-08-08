from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api import debug, game, garage, lobby, web
from src.lobby.manager import LobbyManager


app = FastAPI(docs_url="/api/docs", redoc_url="/redoc")

# CORS — разрешаем текущий хост и localhost для дебага
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="web/static"), name="static")

lobby_manager = LobbyManager()
app.state.lobby_manager = lobby_manager

app.include_router(web.router)
app.include_router(lobby.router)
app.include_router(garage.router)
app.include_router(debug.router)
app.include_router(game.router)
