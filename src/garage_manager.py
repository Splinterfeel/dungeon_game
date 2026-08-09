from uuid import uuid4

from dto.garage import (
    GarageLoadoutState,
    GarageMetricsState,
    GarageState,
    PendingSkillChoiceState,
)
from dto.state import SkillState
from src.entities.player import Player
from src.garage import (
    FireControlMode,
    GarageProfile,
    MATCH_REWARD_CHANCES,
    ReactorMode,
)


class GarageManager:
    """App-scoped реестр гаражей и операции над профилем пилота."""

    def __init__(self) -> None:
        self.profiles: dict[str, GarageProfile] = {}

    def find_profile(self, player_id: str) -> GarageProfile | None:
        return self.profiles.get(player_id)

    def get_profile(self, player_id: str) -> GarageProfile:
        profile = self.find_profile(player_id)
        if profile is None:
            raise ValueError(
                "Гараж пилота ещё не создан: сначала подключитесь через debug-карту"
            )
        return profile

    def register_profile(self, profile: GarageProfile) -> None:
        self.profiles[str(profile.player_id)] = profile

    def create_profile(self, starting_players: list[Player]) -> GarageProfile:
        profile = GarageProfile.from_players(starting_players)
        self.register_profile(profile)
        return profile

    def build_players(self, player_id: str, team: int) -> list[Player]:
        return self._build_players(self.get_profile(player_id), team)

    def build_temporary_players(
        self, starting_players: list[Player], team: int
    ) -> list[Player]:
        profile = GarageProfile.from_players(starting_players)
        return self._build_players(profile, team)

    @staticmethod
    def _build_players(profile: GarageProfile, team: int) -> list[Player]:
        return [
            profile.build_player(
                team=team,
                loadout_id=loadout.id,
                actor_id=uuid4(),
            )
            for loadout in profile.loadouts
        ]

    def get_garage_state(self, player_id: str) -> GarageState:
        garage = self.get_profile(player_id)
        loadout_states = []
        equipped_ids = set()
        for loadout in garage.loadouts:
            player = garage.build_player(loadout_id=loadout.id)
            equipped_ids.update(loadout.equipped_part_ids.values())
            loadout_states.append(
                GarageLoadoutState(
                    id=str(loadout.id),
                    name=loadout.name,
                    preset_name=loadout.preset_name,
                    reactor_mode=loadout.reactor_mode.value,
                    fire_control_mode=loadout.fire_control_mode.value,
                    mech=player.mech.model_dump(mode="json"),
                    stats=player.stats.model_dump(),
                    weapons=[
                        weapon.model_dump(mode="json")
                        for weapon in player.inventory.weapons
                    ],
                )
            )
        return GarageState(
            player_id=player_id,
            xp=garage.xp,
            level=garage.level,
            owned_skills=[
                SkillState.model_validate(skill.model_dump())
                for skill in garage.build_skills()
            ],
            pending_skill_choices=[
                PendingSkillChoiceState(
                    level=level,
                    options=[
                        SkillState.model_validate(skill.model_dump())
                        for skill in options
                    ],
                )
                for level, options in garage.get_pending_skill_options()
            ],
            loadouts=loadout_states,
            stored_parts=[
                part.model_dump(mode="json")
                for part in garage.owned_parts
                if part.id not in equipped_ids
            ],
            reward_chances=MATCH_REWARD_CHANCES,
            metrics=GarageMetricsState.model_validate(garage.metrics.model_dump()),
        )

    def equip_garage_part(
        self, player_id: str, loadout_id: str, part_id: str
    ) -> GarageState:
        garage = self.get_profile(player_id)
        garage.equip(loadout_id, part_id)
        return self.get_garage_state(player_id)

    def update_garage_tuning(
        self,
        player_id: str,
        loadout_id: str,
        reactor_mode: str,
        fire_control_mode: str,
    ) -> GarageState:
        garage = self.get_profile(player_id)
        garage.set_tuning(
            loadout_id,
            ReactorMode(reactor_mode),
            FireControlMode(fire_control_mode),
        )
        return self.get_garage_state(player_id)

    def choose_garage_skill(self, player_id: str, skill_key: str) -> GarageState:
        garage = self.get_profile(player_id)
        garage.choose_skill(skill_key)
        return self.get_garage_state(player_id)
