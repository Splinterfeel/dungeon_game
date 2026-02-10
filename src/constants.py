from dataclasses import dataclass
from enum import Enum


class CELL_TYPE(Enum):
    WALL = " # "
    FLOOR = "   "
    START = " S "
    CHEST = " C "
    ENEMY = " E "
    EXIT = " X "
    PLAYER = " P "


class ButtonPressed:
    LEFT = 1
    RIGHT = 3


class MapEntity:
    def __init__(self, color: str = "black", text: str = "?"):
        self.color = color
        self.text = text


MapEntities = {
    CELL_TYPE.WALL.value: MapEntity(color="blue", text=""),
    CELL_TYPE.FLOOR.value: MapEntity(color="black", text=""),
    CELL_TYPE.CHEST.value: MapEntity(color="yellow", text="C"),
    CELL_TYPE.PLAYER.value: MapEntity(color="white", text="P"),
    CELL_TYPE.ENEMY.value: MapEntity(color="red", text="E"),
    CELL_TYPE.START.value: MapEntity(color="green", text="Start"),
    CELL_TYPE.EXIT.value: MapEntity(color="green", text="Exit"),
}


class ColorPallette:
    DEFAULT_EDGE_COLOR = "gray"
    # цвет для ячеек доступных для перемещения
    MOVE_CELL_EDGE_COLOR = "green"
    MOVE_CELL_BG_COLOR = (0.2, 0.2, 0.2)


@dataclass
class AttackType:
    cost: int
    default_multiplier: float

    def to_dict(self):
        return {
            "cost": self.cost,
            "default_multiplier": self.default_multiplier,
        }

    @classmethod
    def from_dict(cls, _dict: dict):
        return cls(**_dict)


class Attack:
    SIMPLE = AttackType(cost=5, default_multiplier=1.0)
    HEAVY = AttackType(cost=8, default_multiplier=1.5)


class ActionPoints:
    ATTACK = 5
    HEAVY_ATTACK = 7
