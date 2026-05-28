import copy
import random
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator
from src.base import Point, PointOffset
from src.constants import CELL_TYPE
from src.entities.base import CharacterStats, Inventory, Weapon
from src.entities.chest import Chest
from src.entities.player import Player
from src.entities.room import Room
from src.entities.enemy import Enemy
from src.map import DungeonMap


class Dungeon(BaseModel):
    max_chests: int
    enemies_num: int
    width: Optional[int] = None
    height: Optional[int] = None
    min_rooms: Optional[int] = None
    max_rooms: Optional[int] = None
    min_room_size: Optional[int] = None
    max_room_size: Optional[int] = None
    min_enemy_ap: int = 8
    max_enemy_ap: int = 10

    # Состояние подземелья
    map: Optional[DungeonMap] = None
    start_room: Optional[Room] = None
    rooms: List[Room] = Field(default_factory=list)
    chests: List[Chest] = Field(default_factory=list)
    enemies: List[Enemy] = Field(default_factory=list)
    exits: List[Point] = Field(default_factory=list)

    # Списки стартовых точек
    start_points_team_1: List[Point] = Field(default_factory=list)
    start_points_team_2: List[Point] = Field(default_factory=list)

    @model_validator(mode="after")
    def initialize_dungeon(self) -> "Dungeon":
        # Если карта уже передана (загрузка), инициализируем из неё
        if self.map is not None:
            # Если списки объектов пусты, значит мы загрузили "сырую" карту и надо их вытащить
            # Если же они полные, значит мы просто восстановили объект из БД/JSON
            if not self.enemies and not self.chests:
                self._init_from_map()
        else:
            # Процедурная генерация
            required_gen_fields = [
                "width",
                "height",
                "min_rooms",
                "max_rooms",
                "min_room_size",
                "max_room_size",
            ]
            for attr in required_gen_fields:
                if getattr(self, attr) is None:
                    raise ValueError(f"Can't procedural generate without {attr}")
            self._procedural_generate()
        self.__save_initial_map()
        return self

    def __save_initial_map(self):
        self._initial_map = self.map.model_copy(deep=True)
        self._initial_map.clear_start_points()

    def _init_from_map(self):
        self.enemies = []
        self.chests = []
        self.rooms = []  # пока непонятно нужно ли, считаем что пока нет
        self.start_room = None
        self.start_points_team_1: list[Point] = []
        self.start_points_team_2: list[Point] = []
        for x in range(self.map.width):
            for y in range(self.map.height):
                _point = Point(x=x, y=y)
                if self.map.get(_point) == CELL_TYPE.START_TEAM_1.value:
                    self.start_points_team_1.append(_point)
                elif self.map.get(_point) == CELL_TYPE.START_TEAM_2.value:
                    self.start_points_team_2.append(_point)
                elif self.map.get(_point) == CELL_TYPE.EXIT.value:
                    self.exits.append(_point)
        if not self.start_points_team_1:
            raise ValueError("Can't find start points for team 1")
        if not self.start_points_team_2:
            raise ValueError("Can't find start points for team 2")
        # find possible chests and enemies positions
        possible_chest_points: list[Point] = []
        possible_enemy_points: list[Point] = []
        for x in range(self.map.width):
            for y in range(self.map.height):
                _point = Point(x=x, y=y)
                if self.map.get(_point) == CELL_TYPE.CHEST.value:
                    possible_chest_points.append(_point)
                    self.map.set(_point, CELL_TYPE.EMPTY.value)
                elif self.map.get(_point) == CELL_TYPE.ENEMY.value:
                    possible_enemy_points.append(_point)
                    self.map.set(_point, CELL_TYPE.EMPTY.value)
        # here can set difficulty of dungeon - min and max enemies

        chests_count = min(
            random.randint(1, self.max_chests), len(possible_chest_points)
        )
        if self.enemies_num > len(possible_enemy_points):
            raise ValueError(
                f"enemies num > possible_enemy_points: {self.enemies_num} / {len(possible_enemy_points)}"
            )
        random.shuffle(possible_chest_points)
        random.shuffle(possible_enemy_points)
        for i in range(chests_count):
            point = possible_chest_points[i]
            self.chests.append(Chest(position=point, gold=random.randint(10, 500)))
            self.map.set(point, CELL_TYPE.CHEST.value)

        for i in range(self.enemies_num):
            point = possible_enemy_points[i]
            mock_enemy_inventory = Inventory(
                weapons=[
                    Weapon(
                        type="melee",
                        name="Старая сабля",
                        damage=3,
                        cost_ap=5,
                        range=1,
                        accuracy=94,
                    ),
                    Weapon(
                        type="ranged",
                        name="Старый пистолет",
                        damage=4,
                        cost_ap=8,
                        range=4,
                        accuracy=83,
                    ),
                ]
            )
            self.enemies.append(
                Enemy(
                    position=point,
                    stats=CharacterStats(
                        health=random.randint(8, 12),
                        damage=random.randint(3, 5),
                        speed=2,
                        view_distance=5,
                        accuracy=75,
                        action_points=random.randint(
                            self.min_enemy_ap, self.max_enemy_ap
                        ),
                    ),
                    inventory=mock_enemy_inventory,
                )
            )
            self.map.set(point, CELL_TYPE.ENEMY.value)

    def _procedural_generate(self):
        self.map = DungeonMap(self.width, self.height)
        if self.rooms is None:
            self.rooms = []
            self._generate_rooms()

        if self.start_room is None:
            self._generate_start_room()
        self.start_points_team_1 = [self.start_room.center()]
        # пока генерация работает только для 1 команды, и по сути для 1 игрока
        self.start_points_team_2 = []

        if self.chests is None:
            self.chests = []
            self._generate_chests()

        if self.enemies is None:
            self.enemies = []
            self._generate_enemies()

        if not self.exits:
            self._generate_exits()

    def remove_dead_enemy(self, enemy: Enemy):
        self.enemies.remove(enemy)
        self.map.set(enemy.position, CELL_TYPE.EMPTY.value)

    def reset_map_cell(self, cell: Point):
        initial_value = self._initial_map.get(cell)
        self.map.set(cell, initial_value)

    def remove_dead_player(self, player: Player):
        self.map.set(player.position, CELL_TYPE.EMPTY.value)

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
                    view_distance=5,
                    accuracy=75,
                    action_points=random.randint(self.min_enemy_ap, self.max_enemy_ap),
                ),
            )
            if not self.map.is_free(enemy.position):
                raise ValueError("Enemy not in free tile")
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
                    self.map.set(Point(i, j), CELL_TYPE.EMPTY.value)

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

    def _generate_start_room(self):
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
            gold_amount = random.randint(
                10 + distance_factor * 5, 50 + distance_factor * 10
            )
            new_chest = Chest(position=position, gold=gold_amount)
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
            if self.map.get(point) != CELL_TYPE.EMPTY.value:
                continue
            point_left = self.map.get(point.on(PointOffset.LEFT))
            point_right = self.map.get(point.on(PointOffset.RIGHT))
            point_up = self.map.get(point.on(PointOffset.TOP))
            point_down = self.map.get(point.on(PointOffset.BOTTOM))
            if all(
                t == CELL_TYPE.EMPTY.value
                for t in [point_left, point_right, point_up, point_down]
            ):
                continue
            result_choices.append(point)
        if not result_choices:
            raise ValueError("No choices for rooms borders")
        return result_choices

    def print_info(self):
        print("rooms:", len(self.rooms))
        for chest in self.chests:
            print(chest)
        print("full dungeon gold:", sum(chest.gold for chest in self.chests))
        for enemy in self.enemies:
            print("Enemy: stats", enemy.stats)

    def _make_h_tunnel(self, x1: int, x2: int, y: int):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.map.set(Point(x, y), CELL_TYPE.EMPTY.value)

    def _make_v_tunnel(self, y1: int, y2: int, x: int):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self.map.set(Point(x, y), CELL_TYPE.EMPTY.value)

    def _generate_exits(self):
        # найдем самую дальнюю комнату от старта
        farthest_room = self.start_room
        largest_distance = 0
        for room in self.rooms:
            distance = Point.distance_euklid(self.start_room.center(), room.center())
            if distance > largest_distance:
                largest_distance = distance
                farthest_room = room
        # генерим точку выхода
        choices = self._get_room_border_places(farthest_room)
        # Выбираем случайную позицию внутри комнаты, избегая границ
        self.exits = [random.choice(choices)]
        for e in self.exits:
            self.map.set(e, CELL_TYPE.EXIT.value)
