import random
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator
from src.base import Point
from src.constants import CELL_TYPE, Accuracy
from src.entities.base import CharacterStats, Inventory, Weapon
from src.entities.player import Player
from src.entities.room import Room
from src.entities.enemy import Enemy
from src.map import ArenaMap


class Arena(BaseModel):
    enemies_num: int
    width: Optional[int] = None
    height: Optional[int] = None
    min_rooms: Optional[int] = None
    max_rooms: Optional[int] = None
    min_room_size: Optional[int] = None
    max_room_size: Optional[int] = None
    min_enemy_ap: int = 9
    max_enemy_ap: int = 12

    # Состояние арены
    map: Optional[ArenaMap] = None
    start_room: Optional[Room] = None
    rooms: List[Room] = Field(default_factory=list)
    enemies: List[Enemy] = Field(default_factory=list)

    # Списки стартовых точек
    start_points_team_1: List[Point] = Field(default_factory=list)
    start_points_team_2: List[Point] = Field(default_factory=list)

    @model_validator(mode="after")
    def initialize_arena(self) -> "Arena":
        # Если карта уже передана (загрузка), инициализируем из неё
        if self.map is not None:
            # Если список пуст, значит мы загрузили "сырую" карту и надо его вытащить
            # Если же он полный, значит мы просто восстановили объект из БД/JSON
            if not self.enemies:
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
        # _initial_map — снимок только террейна (стены/пол): по нему
        # reset_map_cell восстанавливает клетку, которую покидает актор.
        # Маркеры сущностей (враги/игроки/спавны) сюда попадать не должны,
        # иначе покинутые клетки восстанавливаются как занятые.
        self._initial_map = self.map.model_copy(deep=True)
        self._initial_map.keep_only_terrain()

    def _init_from_map(self):
        self.enemies = []
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
        if not self.start_points_team_1:
            raise ValueError("Can't find start points for team 1")
        if not self.start_points_team_2:
            raise ValueError("Can't find start points for team 2")
        # find possible enemies positions
        possible_enemy_points: list[Point] = []
        for x in range(self.map.width):
            for y in range(self.map.height):
                _point = Point(x=x, y=y)
                if self.map.get(_point) == CELL_TYPE.ENEMY.value:
                    possible_enemy_points.append(_point)
                    self.map.set(_point, CELL_TYPE.EMPTY.value)
        # here can set difficulty of arena - min and max enemies

        if self.enemies_num > len(possible_enemy_points):
            raise ValueError(
                f"enemies num > possible_enemy_points: {self.enemies_num} / {len(possible_enemy_points)}"
            )
        random.shuffle(possible_enemy_points)

        for i in range(self.enemies_num):
            point = possible_enemy_points[i]
            mock_enemy_inventory = Inventory(
                weapons=[
                    Weapon(
                        type="melee",
                        name="Повреждённый ударный модуль",
                        damage=3,
                        cost_ap=5,
                        range=1,
                        accuracy=Accuracy.DEFAULT_ENEMY_MELEE_WEAPON_ACCURACY,
                    ),
                    Weapon(
                        type="ranged",
                        name="Ржавая мех-винтовка",
                        damage=4,
                        cost_ap=8,
                        range=4,
                        accuracy=Accuracy.DEFAULT_ENEMY_RANGED_WEAPON_ACCURACY,
                    ),
                ]
            )
            self.enemies.append(
                Enemy(
                    position=point,
                    stats=CharacterStats(
                        health=random.randint(8, 12),
                        melee_power=random.randint(0, 1),
                        speed=3,
                        view_distance=5,
                        accuracy=Accuracy.DEFAULT_ENEMY_STATS_ACCURACY,
                        action_points=random.randint(
                            self.min_enemy_ap, self.max_enemy_ap
                        ),
                    ),
                    inventory=mock_enemy_inventory,
                )
            )
            self.map.set(point, CELL_TYPE.ENEMY.value)

    def _procedural_generate(self):
        self.map = ArenaMap(self.width, self.height)
        if self.rooms is None:
            self.rooms = []
            self._generate_rooms()

        if self.start_room is None:
            self._generate_start_room()
        self.start_points_team_1 = [self.start_room.center()]
        # пока генерация работает только для 1 команды, и по сути для 1 игрока
        self.start_points_team_2 = []

        if self.enemies is None:
            self.enemies = []
            self._generate_enemies()

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
                    melee_power=random.randint(0, 1),
                    speed=3,
                    view_distance=5,
                    accuracy=Accuracy.DEFAULT_ENEMY_STATS_ACCURACY,
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
        # Это будет не самый точный способ, но он даст нам смещение к "краю" арены.
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

    def print_info(self):
        print("rooms:", len(self.rooms))
        for enemy in self.enemies:
            print("Enemy: stats", enemy.stats)

    def _make_h_tunnel(self, x1: int, x2: int, y: int):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.map.set(Point(x, y), CELL_TYPE.EMPTY.value)

    def _make_v_tunnel(self, y1: int, y2: int, x: int):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self.map.set(Point(x, y), CELL_TYPE.EMPTY.value)
