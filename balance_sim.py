"""
Headless-симуляция боевого баланса.

Прогоняет много полных 2v2/3v3 PvP-матчей между пресетами мехов, водя обе
команды напрямую через Game.perform_actor_action - без HTTP/WS/браузера
(AGENTS.md, "Уровень 0" проверки). Простой rational-бот (адаптация
SimpleEnemyAI под PvP: стрельба -> сближение -> ближний бой -> овервотч)
играет за всех акторов сразу с обеих сторон; бот учитывает уничтожение рук
(`PvPBotAI._pick_weapon` пропускает оружие в уничтоженной руке, ROADMAP.md
Этап 2 п.3-4). По итогу агрегируются win rate, длина матча, остаток HP
победителя и статистика по уничтожению рук (сколько рук выбито за игру, как
часто игрок остаётся полностью безоружным и чем это заканчивается для его
команды) - чтобы на глаз оценить текущий баланс пресетов/оружия без ручного
запуска нескольких клиентов.

Запуск: python balance_sim.py
"""

import asyncio
import copy
import random
from collections import defaultdict

import src.action_handler as action_handler_module


# Продакшен-код намеренно делает await asyncio.sleep(0.1) на каждый шаг
# движения (src/action_handler.py, __perform_action_move), чтобы реальный
# клиент видел пошаговую анимацию по WS. Для headless-симуляции это не
# нужно и сводит скорость к ~4.5s/матч - убираем задержку только здесь,
# в реальном коде она остаётся.
async def _no_sleep(*_args, **_kwargs):
    return None


action_handler_module.asyncio.sleep = _no_sleep

from src.action import Action, ActionType, AttackActionParams, OverwatchActionParams
from src.ai.base import AI
from src.arena import Arena
from src.base import Point
from src.entities.base import Inventory
from src.entities.player import Player
from src.game import Game
from src.map import ArenaMap
from src.maps import default
from src.mech_presets import get_mech_preset_by_name


class PvPBotAI(AI):
    """Team-aware rational-бот: стреляет, если может, иначе сближается,
    иначе бьёт в ближнем, иначе встаёт в дозор, иначе завершает ход."""

    def __init__(self, actor, game):
        super().__init__(actor, game)
        self.attacked_on_turn = False

    def _hostiles(self):
        return [
            p
            for p in self.game.players
            if self.game._is_hostile(self.actor, p) and not p.is_dead()
        ]

    def _pick_weapon(self, weapon_type):
        "Первое оружие нужного типа, чья рука не уничтожена (ROADMAP.md Этап 2 п.3-4)"
        for w in self.actor.inventory.weapons:
            if w.type != weapon_type:
                continue
            if w.hand and self.actor.mech.arm_for(w.hand).destroyed:
                continue
            return w
        return None

    def decide(self) -> Action:
        hostiles = self._hostiles()
        if not hostiles:
            return self.end_turn()

        if not self.attacked_on_turn:
            ranged_weapon = self._pick_weapon("ranged")
            if (
                ranged_weapon
                and self.actor.current_action_points >= ranged_weapon.cost_ap
            ):
                shootable = [
                    p
                    for p in hostiles
                    if self.game.arena.map.can_shoot(
                        self.actor, ranged_weapon, p.position
                    )
                ]
                if shootable:
                    target = min(shootable, key=lambda p: p.stats.health)
                    self.attacked_on_turn = True
                    return Action(
                        actor_id=str(self.actor.id),
                        type=ActionType.ATTACK,
                        cell=target.position,
                        params=AttackActionParams(weapon_id=ranged_weapon.id),
                    )

        if self.actor.stats.speed - self.actor.current_speed_spent > 0:
            distances = []
            for p in hostiles:
                path = self.game.arena.map.bfs_path(self.actor.position, p.position)
                if path:
                    distances.append((len(path), path))
            if distances:
                _, path = min(distances, key=lambda x: x[0])
                rev_path = path[::-1][:-1]
                for step in rev_path:
                    if step in self.game.turn.available_moves:
                        return Action(
                            actor_id=str(self.actor.id),
                            type=ActionType.MOVE,
                            cell=step,
                        )

        adjacent_target = next(
            (
                p
                for p in hostiles
                if Point.distance_chebyshev(p.position, self.actor.position) == 1
            ),
            None,
        )
        if adjacent_target and not self.attacked_on_turn:
            melee_weapon = self._pick_weapon("melee")
            if (
                melee_weapon
                and self.actor.current_action_points >= melee_weapon.cost_ap
            ):
                self.attacked_on_turn = True
                return Action(
                    actor_id=str(self.actor.id),
                    type=ActionType.ATTACK,
                    cell=adjacent_target.position,
                    params=AttackActionParams(weapon_id=melee_weapon.id),
                )

        if self.actor.overwatch is None:
            ranged_weapon = self._pick_weapon("ranged")
            if (
                ranged_weapon
                and self.actor.current_action_points >= ranged_weapon.cost_ap
            ):
                can_see_any = any(
                    Point.distance_euklid(self.actor.position, p.position)
                    <= self.actor.stats.view_distance
                    for p in hostiles
                )
                if can_see_any:
                    return Action(
                        actor_id=str(self.actor.id),
                        type=ActionType.OVERWATCH,
                        cell=self.actor.position,
                        params=OverwatchActionParams(weapon_id=ranged_weapon.id),
                    )

        return self.end_turn()


def make_player(team: int, preset_name: str) -> Player:
    preset = get_mech_preset_by_name(preset_name)
    mech = preset.mech
    return Player(
        team=team,
        mech=mech,
        stats=mech.build_character_stats(action_points=10),
        inventory=Inventory(weapons=preset.weapons),
    )


def build_game(team1_presets, team2_presets) -> Game:
    arena_map = ArenaMap(
        width=copy.deepcopy(default.map_2["width"]),
        height=copy.deepcopy(default.map_2["height"]),
        tiles=copy.deepcopy(default.map_2["tiles"]),
    )
    # enemies_num=0: чистый PvP без нейтрального ИИ, чтобы не шуметь поверх
    # баланса пресетов.
    arena = Arena(enemies_num=0, map=arena_map)
    players = [make_player(1, p) for p in team1_presets] + [
        make_player(2, p) for p in team2_presets
    ]
    return Game(arena=arena, players=players)


def _hand_stats(players, team):
    "Сколько рук уничтожено и сколько игроков полностью безоружны (обе руки) в команде"
    team_players = [p for p in players if p.team == team]
    destroyed = sum(
        int(p.mech.arms_left.destroyed) + int(p.mech.arms_right.destroyed)
        for p in team_players
    )
    disarmed = sum(
        1
        for p in team_players
        if p.mech.arms_left.destroyed and p.mech.arms_right.destroyed
    )
    return destroyed, disarmed


async def run_match(team1_presets, team2_presets, max_actions=2000):
    game = build_game(team1_presets, team2_presets)
    # снимок ДО того, как game.players начнёт терять погибших (remove_dead_player) -
    # объекты Player переживают удаление из game.players, поэтому по этому списку
    # можно после матча проверить состояние рук у всех, включая погибших
    all_players = list(game.players)
    await game.launch()

    ai_by_actor = {}
    actions_taken = 0
    while not game.ended and actions_taken < max_actions:
        actor = game.turn.current_actor
        ai = ai_by_actor.get(actor.id)
        if ai is None:
            ai = PvPBotAI(actor, game)
            ai_by_actor[actor.id] = ai
        action = ai.decide()
        await game.perform_actor_action(actor, action)
        actions_taken += 1
        # ход этого актора закончился (сменился current_actor) - сбросить
        # его bot-состояние (attacked_on_turn и т.п.) к следующему разу
        if game.turn.current_actor is None or game.turn.current_actor.id != actor.id:
            ai_by_actor.pop(actor.id, None)

    team1_alive = [p for p in game.players if p.team == 1 and not p.is_dead()]
    team2_alive = [p for p in game.players if p.team == 2 and not p.is_dead()]
    hands_destroyed_1, disarmed_1 = _hand_stats(all_players, 1)
    hands_destroyed_2, disarmed_2 = _hand_stats(all_players, 2)
    return {
        "winner": game.winner,
        "rounds": game.turn.number,
        "timeout": actions_taken >= max_actions and not game.ended,
        "team1_hp_left": sum(p.stats.health for p in team1_alive),
        "team2_hp_left": sum(p.stats.health for p in team2_alive),
        "team1_alive": len(team1_alive),
        "team2_alive": len(team2_alive),
        "hands_destroyed_team1": hands_destroyed_1,
        "hands_destroyed_team2": hands_destroyed_2,
        "disarmed_team1": disarmed_1,
        "disarmed_team2": disarmed_2,
    }


async def run_matchup(name, team1_presets, team2_presets, n_games):
    wins = defaultdict(int)
    rounds = []
    hp_left_winner = []
    timeouts = 0
    hands_destroyed_total = []
    disarm_games = 0
    # была ли рука уничтожена именно у ПРОИГРАВШЕЙ команды (риск "рука убила бой")
    disarm_on_loser_side = 0
    for _ in range(n_games):
        result = await run_match(team1_presets, team2_presets)
        if result["timeout"]:
            timeouts += 1
        wins[result["winner"]] += 1
        rounds.append(result["rounds"])
        if result["winner"] == 1:
            hp_left_winner.append(result["team1_hp_left"])
        elif result["winner"] == 2:
            hp_left_winner.append(result["team2_hp_left"])

        game_hands_destroyed = (
            result["hands_destroyed_team1"] + result["hands_destroyed_team2"]
        )
        hands_destroyed_total.append(game_hands_destroyed)
        game_disarmed = result["disarmed_team1"] + result["disarmed_team2"]
        if game_disarmed:
            disarm_games += 1
            loser = {1: 2, 2: 1}.get(result["winner"])
            if loser == 1 and result["disarmed_team1"]:
                disarm_on_loser_side += 1
            elif loser == 2 and result["disarmed_team2"]:
                disarm_on_loser_side += 1

    print(f"\n=== {name} ({n_games} games) ===")
    print(
        f"Team1 ({', '.join(team1_presets)}) wins: {wins[1]} ({wins[1] / n_games:.0%})"
    )
    print(
        f"Team2 ({', '.join(team2_presets)}) wins: {wins[2]} ({wins[2] / n_games:.0%})"
    )
    print(f"Draws: {wins[None]} ({wins[None] / n_games:.0%})")
    if timeouts:
        print(f"WARNING: {timeouts} games hit action-count safety cap without ending")
    print(f"Avg rounds to decide: {sum(rounds) / len(rounds):.1f}")
    if hp_left_winner:
        print(
            f"Avg winner remaining team HP: {sum(hp_left_winner) / len(hp_left_winner):.1f}"
        )
    print(
        f"Avg hands destroyed per game: {sum(hands_destroyed_total) / n_games:.2f} "
        f"(ROADMAP.md Этап 2 п.3-4)"
    )
    if disarm_games:
        print(
            f"Full-disarm events (both hands lost by some player): {disarm_games} "
            f"({disarm_games / n_games:.0%}); disarmed player's team went on to lose: "
            f"{disarm_on_loser_side}/{disarm_games} ({disarm_on_loser_side / disarm_games:.0%})"
        )


async def main():
    random.seed(1234)
    n = 250
    await run_matchup(
        "SteelMan vs SteelMan (mirror)",
        ["SteelMan", "SteelMan"],
        ["SteelMan", "SteelMan"],
        n,
    )
    await run_matchup(
        "Fireworks vs Fireworks (mirror)",
        ["Fireworks Mk. 1", "Fireworks Mk. 1"],
        ["Fireworks Mk. 1", "Fireworks Mk. 1"],
        n,
    )
    await run_matchup(
        "SteelMan team vs Fireworks team",
        ["SteelMan", "SteelMan"],
        ["Fireworks Mk. 1", "Fireworks Mk. 1"],
        n,
    )
    await run_matchup(
        "Mixed vs Mixed",
        ["SteelMan", "Fireworks Mk. 1"],
        ["SteelMan", "Fireworks Mk. 1"],
        n,
    )

    # StrikeForce - карта (map_2) даёт по 6 стартовых точек на команду,
    # так что 3v3 доступно без изменений в Arena/Game - используем его,
    # чтобы у каждого архетипа была своя мирорка и парные матч-апы разом.
    await run_matchup(
        "StrikeForce vs StrikeForce (mirror, 3v3)",
        ["StrikeForce", "StrikeForce", "StrikeForce"],
        ["StrikeForce", "StrikeForce", "StrikeForce"],
        n,
    )
    await run_matchup(
        "SteelMan vs StrikeForce (3v3)",
        ["SteelMan", "SteelMan", "SteelMan"],
        ["StrikeForce", "StrikeForce", "StrikeForce"],
        n,
    )
    await run_matchup(
        "Fireworks vs StrikeForce (3v3)",
        ["Fireworks Mk. 1", "Fireworks Mk. 1", "Fireworks Mk. 1"],
        ["StrikeForce", "StrikeForce", "StrikeForce"],
        n,
    )
    await run_matchup(
        "Mixed (1 of each) vs Mixed (3v3)",
        ["SteelMan", "Fireworks Mk. 1", "StrikeForce"],
        ["SteelMan", "Fireworks Mk. 1", "StrikeForce"],
        n,
    )


if __name__ == "__main__":
    asyncio.run(main())
