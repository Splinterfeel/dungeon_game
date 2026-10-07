import copy
import random
from uuid import UUID, uuid4
from typing import Optional, List

from src.action_handler import ActionHandler
from dto.event import GameEvent
from src.action import Action, ActionResult, ActionType, ActorMovement
from src.entities.base import Actor, Weapon
from src.base import Point
from src.entities.player import Player
from src.entities.enemy import Enemy
from src.arena import Arena
from src.constants import CELL_TYPE
from src.combat import ActorAttack, AttackKind, AttackOutcome, CombatResolver
from src.turn import GamePhase, Turn
from src.game_observer import GameObserver

ACTIONS_ENDS_TURN = {ActionType.END_TURN, ActionType.OVERWATCH}


class Game:
    def __init__(
        self,
        arena: Arena,
        players: List[Player],
        enemies: List[Enemy],
        turn: Turn = None,
        version: int = 0,
    ):
        self._observer: Optional[GameObserver] = None
        self.id = uuid4()
        self.ended = False
        # Награды начисляет Lobby, но флаг живёт у конкретного матча, чтобы
        # повторная проверка конца игры не выдала дроп второй раз.
        self.rewards_granted = False
        self.winner: Optional[int] = (
            None  # 1/2 — команда-победитель, None — ничья/матч не завершён
        )
        self.version = version
        self.arena = arena
        self.players = players
        self.enemies = enemies
        for enemy in self.enemies:
            self.arena.map.set(enemy.position, CELL_TYPE.ENEMY.value)
        if turn is not None:
            self.turn = turn
        else:
            self.turn = Turn()
        if not self.turn.player_actor_order:
            self.turn.player_actor_order = self._build_player_actor_order()
        self.combat = CombatResolver(game=self)
        self.action_handler = ActionHandler(game=self)

    def _build_player_actor_order(self) -> list[str]:
        """Стабильная инициатива A1 → B1 → A2 → B2 без смены стороны."""
        teams = {
            1: [player for player in self.players if player.team == 1],
            2: [player for player in self.players if player.team == 2],
        }
        order: list[str] = []
        for index in range(max(len(teams[1]), len(teams[2]))):
            for team in (1, 2):
                if index < len(teams[team]):
                    order.append(str(teams[team][index].id))
        return order

    def set_observer(self, observer: GameObserver) -> None:
        """Register an observer for game events"""
        self._observer = observer

    async def _notify_event(
        self, event: GameEvent, receiver_player_ids: Optional[List[str]] = None
    ) -> None:
        """Notify observer of game event"""
        if self._observer:
            await self._observer.on_game_event(event, receiver_player_ids)

    async def _notify_state_change(self) -> None:
        """Notify observer of state change"""
        if self._observer:
            await self._observer.on_state_change()

    async def _notify_actor_moved(self, movements: dict[int, ActorMovement]) -> None:
        if self._observer:
            await self._observer.on_actor_moved(movements)

    def actor_visible_to_team(self, actor: Actor, team: int) -> bool:
        if isinstance(actor, Player) and actor.team == team:
            return True
        return any(
            player.team == team
            and not player.is_dead()
            and self.arena.map.can_see(player, actor)
            for player in self.players
        )

    async def resolve_and_publish_attack(
        self,
        attacker: Actor,
        target: Actor,
        weapon: Weapon,
        distance: float,
        kind: AttackKind,
        movement_action_id: UUID | None = None,
    ) -> AttackOutcome:
        # Видимость и позиции фиксируем до урона: цель может стать последним
        # погибшим наблюдателем команды, но её попадание всё равно видно.
        attack_id = uuid4()
        attacks: dict[int, ActorAttack] = {}
        for team in (1, 2):
            attacker_visible = self.actor_visible_to_team(attacker, team)
            target_visible = self.actor_visible_to_team(target, team)
            if not attacker_visible and not target_visible:
                continue
            attacks[team] = ActorAttack(
                attack_id=attack_id,
                attacker_id=str(attacker.id) if attacker_visible else None,
                target_id=str(target.id) if target_visible else None,
                from_cell=attacker.position.model_copy() if attacker_visible else None,
                to_cell=target.position.model_copy() if target_visible else None,
                weapon_type=weapon.type,
                kind=kind,
                movement_action_id=movement_action_id,
            )
        outcome = self.combat.resolve_attack(
            attacker=attacker,
            target=target,
            weapon=weapon,
            distance=distance,
            kind=kind,
        )
        for attack in attacks.values():
            attack.hit = outcome.hit
            # Прок скрытого меха не раскрывает его имя/навыки другой команде.
            attack.skill_procs = [
                proc
                for proc in outcome.skill_procs
                if proc.actor_id in (attack.attacker_id, attack.target_id)
            ]
            if attack.to_cell is not None:
                attack.damage = outcome.damage
                attack.target_killed = outcome.target_killed
        if self._observer and attacks:
            await self._observer.on_actor_attacked(attacks)
        return outcome

    async def launch(self):
        self._init_players()

        # ставим ход первому игроку
        self.turn.next()
        await self.pass_turn_to_next_actor()

    async def prepare_actor_turn(self, actor: Actor):
        await self._notify_event(GameEvent(message=f"Ход {actor.name}"))
        actor.current_action_points = actor.stats.action_points
        actor.overwatch = None
        actor.current_speed_spent = 0
        self.turn.available_moves = self.arena.map.get_available_moves(actor)
        self.turn.set_current_actor(actor)

    def get_actors(self) -> list[Actor]:
        return [*self.players, *self.enemies]

    def get_actor_at(self, cell: Point) -> Actor | None:
        return next(
            (actor for actor in self.get_actors() if actor.position == cell), None
        )

    def is_hostile(self, watcher: Actor, target: Actor) -> bool:
        if isinstance(watcher, Enemy) and isinstance(target, Player):
            return True
        if isinstance(watcher, Player) and isinstance(target, Enemy):
            return True
        if isinstance(watcher, Player) and isinstance(target, Player):
            return watcher.team != target.team
        return False

    def remove_dead_actor(self, actor: Actor) -> None:
        if not actor.is_dead():
            raise ValueError(f"Нельзя удалить живого актора {actor.name}")
        if isinstance(actor, Player):
            self.players.remove(actor)
        elif isinstance(actor, Enemy):
            self.enemies.remove(actor)
        self.arena.reset_map_cell(actor.position)

    async def check_overwatch_triggers(
        self, moving_actor: Actor, movement_action_id: UUID | None = None
    ) -> bool:
        for watcher in self.get_actors():
            if watcher.overwatch is None or watcher.is_dead():
                continue
            if not self.is_hostile(watcher, moving_actor):
                continue
            weapon = watcher.get_weapon(watcher.overwatch.weapon_id)
            if weapon is None:
                watcher.overwatch = None
                continue
            # если рука с оружием огневого дозора уничтожена к моменту срабатывания -
            # выстрела нет, дозор снимается (ROADMAP.md Этап 2 п.3-4)
            if not watcher.is_weapon_usable(weapon):
                watcher.overwatch = None
                continue
            if self.arena.map.can_shoot(watcher, weapon, moving_actor.position):
                await self._fire_overwatch_shot(
                    watcher, weapon, moving_actor, movement_action_id
                )
                watcher.overwatch = None
                return True
        return False

    async def _fire_overwatch_shot(
        self,
        watcher: Actor,
        weapon: Weapon,
        target: Actor,
        movement_action_id: UUID | None = None,
    ):
        # Дальнобойная атака формирует визуальный круг, поэтому и обычный
        # выстрел, и огневой дозор используют евклидово расстояние.
        distance = Point.distance_euklid(watcher.position, target.position)
        outcome = await self.resolve_and_publish_attack(
            attacker=watcher,
            target=target,
            weapon=weapon,
            distance=distance,
            kind=AttackKind.OVERWATCH,
            movement_action_id=movement_action_id,
        )
        if not outcome.hit:
            await self._notify_event(
                GameEvent(
                    message=f"Огневой дозор: {outcome.skill_prefix}{watcher.name} промахивается по {target.name} из {weapon.name}"  # noqa
                )
            )
            return
        death_detail = ""
        if outcome.target_killed:
            if isinstance(target, Player):
                death_detail = f" Мех {target.name} уничтожен!"
            elif isinstance(target, Enemy):
                death_detail = f" {target.name} погиб!"
        await self._notify_event(
            GameEvent(
                message=f"Огневой дозор: {outcome.skill_prefix}{watcher.name} попадает по {target.name} из {weapon.name} ({outcome.damage} урона){outcome.part_detail}{death_detail}"  # noqa
            )
        )

    def move_actor(self, actor: Actor, cell: Point):
        actor_cell_type = self.arena.map.get(actor.position)
        self.arena.reset_map_cell(actor.position)
        actor.position = cell
        self.arena.map.set(cell, actor_cell_type)

    def dump_state(self) -> dict:
        return self.to_dict()

    async def perform_actor_action(self, actor: Actor, action: Action) -> ActionResult:
        action_result: ActionResult = await self.action_handler.perform_actor_action(
            actor, action
        )
        if action_result.performed:
            await self._notify_event(GameEvent(message=action_result.detail))
            actor.current_action_points = max(
                actor.current_action_points - action_result.action_cost, 0
            )
            actor.current_speed_spent += action_result.speed_spent
        elif isinstance(actor, Player):
            # неуспешная попытка действия (не хватило AP, недоступная клетка
            # и т.п.) — обратная связь только тому, кто попытался, остальным
            # это спам, а не игровое событие
            await self._notify_event(
                GameEvent(message=action_result.detail),
                receiver_player_ids=[str(actor.owner_player_id)],
            )
        # актор мог погибнуть от огневого дозора прямо во время своего
        # перемещения (MOVE не входит в ACTIONS_ENDS_TURN, но мёртвый актор
        # не может продолжать ход) — в этом случае ход тоже нужно передать
        if (action.type in ACTIONS_ENDS_TURN and action_result.performed) or (
            actor.is_dead()
        ):
            await self.pass_turn_to_next_actor()
        self.check_game_end()
        self.turn.available_moves = self.arena.map.get_available_moves(
            self.turn.current_actor
        )
        return action_result

    async def pass_turn_to_next_actor(self):
        if self.turn.phase == GamePhase.PLAYER_PHASE:
            players_by_id = {str(player.id): player for player in self.players}
            while self.turn.player_order_index + 1 < len(self.turn.player_actor_order):
                self.turn.player_order_index += 1
                actor_id = self.turn.player_actor_order[self.turn.player_order_index]
                actor = players_by_id.get(actor_id)
                if actor is None or actor.is_dead():
                    continue
                await self.prepare_actor_turn(actor)
                return

            self.turn.phase = GamePhase.AI_ENEMY_PHASE
            self.turn.current_actor = None

        for enemy in self.enemies:
            if enemy.is_dead():
                continue
            if str(enemy.id) in self.turn.actor_ids_passed_turn:
                continue
            await self.prepare_actor_turn(enemy)
            return

        self.turn.next()
        await self.pass_turn_to_next_actor()

    def check_game_end(self):
        # Победа определяется исключительно исходом PvP: как только одна из
        # команд полностью уничтожена, матч завершён — независимо от того,
        # живы ли ещё нейтральные ИИ-враги на карте (это не co-op зачистка
        # подземелья, а PvP с побочным PvE-элементом, см. AGENTS.md).
        players_team_1 = [x for x in self.players if x.team == 1]
        players_team_2 = [x for x in self.players if x.team == 2]
        team_1_dead = (
            all(p.is_dead() for p in players_team_1) or len(players_team_1) == 0
        )
        team_2_dead = (
            all(p.is_dead() for p in players_team_2) or len(players_team_2) == 0
        )
        if team_1_dead or team_2_dead:
            self.ended = True
            if team_1_dead and team_2_dead:
                self.winner = None  # обе команды уничтожены — ничья
            elif team_1_dead:
                self.winner = 2
            else:
                self.winner = 1

    def _init_players(self):
        point_choices = {
            1: copy.deepcopy(self.arena.start_points_team_1),
            2: copy.deepcopy(self.arena.start_points_team_2),
        }

        players_team_1 = [p for p in self.players if p.team == 1]
        players_team_2 = [p for p in self.players if p.team == 2]
        if len(point_choices[1]) < len(players_team_1):
            raise ValueError("Not enough place choices for all players in team 1")
        if len(point_choices[2]) < len(players_team_2):
            raise ValueError("Not enough place choices for all players in team 2")
        for player in self.players:
            position = random.choice(point_choices[player.team])
            point_choices[player.team].remove(position)
            player.position = position
            self.arena.map.set(player.position, CELL_TYPE.PLAYER.value)
        self.arena.map.clear_start_points()

    def to_dict(self) -> dict:
        """Сериализует всё состояние игры в словарь"""
        dump = {
            "id": str(self.id),
            "arena": self.arena.model_dump(),
            "players": [p.model_dump() for p in self.players],
            "enemies": [enemy.model_dump() for enemy in self.enemies],
            "turn": self.turn.model_dump(),
            "version": self.version,
            "ended": self.ended,
            "winner": self.winner,
        }
        if self.turn.phase == GamePhase.AI_ENEMY_PHASE:
            dump["turn"]["current_actor"] = None
        elif isinstance(self.turn.current_actor, Player):
            # Turn.current_actor аннотирован базовым Actor, поэтому обычный
            # model_dump обрезает поля владельца/команды/меха подкласса.
            dump["turn"]["current_actor"] = self.turn.current_actor.model_dump()
        return dump
