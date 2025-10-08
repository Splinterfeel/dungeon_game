import colorama


class Constants:
    WALL = ' # '
    FLOOR = '   '
    START = ' S '
    CHEST = ' C '
    ENEMY = ' E '


Colors = {
    Constants.WALL: colorama.Fore.BLUE,
    Constants.FLOOR: colorama.Fore.BLACK,
    Constants.CHEST: colorama.Fore.YELLOW,
    Constants.START: colorama.Fore.GREEN,
    Constants.ENEMY: colorama.Fore.RED,
}
