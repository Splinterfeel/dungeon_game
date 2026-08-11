from dto.state import GameState, PlayerState


class LobbyStateView:
    def __init__(self, game):
        self.game = game

    def filter_available_moves(
        self, game_state: GameState, player_id: str
    ) -> GameState:
        game_state = game_state.model_copy(deep=True)
        if not game_state.turn.current_actor:
            game_state.turn.available_moves = []
            return game_state

        current_actor = game_state.turn.current_actor
        if (
            not isinstance(current_actor, PlayerState)
            or current_actor.owner_player_id != player_id
        ):
            game_state.turn.available_moves = []
        return game_state

    def filter_visible_entities_for_team(
        self, game_state: GameState, team: int
    ) -> GameState:
        game_state = game_state.model_copy(deep=True)
        team_players = [player for player in game_state.players if player.team == team]
        enemy_team_players = [
            player for player in game_state.players if player.team != team
        ]

        visible_enemies = []
        visible_players = [player for player in team_players]

        for enemy in game_state.enemies:
            for player in team_players:
                if self.game.arena.map.can_see(player, enemy):
                    visible_enemies.append(enemy)
                    break

        for enemy_player in enemy_team_players:
            for player in team_players:
                if self.game.arena.map.can_see(player, enemy_player):
                    visible_players.append(enemy_player)
                    break

        game_state.players = visible_players
        game_state.enemies = visible_enemies

        if (
            game_state.turn.current_actor is not None
            and game_state.turn.current_actor.team != team
            and all(
                player.id != game_state.turn.current_actor.id
                for player in visible_players
            )
        ):
            game_state.turn.current_actor = None
            game_state.turn.available_moves = []

        return game_state

    def build_states_for_teams(self, game_state: GameState) -> dict[int, GameState]:
        return {
            1: self.filter_visible_entities_for_team(game_state, 1),
            2: self.filter_visible_entities_for_team(game_state, 2),
        }
