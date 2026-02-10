from src.action import Action, ActionType
from src.base import Queues, Point
from src.constants import CELL_TYPE, Attack


class InteractionHandlers:
    def get_interaction_options(cell: Point, cell_type: CELL_TYPE):
        # (текст, коллбэк, доп.параметры (словарь)
        default_options = [
            (f"Осмотреть [{cell.x}, {cell.y}]", InteractionHandlers._inspect, None)
        ]
        match cell_type:
            case CELL_TYPE.FLOOR:
                return [("Идти сюда", InteractionHandlers._go_to, None)] + default_options
            case CELL_TYPE.EXIT:
                return [
                    ("Покинуть", InteractionHandlers._interact_with_exit, None)
                ] + default_options
            case CELL_TYPE.ENEMY:
                return [
                    ("Атака", InteractionHandlers._attack, Attack.SIMPLE.to_dict()),
                    ("Сильная атака", InteractionHandlers._attack, Attack.HEAVY.to_dict()),
                ] + default_options
            case CELL_TYPE.CHEST:
                return [
                    ("Открыть сундук", InteractionHandlers._open_chest, None),
                ] + default_options
            case _:
                return default_options

    def _go_to(point: Point, params: dict=None):
        Queues.COMMAND_QUEUE.put(
            Action(type=ActionType.MOVE, cell=point, ends_turn=True)
        )

    def _inspect(point: Point, params: dict=None):
        Queues.COMMAND_QUEUE.put(
            Action(type=ActionType.INSPECT, cell=point, ends_turn=False)
        )

    def _open_chest(point: Point, params: dict=None):
        Queues.COMMAND_QUEUE.put(
            Action(type=ActionType.OPEN_CHEST, cell=point, ends_turn=False)
        )

    def _attack(point: Point, params: dict=None):
        Queues.COMMAND_QUEUE.put(
            Action(type=ActionType.ATTACK, cell=point, ends_turn=True, params=params)
        )

    def _interact_with_exit(point: Point, params: dict=None):
        Queues.COMMAND_QUEUE.put(
            Action(type=ActionType.EXIT, cell=point, ends_turn=True)
        )
