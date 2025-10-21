import random
from src.base import Point, PointOffset
from src.constants import CELL_TYPE
from src.entities.base import CharacterStats
from src.entities.chest import Chest
from src.entities.room import Room
from src.entities.enemy import Enemy
from src.map import DungeonMap


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
        self.map = DungeonMap(self.width, self.height)
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
                stats=CharacterStats(
                    health=random.randint(10, 20),
                    damage=random.randint(3, 5),
                    speed=2,
                )
            )
            if not self.map.is_free(enemy.position):
                raise ValueError('Enemy not in free tile')
            self.map.set(enemy.position, CELL_TYPE.ENEMY.value)
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
                    self.map.set(Point(i, j), CELL_TYPE.FLOOR.value)

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
        self.map.set(self.start_point, CELL_TYPE.FLOOR.value)

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
            position = random.choice(choices)
            # Определяем количество золота
            # Чем дальше комната, тем больше золота.
            # Мы можем использовать индекс комнаты как простую меру удаленности
            distance_factor = self.rooms.index(room)
            gold_amount = random.randint(10 + distance_factor * 5, 50 + distance_factor * 10)
            new_chest = Chest(position, gold_amount)
            self.chests.append(new_chest)
            self.map.set(new_chest.position, CELL_TYPE.CHEST.value)

    def _get_room_border_places(self, room: Room) -> list[Point]:
        _point_choices = []
        # верхняя стена
        x_choices = [x for x in range(room.x, room.x + room.width)]
        y_choices = [room.y for _ in x_choices]
        _point_choices.extend([Point(x, y) for x, y in zip(x_choices, y_choices)])
        # нижняя стена
        x_choices = [x for x in range(room.x, room.x + room.width)]
        y_choices = [room.y + room.height - 1 for _ in x_choices]
        _point_choices.extend([Point(x, y) for x, y in zip(x_choices, y_choices)])
        # левая стена
        y_choices = [y for y in range(room.y, room.y + room.height)]
        x_choices = [room.x for _ in y_choices]
        _point_choices.extend([Point(x, y) for x, y in zip(x_choices, y_choices)])
        # правая стена
        y_choices = [y for y in range(room.y, room.y + room.height)]
        x_choices = [room.x + room.width - 1 for _ in y_choices]
        _point_choices.extend([Point(x, y) for x, y in zip(x_choices, y_choices)])
        _point_choices = [p for p in _point_choices if self.map.is_free(p)]
        # исключить тайлы, которые находятся на проходе
        result_choices = []
        for point in _point_choices:
            print(self.map.get(point))
            print(self.map.get(point))
            print(self.map.get(point))
            print(self.map.get(point))
            if self.map.get(point) != CELL_TYPE.FLOOR.value:
                continue
            point_left = self.map.get(point.on(PointOffset.LEFT))
            point_right = self.map.get(point.on(PointOffset.RIGHT))
            point_up = self.map.get(point.on(PointOffset.TOP))
            point_down = self.map.get(point.on(PointOffset.BOTTOM))
            if all(t == CELL_TYPE.FLOOR.value for t in [point_left, point_right, point_up, point_down]):
                continue
            result_choices.append(point)
        if not result_choices:
            raise ValueError("No choices for rooms borders")
        return result_choices

    def print_info(self):
        print('rooms:', len(self.rooms))
        for chest in self.chests:
            print(chest)
        print('full dungeon gold:', sum(chest.gold for chest in self.chests))
        for enemy in self.enemies:
            print("Enemy: stats", enemy.stats)

    def _make_h_tunnel(self, x1: int, x2: int, y: int):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.map.set(Point(x, y), CELL_TYPE.FLOOR.value)

    def _make_v_tunnel(self, y1: int, y2: int, x: int):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self.map.set(Point(x, y), CELL_TYPE.FLOOR.value)

    def _generate_exit(self):
        # найдем самую дальнюю комнату от старта
        farthest_room = self.start_room
        largest_distance = 0
        for room in self.rooms:
            distance = Point.get_distance(self.start_room.center(), room.center())
            if distance > largest_distance:
                largest_distance = distance
                farthest_room = room
        # генерим точку выхода
        choices = self._get_room_border_places(farthest_room)
        # Выбираем случайную позицию внутри комнаты, избегая границ
        self.exit_point = random.choice(choices)
        self.map.set(self.exit_point, CELL_TYPE.EXIT.value)
