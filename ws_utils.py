from enum import IntEnum


class WSCloseCodes(IntEnum):
    LOBBY_NOT_FOUND = 4001
    PLAYER_ALREADY_IN_LOBBY = 4002
    GAME_ALREADY_STARTED = 4003
