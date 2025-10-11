import colorama


class Constants:
    WALL = ' # '
    FLOOR = '   '
    START = ' S '
    CHEST = ' C '
    ENEMY = ' E '
    EXIT = ' X '
    PLAYER = ' P '


ForeColors = {
    Constants.WALL: colorama.Fore.LIGHTBLACK_EX,
    Constants.FLOOR: colorama.Fore.BLACK,
    Constants.CHEST: colorama.Fore.YELLOW,

    Constants.PLAYER: colorama.Fore.WHITE,
    Constants.ENEMY: colorama.Fore.WHITE,

    Constants.START: colorama.Fore.GREEN,
    Constants.EXIT: colorama.Fore.LIGHTMAGENTA_EX,
}

BackColors = {
    Constants.WALL: colorama.Back.LIGHTBLACK_EX,
    Constants.FLOOR: colorama.Back.BLACK,
    Constants.CHEST: colorama.Back.BLACK,

    Constants.PLAYER: colorama.Back.GREEN,
    Constants.ENEMY: colorama.Back.RED,

    Constants.START: colorama.Back.BLACK,
    Constants.EXIT: colorama.Back.BLACK,
}
