from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

from dto.event import GameEvent, MatchResultEvent
from dto.state import PartState
from src.garage import MATCH_XP_REWARDS, roll_match_reward
from src.persistence.database import get_session_factory
from src.persistence.garage import load_profile, save_profile
from src.persistence.models import (
    MatchParticipantRecord,
    MatchRecord,
    MatchRewardRecord,
)


class LobbyRewards:
    def __init__(self, lobby):
        self.lobby = lobby

    async def finalize_match_rewards(self) -> None:
        """Начисляет награды ровно один раз, в том числе погибшим победителям."""
        game = self.lobby.game
        if not game or game.rewards_granted:
            return

        notifications = []
        async with get_session_factory()() as session:
            async with session.begin():
                await session.execute(
                    insert(MatchRecord)
                    .values(id=game.id, winner=game.winner, finalized=False)
                    .on_conflict_do_nothing(index_elements=["id"])
                )
                match = await session.get(MatchRecord, game.id, with_for_update=True)
                if match.finalized:
                    game.rewards_granted = True
                    return

                participants = sorted(
                    (p for p in self.lobby.participants.values() if not p.is_bot),
                    key=lambda p: p.player_id,
                )
                for participant in participants:
                    player_id = participant.player_id
                    garage = await load_profile(session, player_id, for_update=True)
                    if garage is None:
                        raise ValueError(f"Гараж пилота {player_id} не найден")
                    is_winner = (
                        game.winner is not None and participant.team == game.winner
                    )
                    garage.metrics.matches_finished += 1
                    progression = garage.award_xp(
                        MATCH_XP_REWARDS["winner" if is_winner else "loser"]
                    )
                    reward = roll_match_reward(garage, is_winner)
                    await save_profile(session, garage)
                    session.add(
                        MatchParticipantRecord(
                            match_id=game.id,
                            pilot_id=UUID(player_id),
                            team=participant.team,
                        )
                    )
                    session.add(
                        MatchRewardRecord(
                            match_id=game.id,
                            pilot_id=UUID(player_id),
                            xp_awarded=progression.xp_awarded,
                            part_id=(
                                reward.awarded_part.id if reward.awarded_part else None
                            ),
                            chance=reward.chance,
                            reason=reward.reason,
                        )
                    )
                    notifications.append((player_id, garage, progression, reward))
                match.winner = game.winner
                match.finalized = True

        game.rewards_granted = True
        for player_id, garage, progression, reward in notifications:
            await self._broadcast_progression(player_id, garage, progression)
            await self._broadcast_reward(player_id, garage, reward)
            await self._broadcast_match_result(
                player_id, game.id, game.winner, progression, reward
            )

    async def _broadcast_match_result(
        self, player_id, match_id, winner, progression, reward
    ) -> None:
        loot_part = None
        if reward.awarded_part is not None:
            loot_part = PartState.model_validate(
                reward.awarded_part.model_dump(mode="json")
            )
        event = MatchResultEvent(
            match_id=str(match_id),
            winner=winner,
            xp_awarded=progression.xp_awarded,
            level_before=progression.level_before,
            level_after=progression.level_after,
            loot_part=loot_part,
        )
        await self.lobby.broadcast_game_event(event, receiver_player_ids=[player_id])

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
