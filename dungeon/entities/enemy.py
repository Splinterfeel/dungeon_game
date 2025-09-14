from base import Point


class Enemy:
    def __init__(self, position: Point, health: int, damage: int):
        self.position = position
        self.health = health
        self.damage = damage
