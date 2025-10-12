from xml.dom.minidom import Entity
from base import Point
from dungeon.entities.base import CharacterStats


class Player(Entity):
    def __init__(self, positon: Point, stats: CharacterStats):
        self.stats = stats
        super().__init__()
