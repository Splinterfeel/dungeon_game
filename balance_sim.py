"""
Headless-симуляция боевого баланса.

Прогоняет много полных 2v2 PvP-матчей между пресетами мехов, водя обе
команды напрямую через Game.perform_actor_action - без HTTP/WS/браузера
(AGENTS.md, "Уровень 0" проверки). Простой rational-бот (адаптация
SimpleEnemyAI под PvP: стрельба -> сближение -> ближний бой -> овервотч)
играет за всех акторов сразу с обеих сторон; бот учитывает уничтожение рук
(`PlayerBotAI._pick_weapon` пропускает оружие в уничтоженной руке, ROADMAP.md
Этап 2 п.3-4). По итогу агрегируются win rate, длина матча, остаток HP
победителя и статистика по уничтожению рук (сколько рук выбито за игру, как
часто игрок остаётся полностью безоружным и чем это заканчивается для его
команды) - чтобы на глаз оценить текущий баланс пресетов/оружия без ручного
запуска нескольких клиентов.

Запуск:
- `python balance_sim.py` — базовые матч-апы пресетов.
- `python balance_sim.py --affix-suite` — плюс грубая оценка силы аффиксов
  против зеркала того же пресета.
"""

import argparse
import asyncio
import copy
import random
import uuid
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean

import src.action_handler as action_handler_module


# Продакшен-код намеренно делает await asyncio.sleep(0.1) на каждый шаг
# движения (src/action_handler.py, __perform_action_move), чтобы реальный
# клиент видел пошаговую анимацию по WS. Для headless-симуляции это не
# нужно и сводит скорость к ~4.5s/матч - убираем задержку только здесь,
# в реальном коде она остаётся.
async def _no_sleep(*_args, **_kwargs):
    return None


action_handler_module.asyncio.sleep = _no_sleep

from src.ai.player import PlayerBotAI
from src.arena import Arena
from src.entities.base import Inventory
from src.entities.part import PartSlot
from src.entities.player import Player
from src.game import Game
from src.garage import AFFIX_VALUES_BY_STAT
from src.map import ArenaMap
from src.maps import default
from src.mech_presets import get_mech_preset_by_name


@dataclass(frozen=True)
class AffixSpec:
    stat: str
    tier: int


@dataclass(frozen=True)
class BuildSpec:
    preset_name: str
    affixes: tuple[AffixSpec, ...] = ()


AFFIX_SLOT_BY_STAT: dict[str, PartSlot] = {
    "health": PartSlot.TORSO,
    "speed": PartSlot.LEGS,
    "accuracy": PartSlot.ARMS,
    "melee_power": PartSlot.ARMS,
    "view_distance": PartSlot.HEAD,
}
BALANCE_AFFIX_PRESETS = ("SteelMan", "Fireworks Mk. 1", "StrikeForce")
BALANCE_AFFIX_STATS = ("health", "speed", "accuracy", "melee_power", "view_distance")


def _apply_affix_to_mech_part(mech, affix: AffixSpec) -> None:
    affix_value = AFFIX_VALUES_BY_STAT[affix.stat][affix.tier - 1]
    slot = AFFIX_SLOT_BY_STAT[affix.stat]
    if slot == PartSlot.TORSO:
        targets = [mech.torso]
    elif slot == PartSlot.LEGS:
        targets = [mech.legs]
    elif slot == PartSlot.HEAD:
        targets = [mech.head]
    else:
        targets = [mech.arms_left, mech.arms_right]

    for part in targets:
        setattr(part, affix.stat, getattr(part, affix.stat) + affix_value)
        part.affix_tier = affix.tier
        part.affix_stat = affix.stat
        part.affix_value = affix_value


def make_player(team: int, build: str | BuildSpec, owner_id) -> Player:
    if isinstance(build, str):
        build = BuildSpec(preset_name=build)
    preset = get_mech_preset_by_name(build.preset_name)
    mech = preset.mech
    for affix in build.affixes:
        _apply_affix_to_mech_part(mech, affix)
    return Player(
        owner_player_id=owner_id,
        loadout_id=uuid.uuid4(),
        team=team,
        mech=mech,
        stats=mech.build_character_stats(action_points=10),
        inventory=Inventory(weapons=preset.weapons),
    )


def build_game(team1_builds, team2_builds) -> Game:
    arena_map = ArenaMap(
        width=copy.deepcopy(default.map_2["width"]),
        height=copy.deepcopy(default.map_2["height"]),
        tiles=copy.deepcopy(default.map_2["tiles"]),
    )
    # enemies_num=0: чистый PvP без нейтрального ИИ, чтобы не шуметь поверх
    # баланса пресетов.
    arena = Arena(enemies_num=0, map=arena_map)
    # Целевой формат: один пилот на сторону управляет двумя независимыми
    # лоадаутами. На решения бота владелец не влияет, но модель совпадает с
    # серверным боем и пригодна для будущих пилотских эффектов.
    owner_team_1 = uuid.uuid4()
    owner_team_2 = uuid.uuid4()
    players = [make_player(1, p, owner_team_1) for p in team1_builds] + [
        make_player(2, p, owner_team_2) for p in team2_builds
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


async def run_match(team1_builds, team2_builds, max_actions=2000):
    game = build_game(team1_builds, team2_builds)
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
            ai = PlayerBotAI(actor, game)
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


def _build_names(builds) -> str:
    def _name(build):
        if isinstance(build, str):
            return build
        if not build.affixes:
            return build.preset_name
        suffix = ", ".join(f"{a.stat}+{a.tier}" for a in build.affixes)
        return f"{build.preset_name} [{suffix}]"

    return ", ".join(_name(build) for build in builds)


async def collect_matchup_stats(name, team1_builds, team2_builds, n_games):
    wins = defaultdict(int)
    rounds = []
    hp_left_winner = []
    timeouts = 0
    hands_destroyed_total = []
    disarm_games = 0
    # была ли рука уничтожена именно у ПРОИГРАВШЕЙ команды (риск "рука убила бой")
    disarm_on_loser_side = 0
    for _ in range(n_games):
        result = await run_match(team1_builds, team2_builds)
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

    return {
        "name": name,
        "team1_name": _build_names(team1_builds),
        "team2_name": _build_names(team2_builds),
        "games": n_games,
        "wins": wins,
        "rounds": rounds,
        "hp_left_winner": hp_left_winner,
        "timeouts": timeouts,
        "hands_destroyed_total": hands_destroyed_total,
        "disarm_games": disarm_games,
        "disarm_on_loser_side": disarm_on_loser_side,
    }


def print_matchup_stats(stats) -> None:
    name = stats["name"]
    n_games = stats["games"]
    wins = stats["wins"]
    rounds = stats["rounds"]
    hp_left_winner = stats["hp_left_winner"]
    timeouts = stats["timeouts"]
    hands_destroyed_total = stats["hands_destroyed_total"]
    disarm_games = stats["disarm_games"]
    disarm_on_loser_side = stats["disarm_on_loser_side"]

    print(f"\n=== {name} ({n_games} games) ===")
    print(
        f"Team1 ({stats['team1_name']}) wins: {wins[1]} ({wins[1] / n_games:.0%})"
    )
    print(
        f"Team2 ({stats['team2_name']}) wins: {wins[2]} ({wins[2] / n_games:.0%})"
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


async def run_matchup(name, team1_builds, team2_builds, n_games):
    stats = await collect_matchup_stats(name, team1_builds, team2_builds, n_games)
    print_matchup_stats(stats)
    return stats["wins"]


async def run_counter_matchup(name, preset_a, preset_b, n_games):
    """Пара в обеих командных ориентациях, чтобы отделить силу от первого хода."""
    team_a = [preset_a, preset_a]
    team_b = [preset_b, preset_b]
    wins_a_first = await run_matchup(
        f"{name}: {preset_a} (team 1) vs {preset_b} (team 2)",
        team_a,
        team_b,
        n_games,
    )
    wins_b_first = await run_matchup(
        f"{name}: {preset_b} (team 1) vs {preset_a} (team 2)",
        team_b,
        team_a,
        n_games,
    )
    a_wins = wins_a_first[1] + wins_b_first[2]
    b_wins = wins_a_first[2] + wins_b_first[1]
    total = 2 * n_games
    print(f"\n=== {name}: итог без привязки к стороне первого хода ({total} games) ===")
    print(f"{preset_a} wins: {a_wins} ({a_wins / total:.0%})")
    print(f"{preset_b} wins: {b_wins} ({b_wins / total:.0%})")


def _supports_stat(preset_name: str, stat_name: str) -> bool:
    preset = get_mech_preset_by_name(preset_name)
    if stat_name == "melee_power":
        return preset.mech.arms_left.melee_power > 0
    if stat_name == "accuracy":
        return any(w.type == "ranged" for w in preset.weapons)
    return True


async def run_affix_balance_suite(n_games: int):
    print("\n=== AFFIX BALANCE SUITE ===")
    print(
        "Цель: грубо оценить, насколько один и тот же аффикс на ОБОИХ мехах стороны"
    )
    print(
        "ломает зеркало того же пресета. Результат усредняется по ОБЕИМ сторонам первого хода."
    )
    print("Ориентир: +1 не должен доминировать.")
    summary = []
    for preset_name in BALANCE_AFFIX_PRESETS:
        for stat_name in BALANCE_AFFIX_STATS:
            if not _supports_stat(preset_name, stat_name):
                continue
            for tier in (1, 2, 3):
                affixed_team = [
                    BuildSpec(preset_name, (AffixSpec(stat_name, tier),)),
                    BuildSpec(preset_name, (AffixSpec(stat_name, tier),)),
                ]
                base_team = [preset_name, preset_name]
                stats_affixed_first = await collect_matchup_stats(
                    f"{preset_name}: {stat_name}+{tier} vs base mirror (affixed team first)",
                    affixed_team,
                    base_team,
                    n_games,
                )
                stats_base_first = await collect_matchup_stats(
                    f"{preset_name}: base mirror vs {stat_name}+{tier} (affixed team second)",
                    base_team,
                    affixed_team,
                    n_games,
                )
                affixed_wins = (
                    stats_affixed_first["wins"][1] + stats_base_first["wins"][2]
                )
                total_games = 2 * n_games
                team_affixed_wr = affixed_wins / total_games
                avg_rounds = mean(
                    stats_affixed_first["rounds"] + stats_base_first["rounds"]
                )
                summary.append(
                    {
                        "preset": preset_name,
                        "stat": stat_name,
                        "tier": tier,
                        "winrate": team_affixed_wr,
                        "avg_rounds": avg_rounds,
                    }
                )
                print(
                    f"{preset_name:16} {stat_name:13} +{tier}: "
                    f"{team_affixed_wr:.0%} WR vs mirror, {avg_rounds:.1f} rounds"
                )

    print("\n=== AFFIX SUMMARY (сильнейшие отклонения от 50/50) ===")
    for item in sorted(summary, key=lambda x: abs(x["winrate"] - 0.5), reverse=True)[
        :12
    ]:
        print(
            f"{item['preset']:16} {item['stat']:13} +{item['tier']}: "
            f"{item['winrate']:.0%} WR"
        )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=250, help="Кол-во игр на базовую серию")
    parser.add_argument(
        "--affix-suite",
        action="store_true",
        help="Дополнительно прогнать серию зеркал с аффиксами",
    )
    parser.add_argument(
        "--affix-n",
        type=int,
        default=60,
        help="Кол-во игр на один сценарий аффиксного зеркала",
    )
    args = parser.parse_args()

    random.seed(1234)
    n = args.n
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
        "StrikeForce vs StrikeForce (mirror)",
        ["StrikeForce", "StrikeForce"],
        ["StrikeForce", "StrikeForce"],
        n,
    )
    await run_counter_matchup("SteelMan vs Fireworks", "SteelMan", "Fireworks Mk. 1", n)
    await run_counter_matchup(
        "Fireworks vs StrikeForce", "Fireworks Mk. 1", "StrikeForce", n
    )
    await run_counter_matchup("StrikeForce vs SteelMan", "StrikeForce", "SteelMan", n)
    await run_matchup(
        "Mixed vs Mixed",
        ["SteelMan", "Fireworks Mk. 1"],
        ["SteelMan", "Fireworks Mk. 1"],
        n,
    )
    if args.affix_suite:
        await run_affix_balance_suite(args.affix_n)


if __name__ == "__main__":
    asyncio.run(main())
