import random

from pydantic import BaseModel, Field

from src.base import Point
from src.constants import CELL_TYPE
from src.entities.room import Room
from src.map import ArenaMap


class ArenaGenerator(BaseModel):
    """Legacy-генератор карты; не используется в целевом запуске игры."""

    width: int
    height: int
    min_rooms: int
    max_rooms: int
    min_room_size: int
    max_room_size: int
    enemies_num: int
    rooms: list[Room] = Field(default_factory=list)

    def generate(self) -> ArenaMap:
        arena_map = ArenaMap(width=self.width, height=self.height)
        self.rooms = []
        self._generate_rooms(arena_map)
        if len(self.rooms) < 2:
            raise ValueError("Arena generation requires at least two rooms")

        # Генератор исторически выбирал крайнее помещение как стартовое.
        # Для совместимости с PvP-схемой второй команде отдаём другой край.
        team_1_room = self.rooms[-1]
        team_2_room = self.rooms[0]
        arena_map.set(team_1_room.center(), CELL_TYPE.START_TEAM_1.value)
        arena_map.set(team_2_room.center(), CELL_TYPE.START_TEAM_2.value)
        self._generate_enemy_markers(arena_map, (team_1_room, team_2_room))
        return arena_map

    def _generate_rooms(self, arena_map: ArenaMap) -> None:
        num_rooms = random.randint(self.min_rooms, self.max_rooms)
        while len(self.rooms) < num_rooms:
            room_width = random.randint(self.min_room_size, self.max_room_size)
            room_height = random.randint(self.min_room_size, self.max_room_size)
            x = random.randint(1, self.width - room_width - 1)
            y = random.randint(1, self.height - room_height - 1)
            new_room = Room(x=x, y=y, width=room_width, height=room_height)

            if any(new_room.intersects(room) for room in self.rooms):
                continue

            self.rooms.append(new_room)
            for room_x in range(new_room.x, new_room.x + new_room.width):
                for room_y in range(new_room.y, new_room.y + new_room.height):
                    arena_map.set(Point(x=room_x, y=room_y), CELL_TYPE.EMPTY.value)

            if len(self.rooms) < 2:
                continue
            previous = self.rooms[-2].center()
            current = self.rooms[-1].center()
            if random.random() < 0.5:
                self._make_h_tunnel(arena_map, previous.x, current.x, previous.y)
                self._make_v_tunnel(arena_map, previous.y, current.y, current.x)
            else:
                self._make_v_tunnel(arena_map, previous.y, current.y, previous.x)
                self._make_h_tunnel(arena_map, previous.x, current.x, current.y)

    def _generate_enemy_markers(
        self, arena_map: ArenaMap, start_rooms: tuple[Room, Room]
    ) -> None:
        enemy_rooms = [room for room in self.rooms if room not in start_rooms]
        if self.enemies_num > len(enemy_rooms):
            raise ValueError(
                f"enemies num > generated enemy rooms: "
                f"{self.enemies_num} / {len(enemy_rooms)}"
            )
        for room in enemy_rooms[: self.enemies_num]:
            arena_map.set(room.center(), CELL_TYPE.ENEMY.value)

    @staticmethod
    def _make_h_tunnel(arena_map: ArenaMap, x1: int, x2: int, y: int) -> None:
        for x in range(min(x1, x2), max(x1, x2) + 1):
            arena_map.set(Point(x=x, y=y), CELL_TYPE.EMPTY.value)

    @staticmethod
    def _make_v_tunnel(arena_map: ArenaMap, y1: int, y2: int, x: int) -> None:
        for y in range(min(y1, y2), max(y1, y2) + 1):
            arena_map.set(Point(x=x, y=y), CELL_TYPE.EMPTY.value)
