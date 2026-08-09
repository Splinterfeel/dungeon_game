import random

from pydantic import BaseModel, Field, model_validator

from src.base import Point
from src.constants import CELL_TYPE, Accuracy
from src.entities.base import CharacterStats, Inventory, Weapon
from src.entities.enemy import Enemy
from src.entities.player import Player
from src.map import ArenaMap


class Arena(BaseModel):
    enemies_num: int
    map: ArenaMap
    min_enemy_ap: int = 9
    max_enemy_ap: int = 12
    enemies: list[Enemy] = Field(default_factory=list)
    start_points_team_1: list[Point] = Field(default_factory=list)
    start_points_team_2: list[Point] = Field(default_factory=list)

    @model_validator(mode="after")
    def initialize_from_map(self) -> "Arena":
        # При обычном создании карта содержит маркеры спавна. При загрузке
        # полного состояния enemies уже заполнены и повторно создавать их нельзя.
        if not self.enemies:
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
        possible_enemy_points: list[Point] = []

        for x in range(self.map.width):
            for y in range(self.map.height):
                point = Point(x=x, y=y)
                cell = self.map.get(point)
                if cell == CELL_TYPE.START_TEAM_1.value:
                    self.start_points_team_1.append(point)
                elif cell == CELL_TYPE.START_TEAM_2.value:
                    self.start_points_team_2.append(point)
                elif cell == CELL_TYPE.ENEMY.value:
                    possible_enemy_points.append(point)
                    self.map.set(point, CELL_TYPE.EMPTY.value)

        if not self.start_points_team_1:
            raise ValueError("Can't find start points for team 1")
        if not self.start_points_team_2:
            raise ValueError("Can't find start points for team 2")
        if self.enemies_num > len(possible_enemy_points):
            raise ValueError(
                f"enemies num > possible_enemy_points: "
                f"{self.enemies_num} / {len(possible_enemy_points)}"
            )

        random.shuffle(possible_enemy_points)
        for point in possible_enemy_points[: self.enemies_num]:
            inventory = Inventory(
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
                    inventory=inventory,
                )
            )
            self.map.set(point, CELL_TYPE.ENEMY.value)

    def remove_dead_enemy(self, enemy: Enemy) -> None:
        self.enemies.remove(enemy)
        self.map.set(enemy.position, CELL_TYPE.EMPTY.value)

    def reset_map_cell(self, cell: Point) -> None:
        self.map.set(cell, self._initial_map.get(cell))

    def remove_dead_player(self, player: Player) -> None:
        self.map.set(player.position, CELL_TYPE.EMPTY.value)
