class Constants:
    WALL = ' # '
    FLOOR = '   '
    START = ' S '
    CHEST = ' C '
    ENEMY = ' E '
    EXIT = ' X '
    PLAYER = ' P '


class MapEntity:
    def __init__(self, color: str = "black", text: str = "?"):
        self.color = color
        self.text = text


MapEntities = {
    Constants.WALL: MapEntity(color="blue", text=""),
    Constants.FLOOR: MapEntity(color="black", text=""),
    Constants.CHEST: MapEntity(color="yellow", text="C"),

    Constants.PLAYER: MapEntity(color="white", text="P"),
    Constants.ENEMY: MapEntity(color="red", text="E"),

    Constants.START: MapEntity(color="green", text="Start"),
    Constants.EXIT: MapEntity(color="green", text="Exit"),
}
