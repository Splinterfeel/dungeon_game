import random

from pydantic import BaseModel, Field, model_validator

from src.base import Point
from src.constants import CELL_TYPE
from src.map import ArenaMap


class Arena(BaseModel):
    map: ArenaMap
    start_points_team_1: list[Point] = Field(default_factory=list)
    start_points_team_2: list[Point] = Field(default_factory=list)
    enemy_spawn_points: list[Point] = Field(default_factory=list)

    @model_validator(mode="after")
    def initialize_from_map(self) -> "Arena":
        self._init_from_map()
        self._save_initial_map()
        return self

    def _save_initial_map(self) -> None:
        # Снимок содержит только террейн: по нему восстанавливается клетка,
        # которую покинул актор, без возврата старых маркеров сущностей.
        self._initial_map = self.map.model_copy(deep=True)
        self._initial_map.keep_only_terrain()

    def _init_from_map(self) -> None:
        self.start_points_team_1 = []
        self.start_points_team_2 = []
        self.enemy_spawn_points = []

        for x in range(self.map.width):
            for y in range(self.map.height):
                point = Point(x=x, y=y)
                cell = self.map.get(point)
                if cell == CELL_TYPE.START_TEAM_1.value:
                    self.start_points_team_1.append(point)
                elif cell == CELL_TYPE.START_TEAM_2.value:
                    self.start_points_team_2.append(point)
                elif cell == CELL_TYPE.ENEMY.value:
                    self.enemy_spawn_points.append(point)
                    self.map.set(point, CELL_TYPE.EMPTY.value)

        if not self.start_points_team_1:
            raise ValueError("Can't find start points for team 1")
        if not self.start_points_team_2:
            raise ValueError("Can't find start points for team 2")

    def choose_enemy_spawn_points(self, enemies_num: int) -> list[Point]:
        if enemies_num < 0 or enemies_num > len(self.enemy_spawn_points):
            raise ValueError(
                f"invalid enemies num: {enemies_num}; "
                f"available spawn points: {len(self.enemy_spawn_points)}"
            )
        return [
            point.model_copy()
            for point in random.sample(self.enemy_spawn_points, enemies_num)
        ]

    def reset_map_cell(self, cell: Point) -> None:
        self.map.set(cell, self._initial_map.get(cell))
