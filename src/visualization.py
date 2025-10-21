import matplotlib.pyplot as plt
from src.base import Point
from src.constants import CELL_TYPE, MapEntities, MapEntity
from matplotlib.patches import FancyBboxPatch


import matplotlib

from src.entities.interaction import get_interaction_options


matplotlib.use('tkagg')


def render_thread(map):
    menu_artists = []  # все артисты меню (фон + тексты)
    menu_texts = []  # текстовые артисты (для hit-testing через .contains(event))
    menu_callbacks = []  # соответствующие callback'и для текстов

    menu_exists = False

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_xlim(0, map._width)
    ax.set_ylim(0, map._height)
    ax.set_aspect('equal')
    ax.invert_yaxis()
    ax.axis('off')
    rects = {}
    texts = {}

    def init_map():
        # создаём сетку один раз
        for y in range(map._height):
            for x in range(map._width):
                rect = plt.Rectangle((x, y), 1, 1, facecolor='wheat', edgecolor='gray')
                ax.add_patch(rect)
                rects[(x, y)] = rect
                t = ax.text(x + 0.5, y + 0.5, "", ha='center', va='center', fontsize=6, color='black')
                texts[(x, y)] = t

    def clear_menu():
        nonlocal menu_exists, menu_artists, menu_texts, menu_callbacks
        """Безопасно удаляет все элементы меню (если они ещё существуют)."""
        for a in menu_artists:
            try:
                a.remove()
            except Exception:
                # если по какой-то причине remove() не поддерживается или артист уже удалён — пропускаем
                pass
        menu_artists = []
        menu_texts = []
        menu_callbacks = []
        fig.canvas.draw_idle()


    def show_menu_at(event, cell, cell_type):
        """
        Показывает компактное меню рядом с координатами event.xdata/event.ydata.
        Для hit-testing используется метод artist.contains(event).
        """
        clear_menu()
        # Формируем список опций в зависимости от типа клетки
        interaction_options = get_interaction_options(cell_type)

        # Позиционируем меню так, чтобы оно не выходило за пределы axes
        mx = event.xdata
        my = event.ydata
        menu_w = 4
        option_h = 1
        total_h = option_h * len(interaction_options)
        # # Подвинем меню влево/вверх при необходимости, чтобы не выходило правее/ниже
        if mx + menu_w > map._width:
            mx = map._width - menu_w - 0.1
        if my + total_h > map._height:
            my = map._height - total_h - 0.1
        if mx < 0.1:
            mx = 0.1
        if my < 0.1:
            my = 0.1

        # Фон меню (с закруглением)
        bg = FancyBboxPatch(
            (mx, my - 0.5), menu_w, total_h,
            boxstyle="round,pad=0.02", linewidth=1,
            facecolor="white", edgecolor="black", zorder=10)
        ax.add_patch(bg)
        menu_artists.append(bg)

        # Добавим опции как тексты
        for i, (label, callback) in enumerate(interaction_options):
            ty = my + (len(interaction_options) - 1 - i) * option_h + option_h * 0.15
            txt = ax.text(
                mx + menu_w * 0.5, ty, label, ha='center', va='center',
                fontsize=9, zorder=11
            )

            menu_artists.append(txt)
            menu_texts.append(txt)
            # Сохраняем обёртку callback, передаём cell как параметр
            menu_callbacks.append(lambda cb=callback, cell=cell: cb(cell))

        fig.canvas.draw()  # нужно, чтобы artist.contains(event) корректно работал

    def onclick(event):
        # Сначала проверим — клик по пункту меню?
        if menu_texts:
            for i, txt in enumerate(menu_texts):
                contains, _ = txt.contains(event)
                if contains:
                    # вызываем соответствующий callback
                    menu_callbacks[i]()
                    clear_menu()
                    return
            # если клик был внутри фона, но не по тексту — закроем меню
            for a in menu_artists:
                if isinstance(a, FancyBboxPatch):
                    if a.get_bbox().contains(event.xdata, event.ydata):
                        clear_menu()
                        return
        cell = Point(int(event.xdata), int(event.ydata))
        cell_value = map.get(cell)
        cell_type = CELL_TYPE(cell_value)
        # print(int(event.xdata), int(event.ydata), cell_type.name)
        if not menu_exists:
            show_menu_at(event, cell, cell_type)
        # if event.xdata and event.ydata:
        #     COMMAND_QUEUE.put(("click", (event.xdata, event.ydata)))

    fig.canvas.mpl_connect("button_press_event", onclick)
    plt.show(block=False)
    init_map()
    while True:
        for x in range(map._width):
            for y in range(map._height):
                map_entity = MapEntities.get(map.get(Point(x, y)), MapEntity())
                rect = rects[(x, y)]
                text = texts[(x, y)]
                rect.set_facecolor(map_entity.color)
                text.set_text(map_entity.text)
                # показываем номер шага, если клетка достижима и не старт
                # if (x, y) in reachable and (x, y) != start:
                #     ax.text(x + 0.5, y + 0.5, str(reachable[(x, y)]),
                #             ha='center', va='center', fontsize=8, color='black')
        fig.canvas.draw_idle()
        plt.pause(0.05)
