from src import Dungeon
from src.entities.base import CharacterStats
from src.entities.player import Player
from src.game import Game
import warnings


warnings.filterwarnings("ignore")


player_1 = Player(name="Me", positon=None, stats=CharacterStats(health=10, damage=3, speed=3))
player_2 = Player(name="Me2", positon=None, stats=CharacterStats(health=8, damage=4, speed=4))

dungeon = Dungeon(
    width=20, height=20,
    min_rooms=3, max_rooms=4,
    min_room_size=4, max_room_size=5,
    max_chests=3,
    enemies_num=2,
)
game = Game(
    dungeon=dungeon,
    players=[player_1, player_2],
    with_plot=True,
)
game.init()
game.loop()
