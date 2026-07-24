import asyncio
import typing
import random

from src.action import (
    Action,
    ActionResult,
    ActionType,
    AttackActionParams,
    OverwatchActionParams,
)
from src.base import Point
from src.constants import CELL_TYPE
from src.entities.base import Actor, OverwatchState, Weapon
from src.entities.player import Player

if typing.TYPE_CHECKING:
    from src.game import Game

# человекочитаемые названия сторон рук для боевых сообщений (ROADMAP.md Этап 2 п.3)
HAND_LABELS_RU = {"left": "левая рука", "right": "правая рука"}


class ActionHandler:
    def __init__(self, game: "Game"):
        self.game = game

    def __try_proc_skill(
        self, actor: Actor, skill_key: str, proc_actor_ids: set[str] | None = None
    ) -> bool:
        if proc_actor_ids is not None and str(actor.id) in proc_actor_ids:
            return False
        if not isinstance(actor, Player):
            return False
        skill = next((s for s in actor.skills if s.skill_key == skill_key), None)
        if skill is None:
            return False
        if random.random() >= skill.proc_chance:
            return False
        if proc_actor_ids is not None:
            proc_actor_ids.add(str(actor.id))
        return True

    def __apply_locational_damage(self, player: Player, damage: int) -> str:
        "Урон случайной живой части меха игрока + пересчёт живых статов; возвращает суффикс для detail"
        part = player.mech.apply_random_part_damage(damage)
        if part is None:
            return ""  # все части уже уничтожены
        player.mech.recompute_live_stats(player.stats)
        if part.destroyed:
            # для рук указываем сторону (левая/правая), т.к. они одного типа
            side = player.mech.hand_side_of(part)
            location = HAND_LABELS_RU[side] if side else part.slot.value
            return f" Деталь «{part.name}» ({location}) уничтожена!"
        return ""

    async def perform_actor_action(self, actor: Actor, action: Action) -> ActionResult:
        if self.game.turn.current_actor != actor:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name} попытался походить во время хода {self.game.turn.current_actor.name}",
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
            case ActionType.INSPECT:
                print("INSPECTING", action.cell)
                return ActionResult(action=action)
            case _:
                print("Performing unknown action", action)
                return ActionResult(action=action)

    async def __perform_action_end_turn(
        self, actor: Actor, action: Action
    ) -> ActionResult:
        if str(self.game.turn.current_actor.id) != action.actor_id:
            print(self.game.turn.current_actor.id)
            print(action.actor_id)
            print(
                detail=f"{actor.name} попытался закончить ход во время хода {self.game.turn.current_actor.name}",
            )
        return ActionResult(
            action=action,
            action_cost=30000,  # TODO пока просто завершаем ход немыслимым кол-вом AP
            detail=f"{actor.name} завершает ход",
        )

    async def __perform_action_overwatch(
        self, actor: Actor, action: Action
    ) -> ActionResult:
        if actor.overwatch is not None:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name} уже в режиме огневого дозора",
            )
        params: OverwatchActionParams = action.params
        weapon: Weapon | None = next(
            (w for w in actor.inventory.weapons if w.id == params.weapon_id),
            None,
        )
        if weapon is None:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, в инвентаре нет указанного оружия для огневого дозора",
            )
        if weapon.type != "ranged":
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, огневой дозор доступен только с дальнобойным оружием",
            )
        # оружие в уничтоженной руке недоступно и для огневого дозора
        if (
            isinstance(actor, Player)
            and weapon.hand
            and actor.mech.arm_for(weapon.hand).destroyed
        ):
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, {HAND_LABELS_RU[weapon.hand]} уничтожена — оружие «{weapon.name}» недоступно",
            )
        if actor.current_action_points < weapon.cost_ap:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, нет очков действия для огневого дозора",
            )
        actor.overwatch = OverwatchState(weapon_id=weapon.id)
        return ActionResult(
            action=action,
            action_cost=weapon.cost_ap,
            detail=f"{actor.name} переходит в режим огневого дозора ({weapon.name})",
        )

    async def __perform_action_move(self, actor: Actor, action: Action) -> ActionResult:
        if action.cell not in self.game.turn.available_moves:
            print(f"Can't move player {actor} to cell {action.cell}")
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, нельзя переместиться в {action.cell}",
            )
        if not self.game.arena.map.is_free(action.cell):
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, клетка {action.cell} занята, нельзя в нее переместиться",  # noqa
            )
        path = self.game.arena.map.bfs_path(
            action.cell, self.game.turn.current_actor.position
        )
        if not path:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, не получилось построить путь до точки {action.cell}",
            )
        total_cost = len(path) - 1
        assert total_cost > 0
        if self.game.turn.current_actor.current_action_points < total_cost:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, Недостаточно очков действия для перемещения в {action.cell}!",
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
        action_ap_cost = 0
        actor_cell_type = self.game.arena.map.get(self.game.turn.current_actor.position)
        action_cell_type = self.game.arena.map.get(action.cell)
        attack_params: AttackActionParams = action.params
        try:
            weapon = next(
                w for w in actor.inventory.weapons if w.id == attack_params.weapon_id
            )
        except StopIteration:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, в инвентаре нет указанного оружия для атаки: {attack_params.weapon_id}",
            )
        # оружие в уничтоженной руке недоступно (ROADMAP.md Этап 2 п.3-4);
        # у врагов меха/рук нет (weapon.hand=None) - проверка их не касается
        if (
            isinstance(actor, Player)
            and weapon.hand
            and actor.mech.arm_for(weapon.hand).destroyed
        ):
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, {HAND_LABELS_RU[weapon.hand]} уничтожена — оружие «{weapon.name}» недоступно",
            )
        action_ap_cost = weapon.cost_ap
        current_dist = Point.distance_chebyshev(actor.position, action.cell)
        attack_accuracy_bonus = 0
        damage_bonus = 0
        proc_actor_ids: set[str] = set()
        skill_messages: list[str] = []
        if weapon.type == "ranged" and self.__try_proc_skill(
            actor, "accurate_shot", proc_actor_ids
        ):
            attack_accuracy_bonus += 15
            skill_messages.append("срабатывает навык «Точный выстрел»")
        if weapon.type == "melee" and self.__try_proc_skill(
            actor, "heavy_strike", proc_actor_ids
        ):
            damage_bonus += 3
            skill_messages.append("срабатывает навык «Усиленный удар»")
        free_action_proc = self.__try_proc_skill(
            actor, "combat_impulse", proc_actor_ids
        )
        if free_action_proc:
            action_ap_cost = 0
            skill_messages.append("срабатывает навык «Боевой импульс»")
        damage = weapon.roll_damage()
        if weapon.type == "melee":
            damage += actor.stats.melee_power
        damage += damage_bonus
        current_dist = Point.distance_chebyshev(actor.position, action.cell)
        # проверка линии видимости
        if weapon.range > 1:
            if not self.game.arena.map.can_shoot(actor, weapon, action.cell):
                return ActionResult(
                    performed=False,
                    action=action,
                    detail=f"{actor.name}, клетка {action.cell} нельзя атаковать - слишком далеко или есть преграды",  # noqa
                )
        if self.game.turn.current_actor.current_action_points < action_ap_cost:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, недостаточно очков действия для выбранной атаки",
            )
        if current_dist > weapon.range:
            print(
                f"Attempt to attack {action.cell}, but it's too far: {current_dist}"  # noqa
            )  # noqa
            return ActionResult(
                performed=False,
                action=action,
                detail=f"Слишком далеко для атаки ({current_dist} / {weapon.range})",
            )
        attack_stats = actor.stats.model_copy(
            update={"accuracy": actor.stats.accuracy + attack_accuracy_bonus}
        )
        skill_prefix = ""
        if skill_messages:
            skill_prefix = f"{', '.join(skill_messages)}; "
        attack_hit = weapon.check_hit(actor_stats=attack_stats, distance=current_dist)
        if (
            actor_cell_type == CELL_TYPE.ENEMY.value
            and action_cell_type == CELL_TYPE.PLAYER.value
        ):
            player = next(x for x in self.game.players if x.position == action.cell)
            if attack_hit and self.__try_proc_skill(player, "dodge", proc_actor_ids):
                attack_hit = False
                skill_prefix += f"срабатывает навык «Уклонение» у {player.name}; "
            if not attack_hit:
                return ActionResult(
                    performed=True,
                    action=action,
                    action_cost=action_ap_cost,
                    detail=f"{skill_prefix}{actor.name} промахивается из оружия {weapon.name} по {player.name}",
                )
            player.apply_damage(damage)
            part_detail = self.__apply_locational_damage(player, damage)
            death_detail = ""
            if player.is_dead():
                self.game.arena.remove_dead_player(player)
                self.game.players.remove(player)
                death_detail = f" Мех {player.name} уничтожен!"
            return ActionResult(
                action=action,
                action_cost=action_ap_cost,
                detail=f"{skill_prefix}{actor.name} атакует {player.name} ({weapon.name}) и наносит {damage} урона.{part_detail}{death_detail}",
            )
        elif (
            actor_cell_type == CELL_TYPE.PLAYER.value
            and action_cell_type == CELL_TYPE.ENEMY.value
        ):
            enemy = next(
                x for x in self.game.arena.enemies if x.position == action.cell
            )
            if not attack_hit:
                return ActionResult(
                    performed=True,
                    action=action,
                    action_cost=action_ap_cost,
                    detail=f"{skill_prefix}{actor.name} промахивается из оружия {weapon.name} по {enemy.name}",
                )
            enemy.apply_damage(damage)
            death_detail = ""
            if enemy.is_dead():
                self.game.arena.remove_dead_enemy(enemy=enemy)
                death_detail = f" {enemy.name} погиб!"
            return ActionResult(
                action=action,
                action_cost=action_ap_cost,
                detail=f"{skill_prefix}{actor.name} атакует {enemy.name} ({weapon.name}) и наносит {damage} урона{death_detail}",
            )
        elif (
            actor_cell_type == CELL_TYPE.PLAYER.value
            and action_cell_type == CELL_TYPE.PLAYER.value
        ):
            # игрок атакует другого игрока
            player_attacking: Player = next(
                x for x in self.game.players if x.position == actor.position
            )
            player_attacked: Player = next(
                x for x in self.game.players if x.position == action.cell
            )
            if player_attacking.team == player_attacked.team:
                return ActionResult(
                    performed=False,
                    action=action,
                    detail=f"{actor.name}, нельзя атаковать своего сокомандника",
                )
            if attack_hit and self.__try_proc_skill(
                player_attacked, "dodge", proc_actor_ids
            ):
                attack_hit = False
                skill_prefix += (
                    f"срабатывает навык «Уклонение» у {player_attacked.name}; "
                )
            if not attack_hit:
                return ActionResult(
                    performed=True,
                    action=action,
                    action_cost=action_ap_cost,
                    detail=f"{skill_prefix}{player_attacking.name} промахивается из оружия {weapon.name} по {player_attacked.name}",
                )
            player_attacked.apply_damage(damage)
            part_detail = self.__apply_locational_damage(player_attacked, damage)
            death_detail = ""
            if player_attacked.is_dead():
                self.game.arena.remove_dead_player(player_attacked)
                self.game.players.remove(player_attacked)
                death_detail = f" Мех {player_attacked.name} уничтожен!"
            return ActionResult(
                action=action,
                action_cost=action_ap_cost,
                detail=f"{skill_prefix}{player_attacking.name} атакует {player_attacked.name} ({weapon.name}) и наносит {damage} урона.{part_detail}{death_detail}",  # noqa
            )
        else:
            print(
                f"Unknown actor_type / cell_type for attack: {actor_cell_type} / {action_cell_type}"
            )
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, нельзя атаковать клетку {action.cell}",
            )
