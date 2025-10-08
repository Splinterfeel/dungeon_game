import random
import colorama
from base import Point, get_distance
from dungeon.constants import Colors, Constants
from dungeon.entities.chest import Chest
from dungeon.entities.room import Room
from dungeon.entities.enemy import Enemy


class Dungeon:
    def __init__(
            self, width: int, height: int, min_rooms: int, max_rooms: int, min_room_size: int,
            max_room_size: int, max_chests: int, enemies_num: int):
        self.width = width
        self.height = height
        self.min_rooms = min_rooms
        self.max_rooms = max_rooms
        self.min_room_size = min_room_size
        self.max_room_size = max_room_size
        self.max_chests = max_chests
        self.enemies_num = enemies_num
        self.tiles = [
            [
                Constants.WALL for _ in range(height)
            ] for _ in range(width)
        ]
        self.start_room: Room = None
        self.rooms: list[Room] = []
        self.chests: list[Chest] = []
        self.enemies: list[Enemy] = []
        self._generate_dungeon()

    def _generate_dungeon(self):
        self._generate_rooms()
        self._generate_start_point()
        self._generate_chests()
        self._generate_enemies()
        self._generate_exit()

    def _generate_enemies(self):
        possible_enemy_rooms = [room for room in self.rooms if room != self.start_room]
        num_enemies = min(self.enemies_num, len(possible_enemy_rooms))
        for room in possible_enemy_rooms:
            if len(self.enemies) >= num_enemies:
                break
            position = room.center()
            enemy = Enemy(
                position=position,
                health=random.randint(10, 20),
                damage=random.randint(3, 5),
            )
            if self.tiles[enemy.position.x][enemy.position.y] != Constants.FLOOR:
                raise ValueError('Enemy not in floor')
            self.tiles[enemy.position.x][enemy.position.y] = Constants.ENEMY
            self.enemies.append(enemy)

    def _generate_rooms(self):
        num_rooms = random.randint(self.min_rooms, self.max_rooms)
        while len(self.rooms) < num_rooms:
            # 1. Randomly select room dimensions and position
            room_width = random.randint(self.min_room_size, self.max_room_size)
            room_height = random.randint(self.min_room_size, self.max_room_size)
            x = random.randint(1, self.width - room_width - 1)
            y = random.randint(1, self.height - room_height - 1)

            new_room = Room(x, y, room_width, room_height)

            # 2. Check for overlaps with existing rooms
            has_intersection = False
            for existing_room in self.rooms:
                if new_room.intersects(existing_room):
                    has_intersection = True
                    break  # Found an intersection, so we can stop checking
            if has_intersection:
                continue

            # 3. If no overlap, carve the room and add it to our list
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
                pos_1 = room1.center()
                pos_2 = room2.center()
                if random.random() < 0.5:
                    self._make_h_tunnel(pos_1.x, pos_2.x, pos_1.y)
                    self._make_v_tunnel(pos_1.y, pos_2.y, pos_2.x)
                else:
                    self._make_v_tunnel(pos_1.y, pos_2.y, pos_1.x)
                    self._make_h_tunnel(pos_1.x, pos_2.x, pos_2.y)

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
        self.start_point = farthest_room.center()
        self.tiles[self.start_point.x][self.start_point.y] = Constants.START

    def _generate_chests(self):
        # 1. Отфильтруем комнаты, чтобы исключить стартовую
        possible_chest_rooms = [room for room in self.rooms if room != self.start_room]
        # 2. Выберем случайные комнаты для размещения сундуков
        # Убедимся, что не пытаемся разместить больше сундуков, чем комнат
        num_chests = min(self.max_chests, len(possible_chest_rooms))
        rooms_with_chests = random.sample(possible_chest_rooms, num_chests)
        # 3. Разместим сундуки в выбранных комнатах
        for room in rooms_with_chests:
            choices = self._get_room_border_places(room)
            # Выбираем случайную позицию внутри комнаты, избегая границ
            position = Point(*random.choice(choices))
            # Определяем количество золота
            # Чем дальше комната, тем больше золота.
            # Мы можем использовать индекс комнаты как простую меру удаленности
            distance_factor = self.rooms.index(room)
            gold_amount = random.randint(10 + distance_factor * 5, 50 + distance_factor * 10)
            new_chest = Chest(position, gold_amount)
            self.chests.append(new_chest)
            # Помечаем тайл как сундук, чтобы его можно было нарисовать
            self.tiles[new_chest.position.x][new_chest.position.y] = Constants.CHEST

    def _get_room_border_places(self, room: Room) -> list[list[int, int]]:
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

    def print_info(self):
        print('rooms:', len(self.rooms))
        for chest in self.chests:
            print(chest)
        print('full dungeon gold:', sum(chest.gold for chest in self.chests))
        for enemy in self.enemies:
            print("Enemy: Health", enemy.health, 'Dmg', enemy.damage)

    def _make_h_tunnel(self, x1: int, x2: int, y: int):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.tiles[x][y] = Constants.FLOOR

    def _make_v_tunnel(self, y1: int, y2: int, x: int):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self. tiles[x][y] = Constants.FLOOR

    def _generate_exit(self):
        # найдем самую дальнюю комнату от старта
        farthest_room = self.start_room
        largest_distance = 0
        for room in self.rooms:
            distance = get_distance(self.start_room, room.center())
            if distance > largest_distance:
                largest_distance = distance
                farthest_room = room
        # генерим точку выхода
        choices = self._get_room_border_places(farthest_room)
        # Выбираем случайную позицию внутри комнаты, избегая границ
        self.exit_point = Point(*random.choice(choices))
        self.tiles[self.exit_point.x][self.exit_point.y] = Constants.EXIT
