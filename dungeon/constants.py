import colorama


class Constants:
    WALL = ' # '
    FLOOR = '   '
    START = ' S '
    CHEST = ' C '
    ENEMY = ' E '
    EXIT = ' X '
    PLAYER = ' P '


Colors = {
    Constants.WALL: colorama.Fore.BLUE,
    Constants.FLOOR: colorama.Fore.BLACK,
    Constants.CHEST: colorama.Fore.YELLOW,
    Constants.START: colorama.Fore.GREEN,
    Constants.PLAYER: colorama.Fore.GREEN,
    Constants.ENEMY: colorama.Fore.RED,
    Constants.EXIT: colorama.Fore.LIGHTMAGENTA_EX,
}
