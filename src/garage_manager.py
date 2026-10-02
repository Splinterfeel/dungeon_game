from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from dto.garage import (
    GarageLoadoutState,
    GarageMetricsState,
    GarageState,
    PendingSkillChoiceState,
    PilotSummaryState,
)
from dto.state import SkillState
from src.entities.base import Inventory
from src.entities.player import Player
from src.garage import (
    FireControlMode,
    GarageProfile,
    MATCH_REWARD_CHANCES,
    ReactorMode,
)
from src.persistence.database import get_session_factory
from src.persistence.garage import (
    load_catalog,
    load_profile,
    part_from_catalog,
    save_profile,
)
from src.persistence.models import PilotRecord, PartCatalogRecord, PartInstanceRecord
from src.mech.presets import get_mech_preset_by_name, get_random_mech_preset
from sqlmodel import select


class GarageManager:
    """Операции гаража; постоянное состояние загружается из PostgreSQL."""

    async def find_profile(self, player_id: str) -> GarageProfile | None:
        async with get_session_factory()() as session:
            return await load_profile(session, player_id)

    async def get_profile(self, player_id: str) -> GarageProfile:
        profile = await self.find_profile(player_id)
        if profile is None:
            raise ValueError("Гараж пилота ещё не создан: сначала подключитесь к лобби")
        return profile

    async def list_pilots(self) -> list[PilotSummaryState]:
        """Возвращает краткий список профилей для временного debug-клиента."""
        async with get_session_factory()() as session:
            pilots = (
                await session.scalars(
                    select(PilotRecord).order_by(PilotRecord.name, PilotRecord.id)
                )
            ).all()
        return [
            PilotSummaryState(
                id=str(pilot.id),
                name=pilot.name,
                xp=pilot.xp,
                level=pilot.level,
                matches_finished=pilot.matches_finished,
            )
            for pilot in pilots
        ]

    async def save_profile(self, profile: GarageProfile) -> None:
        async with get_session_factory()() as session:
            async with session.begin():
                await save_profile(session, profile)

    async def create_profile(
        self, starting_players: list[Player], profile_name: str | None = None
    ) -> GarageProfile:
        profile = GarageProfile.from_players(starting_players)
        if profile_name:
            profile.name = profile_name
        async with get_session_factory()() as session:
            async with session.begin():
                await self._apply_catalog(session, profile)
                await save_profile(session, profile)
        return profile

    async def create_starting_profile(
        self,
        player_id: UUID,
        mech_presets: list[str | None],
        name: str | None = None,
    ) -> GarageProfile:
        """Создаёт постоянный профиль из двух пресетов через общий путь гаража."""
        presets = []
        for preset_name in mech_presets:
            if preset_name:
                preset = get_mech_preset_by_name(preset_name)
                if preset is None:
                    raise ValueError(f"Неизвестный пресет меха: {preset_name}")
            else:
                preset = get_random_mech_preset()
            presets.append(preset)

        starting_players = [
            Player(
                id=player_id,
                team=1,
                name=name or "",
                mech=preset.mech,
                stats=preset.mech.build_character_stats(action_points=10),
                inventory=Inventory(weapons=preset.weapons),
            )
            for preset in presets
        ]
        return await self.create_profile(starting_players, profile_name=name)

    async def build_players(self, player_id: str, team: int) -> list[Player]:
        return self._build_players(await self.get_profile(player_id), team)

    async def build_temporary_players(
        self, starting_players: list[Player], team: int
    ) -> list[Player]:
        profile = GarageProfile.from_players(starting_players)
        async with get_session_factory()() as session:
            await self._apply_catalog(session, profile)
        return self._build_players(profile, team)

    @staticmethod
    async def _apply_catalog(session: AsyncSession, profile: GarageProfile) -> None:
        catalog_rows = (await session.scalars(select(PartCatalogRecord))).all()
        catalog = {row.catalog_key: row for row in catalog_rows}
        profile.owned_parts = [
            part_from_catalog(
                catalog[part.catalog_key],
                PartInstanceRecord(
                    id=part.id,
                    pilot_id=profile.player_id,
                    catalog_key=part.catalog_key,
                    slot=part.slot.value,
                    affix_tier=part.affix_tier,
                    affix_stat=part.affix_stat,
                    affix_value=part.affix_value,
                ),
            )
            for part in profile.owned_parts
        ]
        templates, definitions, tree = await load_catalog(session)
        profile.part_templates = templates
        profile.skill_definitions = definitions
        profile.skill_choice_rules = tree

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

    async def get_garage_state(self, player_id: str) -> GarageState:
        garage = await self.get_profile(player_id)
        return self._garage_state(garage)

    @staticmethod
    def _garage_state(garage: GarageProfile) -> GarageState:
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
            player_id=str(garage.player_id),
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

    async def equip_garage_part(
        self, player_id: str, loadout_id: str, part_id: str
    ) -> GarageState:
        async with get_session_factory()() as session:
            async with session.begin():
                garage = await load_profile(session, player_id, for_update=True)
                if garage is None:
                    raise ValueError("Гараж пилота не найден")
                garage.equip(loadout_id, part_id)
                await save_profile(session, garage)
        return self._garage_state(garage)

    async def update_garage_tuning(
        self,
        player_id: str,
        loadout_id: str,
        reactor_mode: str,
        fire_control_mode: str,
    ) -> GarageState:
        async with get_session_factory()() as session:
            async with session.begin():
                garage = await load_profile(session, player_id, for_update=True)
                if garage is None:
                    raise ValueError("Гараж пилота не найден")
                garage.set_tuning(
                    loadout_id,
                    ReactorMode(reactor_mode),
                    FireControlMode(fire_control_mode),
                )
                await save_profile(session, garage)
        return self._garage_state(garage)

    async def choose_garage_skill(self, player_id: str, skill_key: str) -> GarageState:
        async with get_session_factory()() as session:
            async with session.begin():
                garage = await load_profile(session, player_id, for_update=True)
                if garage is None:
                    raise ValueError("Гараж пилота не найден")
                garage.choose_skill(skill_key)
                await save_profile(session, garage)
        return self._garage_state(garage)

    async def record_rematch(self, player_id: str) -> None:
        async with get_session_factory()() as session:
            async with session.begin():
                garage = await load_profile(session, player_id, for_update=True)
                if garage is None:
                    raise ValueError("Гараж пилота не найден")
                garage.metrics.rematches_started += 1
                await save_profile(session, garage)
