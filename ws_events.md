# События, передаваемые по WS от сервера к игроку

- type: state_update
Обновление состояния игры `dto.state.GameState`

У боевого `PlayerState.id` теперь UUID конкретного меха, а
`PlayerState.owner_player_id` — `player_id` пилота из URL WebSocket. Один
пилот получает обоих своих мехов в `players`, но `turn.available_moves`
заполняется только когда `turn.current_actor.owner_player_id` совпадает с
его `player_id`. В действии клиент передаёт `actor_id` текущего меха.

- type: lobby_state
Обновление состояния лобби `dto.state.LobbyState`

- type: game_event
Значимые события в игре (гибель игрока, присоединение/отсоединение игрока и т д) `dto.event.GameEvent`

