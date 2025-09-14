class Chest:
    def __init__(self, x: int, y: int, gold: int):
        self.x = x
        self.y = y
        self.gold = gold

    def __str__(self):
        return f"Chest [{self.x}, {self.y}], gold {self.gold}"
