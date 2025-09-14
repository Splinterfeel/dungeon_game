import random
import colorama
from dungeon.constants import Colors, Constants
from dungeon.entities.chest import Chest
from dungeon.entities.room import Room
from dungeon.entities.enemy import Enemy


class Dungeon:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.tiles = [
            [
                Constants.WALL for _ in range(height)
            ] for _ in range(width)
        ]
        self.start_room: Room = None
        self.rooms: list[Room] = []
        self.chests: list[Chest] = []
        self.enemies: list[Enemy] = []

    def generate_dungeon(self, min_rooms: int, max_rooms: int, min_room_size: int, max_room_size: int, max_chests: int, enemies_num: int):
        self._generate_rooms(min_rooms, max_rooms, min_room_size, max_room_size)
        self._generate_start_point()
        self._generate_chests(max_chests)
        self._generate_enemies(enemies_num)

    def _generate_enemies(self, enemies_num: int):
        possible_enemy_rooms = [room for room in self.rooms if room != self.start_room]
        num_enemies = min(enemies_num, len(possible_enemy_rooms))
        for room in possible_enemy_rooms:
            if len(self.enemies) >= num_enemies:
                break
            position = room.center()
            enemy = Enemy(
                x=position[0], y=position[1],
                health=random.randint(10, 20),
                damage=random.randint(3, 5),
            )
            self.enemies.append(enemy)
            if self.tiles[enemy.x][enemy.y] != Constants.FLOOR:
                raise ValueError('Enemy not in floor')
            self.tiles[enemy.x][enemy.y] = Constants.ENEMY

    def _generate_rooms(self, min_rooms, max_rooms, min_room_size, max_room_size):
        num_rooms = random.randint(min_rooms, max_rooms)
        while len(self.rooms) < num_rooms:
            # 1. Randomly select room dimensions and position
            room_width = random.randint(min_room_size, max_room_size)
            room_height = random.randint(min_room_size, max_room_size)
            x = random.randint(1, self.width - room_width - 1)
            y = random.randint(1, self.height - room_height - 1)

            new_room = Room(x, y, room_width, room_height)

            # 2. Check for overlaps with existing rooms
            has_intersection = False
            for existing_room in self.rooms:
                if new_room.intersects(existing_room):
                    has_intersection = True
                    break  # Found an intersection, so we can stop checking
            # 3. If no overlap, carve the room and add it to our list
            if has_intersection:
                continue

            self.rooms.append(new_room)
            # Carve the room into the tiles grid
            # We iterate over the room's area and set the tiles to 0 (floor).
            for i in range(new_room.x, new_room.x + new_room.width):
                for j in range(new_room.y, new_room.y + new_room.height):
                    self.tiles[i][j] = Constants.FLOOR

            # make corridors
            for i in range(len(self.rooms) - 1):
                room1 = self.rooms[i]
                room2 = self.rooms[i + 1]
                x1, y1 = room1.center()
                x2, y2 = room2.center()
                if random.random() < 0.5:
                    self.make_h_tunnel(x1, x2, y1)
                    self.make_v_tunnel(y1, y2, x2)
                else:
                    self.make_v_tunnel(y1, y2, x1)
                    self.make_h_tunnel(x1, x2, y2)

    def _generate_start_point(self):
        distances = {room: 0 for room in self.rooms}

        # Мы можем использовать простую эвристику: расстояние от первой комнаты в списке.
        # Это будет не самый точный способ, но он даст нам смещение к "краю" подземелья.
        # Более сложный подход требует волнового алгоритма, но для начала это сработает.
        first_room = self.rooms[0]

        for i in range(1, len(self.rooms)):
            current_room = self.rooms[i]
            distances[current_room] = i  # Расстояние от первой комнаты

        # 2. Находим комнату с максимальным расстоянием
        farthest_room = first_room
        max_distance = 0
        for room, dist in distances.items():
            if dist > max_distance:
                max_distance = dist
                farthest_room = room

        self.start_room = farthest_room
        # 3. Размещаем стартовую точку в центре этой комнаты
        start_point = farthest_room.center()
        self.tiles[start_point[0]][start_point[1]] = Constants.START

    def _generate_chests(self, max_chests: int):
        # 1. Отфильтруем комнаты, чтобы исключить стартовую
        possible_chest_rooms = [room for room in self.rooms if room != self.start_room]
        # 2. Выберем случайные комнаты для размещения сундуков
        # Убедимся, что не пытаемся разместить больше сундуков, чем комнат
        num_chests = min(max_chests, len(possible_chest_rooms))
        rooms_with_chests = random.sample(possible_chest_rooms, num_chests)
        # 3. Разместим сундуки в выбранных комнатах
        for room in rooms_with_chests:
            choices = self._get_chest_place_choices(room)
            # Выбираем случайную позицию внутри комнаты, избегая границ
            position = random.choice(choices)
            # Определяем количество золота
            # Чем дальше комната, тем больше золота.
            # Мы можем использовать индекс комнаты как простую меру удаленности
            distance_factor = self.rooms.index(room)
            gold_amount = random.randint(10 + distance_factor * 5, 50 + distance_factor * 10)
            new_chest = Chest(position[0], position[1], gold_amount)
            self.chests.append(new_chest)
            # Помечаем тайл как сундук, чтобы его можно было нарисовать
            self.tiles[position[0]][position[1]] = Constants.CHEST

    def _get_chest_place_choices(self, room) -> list[list[int, int]]:
        wall = random.randint(0, 3)
        if wall == 0:
            # верхняя стена
            x_choices = [x for x in range(room.x, room.x + room.width)]
            y_choices = [room.y for _ in x_choices]
        elif wall == 1:
            # нижняя стена
            x_choices = [x for x in range(room.x, room.x + room.width)]
            y_choices = [room.y + room.height - 1 for _ in x_choices]
        elif wall == 2:
            # левая стена
            y_choices = [y for y in range(room.y, room.y + room.height)]
            x_choices = [room.x for _ in y_choices]
        elif wall == 3:
            # правая стена
            y_choices = [y for y in range(room.y, room.y + room.height)]
            x_choices = [room.x + room.width - 1 for _ in y_choices]
        _tile_choices = [[x, y] for x, y in zip(x_choices, y_choices)]
        # исключить тайлы, которые находятся на проходе
        tile_choices = []
        for tile in _tile_choices:
            if self.tiles[tile[0]][tile[1]] != Constants.FLOOR:
                continue
            tile_left = self.tiles[tile[0] - 1][tile[1]]
            tile_right = self.tiles[tile[0] + 1][tile[1]]
            tile_up = self.tiles[tile[0]][tile[1] - 1]
            tile_down = self.tiles[tile[0]][tile[1] + 1]
            if all(t == Constants.FLOOR for t in [tile_left, tile_right, tile_up, tile_down]):
                continue
            tile_choices.append(tile)
        if not tile_choices:
            print()
        return tile_choices

    def print_map(self):
        for y in range(self.height):
            line = ""
            for x in range(self.width):
                value = self.tiles[x][y]
                line += Colors.get(value, colorama.Fore.BLACK)
                line += value
            print(line)
        print('rooms:', len(self.rooms))
        for chest in self.chests:
            print(chest)
        print('full dungeon gold:', sum(chest.gold for chest in self.chests))
        for enemy in self.enemies:
            print("Enemy: Health", enemy.health, 'Dmg', enemy.damage)

    def make_h_tunnel(self, x1: int, x2: int, y: int):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.tiles[x][y] = Constants.FLOOR

    def make_v_tunnel(self, y1: int, y2: int, x: int):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self. tiles[x][y] = Constants.FLOOR
