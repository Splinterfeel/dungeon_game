from dungeon import Dungeon


dungeon = Dungeon(
    width=20, height=20,
    min_rooms=4, max_rooms=4,
    min_room_size=3, max_room_size=4,
    max_chests=3,
    enemies_num=2,
)
dungeon.print_map()
