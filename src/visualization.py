from __future__ import annotations
import queue
import time

from src.game import Game
from copy import deepcopy
import matplotlib.pyplot as plt
from src.base import Point, Queues
from src.constants import CELL_TYPE, ColorPallette, MapEntities, MapEntity
from matplotlib.patches import FancyBboxPatch


import matplotlib
from matplotlib.text import Text as mText


from src.interaction import InteractionHandlers


matplotlib.use("tkagg")


class Visualization:
    def __init__(self):
        self.game = None
        while self.game is None:
            print("[RENDER] waiting for game state")
            self.read_new_game_state()
            time.sleep(0.2)
        self.menu_drawables = []  # все артисты меню (фон + тексты)
        self.menu_texts = (
            []
        )  # текстовые артисты (для hit-testing через .contains(event))
        self.menu_callbacks = []  # соответствующие callback'и для текстов
        self.menu_exists = False
        # init matplotlib
        self.fig, self.ax = plt.subplots(figsize=(6, 6))
        self.ax.set_xlim(0, self.game.dungeon.map.width)
        self.ax.set_ylim(0, self.game.dungeon.map.height)
        self.ax.set_aspect("equal")
        self.ax.invert_yaxis()
        self.ax.axis("off")
        self.rects: dict[tuple, plt.Rectangle] = {}
        self.texts: dict[tuple, mText] = {}
        self.fig.canvas.mpl_connect("button_press_event", self.onclick)
        self.init_map()

    def clear_menu(self):
        """Безопасно удаляет все элементы меню (если они ещё существуют)."""
        for a in self.menu_drawables:
            try:
                a.remove()
            except Exception:
                # если по какой-то причине remove() не поддерживается или артист уже удалён — пропускаем
                pass
        self.menu_drawables = []
        self.menu_texts = []
        self.menu_callbacks = []
        self.menu_exists = False
        self.fig.canvas.draw_idle()

    def init_map(self):
        # создаём сетку один раз
        for y in range(self.game.dungeon.height):
            for x in range(self.game.dungeon.width):
                rect = plt.Rectangle(
                    (x, y),
                    1,
                    1,
                    facecolor="wheat",
                    edgecolor=ColorPallette.DEFAULT_EDGE_COLOR,
                )
                self.ax.add_patch(rect)
                self.rects[(x, y)] = rect
                t = self.ax.text(
                    x + 0.5,
                    y + 0.5,
                    "",
                    ha="center",
                    va="center",
                    fontsize=6,
                    color="black",
                )
                self.texts[(x, y)] = t

    def read_new_game_state(self):
        while not Queues.RENDER_QUEUE.empty():
            try:
                new_game_dump = Queues.RENDER_QUEUE.get_nowait()
                self.game = Game.from_dict(new_game_dump)
            except queue.Empty:
                break

    def loop(self):
        plt.show(block=False)
        while True:
            self.read_new_game_state()
            for x in range(self.game.dungeon.width):
                for y in range(self.game.dungeon.map.height):
                    map_entity = MapEntities.get(
                        self.game.dungeon.map.get(Point(x, y)), MapEntity()
                    )
                    rect = self.rects[(x, y)]
                    text = self.texts[(x, y)]
                    rect.set_facecolor(map_entity.color)
                    rect.set_edgecolor(ColorPallette.DEFAULT_EDGE_COLOR)
                    text.set_text(map_entity.text)
            # дорисовываем клетки доступные для перемещения, другой BG цвет
            move_points = deepcopy(self.game.turn.available_moves)
            for point in move_points:
                rect = self.rects[(point.x, point.y)]
                rect.set_edgecolor(ColorPallette.MOVE_CELL_EDGE_COLOR)
                rect.set_facecolor(ColorPallette.MOVE_CELL_BG_COLOR)
            self.fig.canvas.draw_idle()
            plt.pause(0.1)

    def show_menu_at(self, event, cell: Point, cell_type: CELL_TYPE):
        """
        Показывает компактное меню рядом с координатами event.xdata/event.ydata.
        Для hit-testing используется метод artist.contains(event).
        """
        self.clear_menu()
        # Формируем список опций в зависимости от типа клетки
        interaction_options = InteractionHandlers.get_interaction_options(
            actor=self.game.turn.current_actor, cell=cell, cell_type=cell_type
        )

        # Позиционируем меню так, чтобы оно не выходило за пределы axes
        mx = event.xdata
        my = event.ydata
        menu_width = 6
        option_height = 1
        total_height = option_height * len(interaction_options)
        # # Подвинем меню влево/вверх при необходимости, чтобы не выходило правее/ниже
        if mx + menu_width > self.game.dungeon.map.width:
            mx = self.game.dungeon.map.width - menu_width - 0.1
        if my + total_height > self.game.dungeon.map.height:
            my = self.game.dungeon.map.height - total_height - 0.1
        if mx < 0.1:
            mx = 0.1
        if my < 0.1:
            my = 0.1

        # Фон меню (с закруглением)
        bg = FancyBboxPatch(
            (mx, my - 0.5),
            menu_width,
            total_height,
            boxstyle="round,pad=0.02",
            linewidth=1,
            facecolor="white",
            edgecolor="black",
            zorder=10,
        )
        self.ax.add_patch(bg)
        self.menu_drawables.append(bg)

        # Добавим опции как тексты
        for i, (label, callback, params) in enumerate(interaction_options):
            ty = (
                my
                + (len(interaction_options) - 1 - i) * option_height
                + option_height * 0.15
            )
            txt = self.ax.text(
                mx + menu_width * 0.5,
                ty,
                label,
                ha="center",
                va="center",
                fontsize=9,
                zorder=11,
            )
            self.menu_drawables.append(txt)
            self.menu_texts.append(txt)
            # Сохраняем обёртку callback, передаём cell как параметр
            self.menu_callbacks.append(lambda cb=callback, actor=self.game.turn.current_actor, cell=cell, params=params: cb(actor, cell, params))
        self.menu_exists = True
        self.fig.canvas.draw()  # нужно, чтобы artist.contains(event) корректно работал

    def onclick(self, event):
        # Сначала проверим — клик по пункту меню?
        if self.menu_exists:
            for i, txt in enumerate(self.menu_texts):
                contains, _ = txt.contains(event)
                if contains:
                    # вызываем соответствующий callback
                    self.menu_callbacks[i]()
                    self.clear_menu()
                    return
            # если меню открыто, но клик не по нему - закрываем меню
            self.clear_menu()
            return
        cell = Point(int(event.xdata), int(event.ydata))
        cell_value = self.game.dungeon.map.get(cell)
        cell_type = CELL_TYPE(cell_value)
        if not self.menu_exists:
            self.show_menu_at(event, cell, cell_type)


def render_thread(*args, **kwargs):
    visualization = Visualization(*args, **kwargs)
    visualization.loop()
