from dto.event import GameEvent
from dto.state import PartState
from src.garage import MATCH_XP_REWARDS, roll_match_reward


class LobbyRewards:
    def __init__(self, lobby):
        self.lobby = lobby

    async def finalize_match_rewards(self) -> None:
        """Начисляет награды ровно один раз, в том числе погибшим победителям."""
        game = self.lobby.game
        if not game or game.rewards_granted:
            return

        game.rewards_granted = True
        for player_id, participant in self.lobby.participants.items():
            if participant.is_bot:
                continue

            garage = self.lobby.garages[player_id]
            is_winner = game.winner is not None and participant.team == game.winner
            garage.metrics.matches_finished += 1

            progression = garage.award_xp(
                MATCH_XP_REWARDS["winner" if is_winner else "loser"]
            )
            await self._broadcast_progression(player_id, garage, progression)

            reward = roll_match_reward(garage, is_winner)
            await self._broadcast_reward(player_id, garage, reward)

    async def _broadcast_progression(self, player_id, garage, progression) -> None:
        if progression.level_after > progression.level_before:
            await self.lobby.broadcast_game_event(
                GameEvent(
                    message=(
                        f"Прогресс пилота {garage.name}: +{progression.xp_awarded} XP, "
                        f"уровень {progression.level_before} → {progression.level_after}. "
                        f"Новый выбор навыка доступен в гараже."
                    )
                ),
                receiver_player_ids=[player_id],
            )
            return

        await self.lobby.broadcast_game_event(
            GameEvent(
                message=(
                    f"Прогресс пилота {garage.name}: +{progression.xp_awarded} XP "
                    f"(всего {garage.xp}), уровень {garage.level}."
                )
            ),
            receiver_player_ids=[player_id],
        )

    async def _broadcast_reward(self, player_id, garage, reward) -> None:
        if reward.awarded_part is None:
            chance_percent = round(reward.chance * 100)
            await self.lobby.broadcast_game_event(
                GameEvent(
                    message=(
                        f"Награда: ролл {chance_percent}% для {garage.name} — "
                        f"деталь не выпала. {reward.reason}."
                    )
                ),
                receiver_player_ids=[player_id],
            )
            return

        part_state = PartState.model_validate(
            reward.awarded_part.model_dump(mode="json")
        )
        await self.lobby.broadcast_game_event(
            GameEvent(
                message=(
                    f"Награда: {garage.name} получает {part_state.rarity} "
                    f"деталь «{part_state.name}»!"
                ),
                loot_part=part_state,
            )
        )
