import threading
from base import Point
from src.constants import Constants, MapEntities, MapEntity
import matplotlib
import matplotlib.pyplot as plt


matplotlib.use('wxcairo')


SIG_EXIT = threading.Event()


class DungeonMap:
    def __init__(self, width: int, height: int):
        self._width = width
        self._height = height
        self.plt_thread: threading.Thread = None
        self.tiles = [
            [
                Constants.WALL for _ in range(self._height)
            ] for _ in range(self._width)
        ]

    def get(self, point: Point):
        return self.tiles[point.x][point.y]

    def set(self, point: Point, value):
        self.tiles[point.x][point.y] = value

    def is_free(self, point: Point) -> bool:
        if self.get(point) == Constants.FLOOR:
            return True
        return False

    def show(self):
        self.plt_thread = threading.Thread(target=plt_show, args=[self])
        self.plt_thread.start()

    def destroy(self):
        SIG_EXIT.set()
        if self.plt_thread:
            self.plt_thread.join()


def plt_show(map: DungeonMap):
    # визуализация
    fig, ax = plt.subplots(figsize=(6, 6))
    while True:
        plt.show(block=False)
        for y in range(map._width):
            for x in range(map._height):
                map_entity = MapEntities.get(map.get(Point(x, y)), MapEntity())
                rect = plt.Rectangle((x, y), 1, 1, facecolor=map_entity.color, edgecolor='gray')
                ax.add_patch(rect)
                ax.text(
                    x + 0.5, y + 0.5, map_entity.text,
                    ha='center', va='center', fontsize=6, color='black'
                )
                # показываем номер шага, если клетка достижима и не старт
                # if (x, y) in reachable and (x, y) != start:
                #     ax.text(x + 0.5, y + 0.5, str(reachable[(x, y)]),
                #             ha='center', va='center', fontsize=8, color='black')

        ax.set_xlim(0, map._width)
        ax.set_ylim(0, map._height)
        ax.set_aspect('equal')
        ax.invert_yaxis()
        ax.axis('off')
        plt.pause(0.3)
        if SIG_EXIT.is_set():
            break
    print("Destroying thread...")
