import asyncio
import typing
from typing import Literal

from pydantic import BaseModel

from src.action import Action, ActionResult, ActionType
from src.base import Point
from src.combat import AttackKind, HAND_LABELS_RU
from src.entities.base import Actor, OverwatchState, Weapon
from src.entities.player import Player

if typing.TYPE_CHECKING:
    from src.game import Game


class WeaponActionContext(BaseModel):
    actor: Actor
    action: Action
    weapon: Weapon


class AttackContext(WeaponActionContext):
    target: Actor
    distance: float


class ActionHandler:
    def __init__(self, game: "Game"):
        self.game = game

    @staticmethod
    def _reject(action: Action, detail: str) -> ActionResult:
        return ActionResult(performed=False, action=action, detail=detail)

    def _prepare_weapon_action(
        self,
        actor: Actor,
        action: Action,
        purpose: str,
        required_weapon_type: Literal["melee", "ranged"] | None = None,
    ) -> WeaponActionContext | ActionResult:
        if action.params is None or not hasattr(action.params, "weapon_id"):
            return self._reject(
                action,
                f"{actor.name}, для {purpose} не указано оружие",
            )
        weapon = actor.get_weapon(action.params.weapon_id)
        if weapon is None:
            return self._reject(
                action,
                f"{actor.name}, в инвентаре нет указанного оружия для {purpose}",
            )
        if required_weapon_type is not None and weapon.type != required_weapon_type:
            return self._reject(
                action,
                f"{actor.name}, для {purpose} требуется дальнобойное оружие",
            )
        if not actor.is_weapon_usable(weapon):
            return self._reject(
                action,
                f"{actor.name}, {HAND_LABELS_RU[weapon.hand]} уничтожена — оружие «{weapon.name}» недоступно",
            )
        if actor.current_action_points < weapon.cost_ap:
            return self._reject(
                action,
                f"{actor.name}, недостаточно очков действия для {purpose}",
            )
        return WeaponActionContext(actor=actor, action=action, weapon=weapon)

    def _prepare_attack(
        self, weapon_context: WeaponActionContext
    ) -> AttackContext | ActionResult:
        actor = weapon_context.actor
        action = weapon_context.action
        weapon = weapon_context.weapon
        target = self.game.get_actor_at(action.cell)
        if target is None:
            return self._reject(
                action,
                f"{actor.name}, в клетке {action.cell} нет цели для атаки",
            )
        if not self.game.is_hostile(actor, target):
            return self._reject(
                action,
                f"{actor.name}, нельзя атаковать своего сокомандника",
            )

        if weapon.type == "ranged":
            distance = Point.distance_euklid(actor.position, action.cell)
            if distance > weapon.range:
                return self._reject(
                    action,
                    f"Слишком далеко для атаки ({distance:.2f} / {weapon.range})",
                )
            if not self.game.arena.map.can_shoot(actor, weapon, action.cell):
                return self._reject(
                    action,
                    f"{actor.name}, клетку {action.cell} нельзя атаковать — цель не видна или есть преграды",
                )
        else:
            # Для melee любая из восьми соседних клеток равноудалена.
            distance = Point.distance_chebyshev(actor.position, action.cell)
            if distance > weapon.range:
                return self._reject(
                    action,
                    f"Слишком далеко для атаки ({distance} / {weapon.range})",
                )
        return AttackContext(
            actor=actor,
            action=action,
            weapon=weapon,
            target=target,
            distance=distance,
        )

    async def perform_actor_action(self, actor: Actor, action: Action) -> ActionResult:
        if str(actor.id) != action.actor_id:
            return self._reject(
                action,
                f"Действие отправлено не от имени актора {actor.name}",
            )
        if self.game.turn.current_actor != actor:
            current_actor_name = (
                self.game.turn.current_actor.name
                if self.game.turn.current_actor is not None
                else "никого"
            )
            return self._reject(
                action,
                f"{actor.name} попытался походить во время хода {current_actor_name}",
            )
        # Enemy и Player приводятся к Actor
        match action.type:
            case ActionType.END_TURN:
                return await self.__perform_action_end_turn(actor=actor, action=action)
            case ActionType.MOVE:
                return await self.__perform_action_move(actor=actor, action=action)
            case ActionType.ATTACK:
                return await self.__perform_action_attack(actor=actor, action=action)
            case ActionType.OVERWATCH:
                return await self.__perform_action_overwatch(actor=actor, action=action)
            case _:
                return self._reject(
                    action,
                    f"Действие {action.type.name} пока не поддерживается",
                )

    async def __perform_action_end_turn(
        self, actor: Actor, action: Action
    ) -> ActionResult:
        return ActionResult(
            action=action,
            detail=f"{actor.name} завершает ход",
        )

    async def __perform_action_overwatch(
        self, actor: Actor, action: Action
    ) -> ActionResult:
        if actor.overwatch is not None:
            return self._reject(
                action,
                f"{actor.name} уже в режиме огневого дозора",
            )
        prepared = self._prepare_weapon_action(
            actor=actor,
            action=action,
            purpose="огневого дозора",
            required_weapon_type="ranged",
        )
        if isinstance(prepared, ActionResult):
            return prepared
        weapon = prepared.weapon
        actor.overwatch = OverwatchState(weapon_id=weapon.id)
        return ActionResult(
            action=action,
            action_cost=weapon.cost_ap,
            detail=f"{actor.name} переходит в режим огневого дозора ({weapon.name})",
        )

    async def __perform_action_move(self, actor: Actor, action: Action) -> ActionResult:
        if action.cell not in self.game.turn.available_moves:
            return self._reject(
                action,
                f"{actor.name}, нельзя переместиться в {action.cell}",
            )
        if not self.game.arena.map.is_free(action.cell):
            return self._reject(
                action,
                f"{actor.name}, клетка {action.cell} занята, нельзя в нее переместиться",
            )
        path = self.game.arena.map.bfs_path(action.cell, actor.position)
        if not path:
            return self._reject(
                action,
                f"{actor.name}, не получилось построить путь до точки {action.cell}",
            )
        total_cost = len(path) - 1
        assert total_cost > 0
        if actor.current_action_points < total_cost:
            return self._reject(
                action,
                f"{actor.name}, недостаточно очков действия для перемещения в {action.cell}!",
            )
        # шагаем по пути по одной клетке, проверяя огневой дозор
        step_path = list(reversed(path))[1:]  # путь от текущей позиции к цели
        for i, step_cell in enumerate(step_path):
            self.game.move_actor(actor, step_cell)
            self.game.version += 1
            await self.game._notify_state_change()
            await asyncio.sleep(0.1)
            overwatch_fired = await self.game.check_overwatch_triggers(actor)
            if overwatch_fired and actor.is_dead():
                return ActionResult(
                    action=action,
                    action_cost=i + 1,
                    speed_spent=i + 1,
                    detail=f"{actor.name} убит огневым дозором при перемещении!",
                )
        return ActionResult(
            action=action,
            action_cost=total_cost,
            speed_spent=total_cost,
            detail=f"{actor.name} перемещается в клетку {action.cell}",
        )

    async def __perform_action_attack(
        self, actor: Actor, action: Action
    ) -> ActionResult:
        prepared_weapon = self._prepare_weapon_action(
            actor=actor,
            action=action,
            purpose="атаки",
        )
        if isinstance(prepared_weapon, ActionResult):
            return prepared_weapon
        prepared_attack = self._prepare_attack(prepared_weapon)
        if isinstance(prepared_attack, ActionResult):
            return prepared_attack

        weapon = prepared_attack.weapon
        target = prepared_attack.target

        outcome = self.game.combat.resolve_attack(
            attacker=actor,
            target=target,
            weapon=weapon,
            distance=prepared_attack.distance,
            kind=AttackKind.REGULAR,
        )
        if not outcome.hit:
            return ActionResult(
                performed=True,
                action=action,
                action_cost=outcome.action_cost,
                detail=f"{outcome.skill_prefix}{actor.name} промахивается из оружия {weapon.name} по {target.name}",
            )

        death_detail = ""
        if outcome.killed:
            death_detail = (
                f" Мех {target.name} уничтожен!"
                if isinstance(target, Player)
                else f" {target.name} погиб!"
            )
        return ActionResult(
            action=action,
            action_cost=outcome.action_cost,
            detail=f"{outcome.skill_prefix}{actor.name} атакует {target.name} ({weapon.name}) и наносит {outcome.damage} урона.{outcome.part_detail}{death_detail}",  # noqa
        )
