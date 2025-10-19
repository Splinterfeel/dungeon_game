from enum import Enum


class Constants(Enum):
    WALL = ' # '
    FLOOR = '   '
    START = ' S '
    CHEST = ' C '
    ENEMY = ' E '
    EXIT = ' X '
    PLAYER = ' P '


class ButtonPressed:
    LEFT = 1
    RIGHT = 3


class MapEntity:
    def __init__(self, color: str = "black", text: str = "?"):
        self.color = color
        self.text = text


MapEntities = {
    Constants.WALL.value: MapEntity(color="blue", text=""),
    Constants.FLOOR.value: MapEntity(color="black", text=""),
    Constants.CHEST.value: MapEntity(color="yellow", text="C"),

    Constants.PLAYER.value: MapEntity(color="white", text="P"),
    Constants.ENEMY.value: MapEntity(color="red", text="E"),

    Constants.START.value: MapEntity(color="green", text="Start"),
    Constants.EXIT.value: MapEntity(color="green", text="Exit"),
}
