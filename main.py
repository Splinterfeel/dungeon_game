from src import Dungeon
import threading
from src.entities.base import CharacterStats
from src.entities.player import Player
from src.game import Game
import warnings

from src.visualization import render_thread


warnings.filterwarnings("ignore")


player_1 = Player(
    name="Me", position=None, stats=CharacterStats(health=10, damage=3, speed=3)
)
player_2 = Player(
    name="Me2", position=None, stats=CharacterStats(health=8, damage=4, speed=4)
)


def run_game(game: Game):
    game.loop()


dungeon = Dungeon(
    width=20,
    height=20,
    min_rooms=3,
    max_rooms=4,
    min_room_size=4,
    max_room_size=5,
    max_chests=3,
    enemies_num=2,
)
game = Game(
    dungeon=dungeon,
    players=[player_1, player_2],
)
game.init()
game_thread = threading.Thread(target=run_game, kwargs={"game": game}, daemon=True)
game_thread.start()
render_thread()
