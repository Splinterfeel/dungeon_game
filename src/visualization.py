import matplotlib.pyplot as plt
from src.base import Point
from src.constants import CELL_TYPE, MapEntities, MapEntity
from matplotlib.patches import FancyBboxPatch


import matplotlib
from matplotlib.text import Text as mText

from src.interaction import InteractionHandlers
from src.map import DungeonMap


matplotlib.use('tkagg')


class Visualization:
    def __init__(self, map: DungeonMap):
        self.map = map
        self.menu_drawables = []  # все артисты меню (фон + тексты)
        self.menu_texts = []  # текстовые артисты (для hit-testing через .contains(event))
        self.menu_callbacks = []  # соответствующие callback'и для текстов
        self.menu_exists = False
        # init matplotlib
        self.fig, self.ax = plt.subplots(figsize=(6, 6))
        self.ax.set_xlim(0, self.map.width)
        self.ax.set_ylim(0, self.map.height)
        self.ax.set_aspect('equal')
        self.ax.invert_yaxis()
        self.ax.axis('off')
        self.rects: dict[tuple, plt.Rectangle] = {}
        self.texts: dict[tuple, mText] = {}
        self.fig.canvas.mpl_connect("button_press_event", self.onclick)

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
        for y in range(self.map.height):
            for x in range(self.map.width):
                rect = plt.Rectangle((x, y), 1, 1, facecolor='wheat', edgecolor='gray')
                self.ax.add_patch(rect)
                self.rects[(x, y)] = rect
                t = self.ax.text(x + 0.5, y + 0.5, "", ha='center', va='center', fontsize=6, color='black')
                self.texts[(x, y)] = t

    def loop(self):
        plt.show(block=False)
        while True:
            for x in range(self.map.width):
                for y in range(self.map.height):
                    map_entity = MapEntities.get(self.map.get(Point(x, y)), MapEntity())
                    rect = self.rects[(x, y)]
                    text = self.texts[(x, y)]
                    rect.set_facecolor(map_entity.color)
                    text.set_text(map_entity.text)
                    # показываем номер шага, если клетка достижима и не старт
                    # if (x, y) in reachable and (x, y) != start:
                    #     ax.text(x + 0.5, y + 0.5, str(reachable[(x, y)]),
                    #             ha='center', va='center', fontsize=8, color='black')
            self.fig.canvas.draw_idle()
            plt.pause(0.05)

    def show_menu_at(self, event, cell, cell_type):
        """
        Показывает компактное меню рядом с координатами event.xdata/event.ydata.
        Для hit-testing используется метод artist.contains(event).
        """
        self.clear_menu()
        # Формируем список опций в зависимости от типа клетки
        interaction_options = InteractionHandlers.get_interaction_options(cell_type)

        # Позиционируем меню так, чтобы оно не выходило за пределы axes
        mx = event.xdata
        my = event.ydata
        menu_w = 4
        option_h = 1
        total_h = option_h * len(interaction_options)
        # # Подвинем меню влево/вверх при необходимости, чтобы не выходило правее/ниже
        if mx + menu_w > self.map.width:
            mx = self.map.width - menu_w - 0.1
        if my + total_h > self.map.height:
            my = self.map.height - total_h - 0.1
        if mx < 0.1:
            mx = 0.1
        if my < 0.1:
            my = 0.1

        # Фон меню (с закруглением)
        bg = FancyBboxPatch(
            (mx, my - 0.5), menu_w, total_h,
            boxstyle="round,pad=0.02", linewidth=1,
            facecolor="white", edgecolor="black", zorder=10)
        self.ax.add_patch(bg)
        self.menu_drawables.append(bg)

        # Добавим опции как тексты
        for i, (label, callback) in enumerate(interaction_options):
            ty = my + (len(interaction_options) - 1 - i) * option_h + option_h * 0.15
            txt = self.ax.text(
                mx + menu_w * 0.5, ty, label, ha='center', va='center',
                fontsize=9, zorder=11
            )

            self.menu_drawables.append(txt)
            self.menu_texts.append(txt)
            # Сохраняем обёртку callback, передаём cell как параметр
            self.menu_callbacks.append(lambda cb=callback, cell=cell: cb(cell))
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
            # если клик был внутри фона, но не по тексту — закроем меню
            for a in self.menu_drawables:
                if isinstance(a, FancyBboxPatch):
                    if a.get_bbox().contains(event.xdata, event.ydata):
                        self.clear_menu()
                        return
        cell = Point(int(event.xdata), int(event.ydata))
        cell_value = self.map.get(cell)
        cell_type = CELL_TYPE(cell_value)
        # print(int(event.xdata), int(event.ydata), cell_type.name)
        if not self.menu_exists:
            self.show_menu_at(event, cell, cell_type)
        # if event.xdata and event.ydata:
        #     COMMAND_QUEUE.put(("click", (event.xdata, event.ydata)))


def render_thread(map: DungeonMap):
    visualization = Visualization(map)
    visualization.init_map()
    visualization.loop()
