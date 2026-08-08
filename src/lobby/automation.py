from src.action import ActionType
from src.ai.enemy import SimpleEnemyAI
from src.ai.player import PlayerBotAI
from src.entities.enemy import Enemy
from src.entities.player import Player
from src.turn import GamePhase


MAX_AUTOMATED_ACTIONS_PER_ACTOR = 20


class LobbyAutomation:
    def __init__(self, lobby):
        self.lobby = lobby

    async def run_automated_turns(self) -> None:
        """Выполняет ходы PvP-ботов и нейтральных врагов до хода человека."""
        async with self.lobby.automation_lock:
            automated_actor_id = None
            ai = None
            actions_for_actor = 0

            while self.lobby.game and not self.lobby.game.ended:
                actor = self.lobby.game.turn.current_actor
                if isinstance(actor, Player):
                    participant = self.lobby.participants.get(
                        str(actor.owner_player_id)
                    )
                    if participant is None or not participant.is_bot:
                        return
                    ai_class = PlayerBotAI
                elif (
                    isinstance(actor, Enemy)
                    and self.lobby.game.turn.phase == GamePhase.AI_ENEMY_PHASE
                ):
                    ai_class = SimpleEnemyAI
                else:
                    return

                actor_id = str(actor.id)
                if actor_id != automated_actor_id:
                    automated_actor_id = actor_id
                    ai = ai_class(actor, self.lobby.game)
                    actions_for_actor = 0

                if actions_for_actor >= MAX_AUTOMATED_ACTIONS_PER_ACTOR:
                    action = ai.end_turn()
                else:
                    action = ai.decide()
                actions_for_actor += 1

                performed = await self.lobby.handle_game_action(
                    actor, action.model_dump(mode="json")
                )
                await self.lobby.broadcast_game_state()
                if performed:
                    continue

                if action.type == ActionType.END_TURN:
                    return

                fallback = ai.end_turn()
                fallback_performed = await self.lobby.handle_game_action(
                    actor, fallback.model_dump(mode="json")
                )
                await self.lobby.broadcast_game_state()
                if not fallback_performed:
                    return
