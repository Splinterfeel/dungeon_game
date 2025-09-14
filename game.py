from dungeon import Dungeon


dungeon = Dungeon(20, 20)
dungeon.generate_dungeon(
    min_rooms=4, max_rooms=4,
    min_room_size=3, max_room_size=4,
    max_chests=3,
)
dungeon.print_map()

