from src import Dungeon
import threading
from src.audio import run_sound_thread
from src.entities.base import CharacterStats
from src.entities.player import Player
from src.game import Game
import warnings

from src.visualization import render_thread


warnings.filterwarnings("ignore")


player_1 = Player(
    name="Player 1",
    position=None,
    stats=CharacterStats(health=10, damage=5, speed=3, action_points=10),
)
# player_2 = Player(
#     name="Player 2",
#     position=None,
#     stats=CharacterStats(health=8, damage=3, speed=5, action_points=10),
# )
# player_3 = Player(
#     name="Player 3",
#     position=None,
#     stats=CharacterStats(health=8, damage=3, speed=5, action_points=10),
# )


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
    # players=[player_1, player_2, player_3],
    players=[player_1],
)
game.init()
sound_thread = threading.Thread(target=run_sound_thread, daemon=True)
game_thread = threading.Thread(target=run_game, kwargs={"game": game}, daemon=True)
sound_thread.start()
game_thread.start()
render_thread()
