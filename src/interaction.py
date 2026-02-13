from src.action import Action, ActionType
from src.base import Queues, Point
from src.constants import CELL_TYPE, Attack
from src.entities.base import Actor


class InteractionHandlers:
    def get_interaction_options(actor: Actor, cell: Point, cell_type: CELL_TYPE):
        # (текст, коллбэк, доп.параметры (словарь)
        if not actor:
            return []
        default_options = [
            (f"Осмотреть [{cell.x}, {cell.y}]", InteractionHandlers._inspect, None),
            ("Завершить ход", InteractionHandlers._end_turn, None),
        ]
        match cell_type:
            case CELL_TYPE.FLOOR:
                return [
                    ("Идти сюда", InteractionHandlers._go_to, None)
                ] + default_options
            case CELL_TYPE.EXIT:
                return [
                    ("Покинуть", InteractionHandlers._interact_with_exit, None)
                ] + default_options
            case CELL_TYPE.ENEMY:
                return [
                    ("Атака", InteractionHandlers._attack, Attack.SIMPLE.to_dict()),
                    (
                        "Сильная атака",
                        InteractionHandlers._attack,
                        Attack.HEAVY.to_dict(),
                    ),
                ] + default_options
            case CELL_TYPE.CHEST:
                return [
                    ("Открыть сундук", InteractionHandlers._open_chest, None),
                ] + default_options
            case _:
                return default_options

    def _end_turn(actor: Actor, point: Point, params: dict = None):
        Queues.COMMAND_QUEUE.put(
            Action(actor=actor, type=ActionType.END_TURN, cell=actor.position)
        )

    def _go_to(actor: Actor, point: Point, params: dict = None):
        Queues.COMMAND_QUEUE.put(Action(actor=actor, type=ActionType.MOVE, cell=point))

    def _inspect(actor: Actor, point: Point, params: dict = None):
        Queues.COMMAND_QUEUE.put(
            Action(actor=actor, type=ActionType.INSPECT, cell=point)
        )

    def _open_chest(actor: Actor, point: Point, params: dict = None):
        Queues.COMMAND_QUEUE.put(
            Action(actor=actor, type=ActionType.OPEN_CHEST, cell=point)
        )

    def _attack(actor: Actor, point: Point, params: dict = None):
        Queues.COMMAND_QUEUE.put(
            Action(actor=actor, type=ActionType.ATTACK, cell=point, params=params)
        )

    def _interact_with_exit(actor: Actor, point: Point, params: dict = None):
        Queues.COMMAND_QUEUE.put(Action(actor=actor, type=ActionType.EXIT, cell=point))
