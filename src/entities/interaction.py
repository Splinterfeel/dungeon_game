from src.base import Point
from src.constants import CELL_TYPE


class InteractionHandlers:
    def get_interaction_options(cell_type: CELL_TYPE):
        default_options =  [("Осмотреть", InteractionHandlers._inspect)]
        match cell_type:
            case CELL_TYPE.FLOOR:
                return [("Идти сюда", InteractionHandlers._go_to)] + default_options
            case CELL_TYPE.EXIT:
                return [("Покинуть", InteractionHandlers._interact_with_exit)] + default_options
            case CELL_TYPE.ENEMY:
                return [("Атаковать", InteractionHandlers._interact_with_enemy)] + default_options
            case CELL_TYPE.CHEST:
                return [("Открыть сундук", InteractionHandlers._open_chest),] + default_options
            case _:
                return default_options

    def _go_to(point: Point):
        print(f"🚶 Идем в клетку {point}")

    def _inspect(point: Point):
        print(f"🔍 Осматриваем клетку {point}")

    def _open_chest(point: Point):
        print(f"🗝️  Открываем сундук в {point}")

    def _interact_with_enemy(point: Point):
        print(f"Атакуем врага в {point}")

    def _interact_with_exit(point: Point):
        print(f"Покидаем подземелье в {point}")


