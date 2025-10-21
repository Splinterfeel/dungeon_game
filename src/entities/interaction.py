from src.base import Point
from src.constants import CELL_TYPE


class InteractionHandlers:
    def go_to(cell):
        print(f"🚶 Идем в клетку {cell}")

    def inspect(cell):
        print(f"🔍 Осматриваем клетку {cell}")

    def open_chest(cell):
        print(f"🗝️  Открываем сундук в {cell}")

    def interact_with_enemy(cell):
        print(f"Атакуем врага в {cell}")

    def interact_with_exit(cell):
        print(f"Покидаем подземелье в {cell}")


def get_interaction_options(cell_type: CELL_TYPE):
    match cell_type:
        case CELL_TYPE.FLOOR:
            return [("Идти сюда", InteractionHandlers.go_to), ("Осмотреть", InteractionHandlers.inspect)]
        case CELL_TYPE.EXIT:
            return [("Покинуть", InteractionHandlers.interact_with_exit), ("Осмотреть", InteractionHandlers.inspect)]
        case CELL_TYPE.ENEMY:
            return [("Атаковать", InteractionHandlers.interact_with_enemy), ("Осмотреть", InteractionHandlers.inspect)]
        case CELL_TYPE.CHEST:
            return [("Открыть сундук", InteractionHandlers.open_chest), ("Осмотреть", InteractionHandlers.inspect)]
        case _:
            return [("Осмотреть", InteractionHandlers.inspect)]
