using System.Collections.Generic;
using Newtonsoft.Json;
using Newtonsoft.Json.Converters;

namespace DungeonClient.Contracts
{
    [JsonConverter(typeof(StringEnumConverter))]
    public enum BattleActionType { MOVE, ATTACK, OVERWATCH, END_TURN }

    public sealed class BattleCell
    {
        [JsonProperty("x")] public int X;
        [JsonProperty("y")] public int Y;
        public BattleCell() { }
        public BattleCell(int x, int y) { X = x; Y = y; }
    }

    public sealed class BattleState
    {
        [JsonProperty("arena")] public BattleArenaState Arena;
        [JsonProperty("players")] public List<BattleActorState> Players = new();
        [JsonProperty("enemies")] public List<BattleActorState> Enemies = new();
        [JsonProperty("turn")] public BattleTurnState Turn;
        [JsonProperty("version")] public int Version;
        [JsonProperty("ended")] public bool Ended;
        [JsonProperty("winner")] public int? Winner;
    }

    public sealed class BattleArenaState
    {
        [JsonProperty("map")] public BattleMapState Map;
    }

    public sealed class BattleMapState
    {
        [JsonProperty("width")] public int Width;
        [JsonProperty("height")] public int Height;
        [JsonProperty("tiles")] public List<List<string>> Tiles;
        public bool IsFloor(int x, int y) => x >= 0 && y >= 0 && x < Width && y < Height && Tiles[x][y] != " # ";
    }

    public sealed class BattleTurnState
    {
        [JsonProperty("number")] public int Number;
        [JsonProperty("phase")] public int Phase;
        [JsonProperty("current_actor")] public BattleActorState CurrentActor;
        [JsonProperty("available_moves")] public List<BattleCell> AvailableMoves = new();
    }

    // Нейтралы используют те же базовые поля, но не имеют меха/владельца/команды.
    public sealed class BattleActorState
    {
        [JsonProperty("id")] public string Id;
        [JsonProperty("name")] public string Name;
        [JsonProperty("team")] public int Team;
        [JsonProperty("owner_player_id")] public string OwnerId;
        [JsonProperty("position")] public BattleCell Position;
        [JsonProperty("stats")] public CharacterStatsState Stats;
        [JsonProperty("current_action_points")] public int CurrentAp;
        [JsonProperty("current_speed_spent")] public int SpeedSpent;
        [JsonProperty("inventory")] public BattleInventoryState Inventory;
        [JsonProperty("mech")] public GarageMechState Mech;
        [JsonProperty("skills")] public List<SkillState> Skills = new();
        [JsonProperty("overwatch")] public BattleOverwatchState Overwatch;
        public bool WeaponUsable(WeaponState weapon)
        {
            if (weapon == null) return false;
            if (Mech == null) return true;
            var arm = weapon.Hand == "left" ? Mech.ArmsLeft : Mech.ArmsRight;
            return arm != null && !arm.Destroyed;
        }
    }

    public sealed class BattleInventoryState
    {
        [JsonProperty("weapons")] public List<WeaponState> Weapons = new();
    }

    public sealed class BattleOverwatchState
    {
        [JsonProperty("weapon_id")] public string WeaponId;
    }

    public sealed class BattleActionRequest
    {
        [JsonProperty("id")] public string Id;
        [JsonProperty("actor_id")] public string ActorId;
        [JsonProperty("type")] public BattleActionType Type;
        [JsonProperty("cell")] public BattleCell Cell;
        [JsonProperty("params", NullValueHandling = NullValueHandling.Ignore)] public BattleWeaponParams Params;
    }

    public sealed class BattleWeaponParams
    {
        [JsonProperty("weapon_id")] public string WeaponId;
    }

    public sealed class BattleActionResult
    {
        [JsonProperty("action_id")] public string ActionId;
        [JsonProperty("performed")] public bool Performed;
        [JsonProperty("detail")] public string Detail;
    }

    public sealed class BattleMovementState
    {
        [JsonProperty("action_id")] public string ActionId;
        [JsonProperty("actor")] public BattleActorState Actor;
        [JsonProperty("paths")] public List<List<BattleCell>> Paths = new();
        [JsonProperty("sightings")] public List<BattleActorState> Sightings = new();
    }

    public sealed class BattleAttackState
    {
        [JsonProperty("attack_id")] public string AttackId;
        [JsonProperty("attacker_id")] public string AttackerId;
        [JsonProperty("target_id")] public string TargetId;
        [JsonProperty("from_cell")] public BattleCell FromCell;
        [JsonProperty("to_cell")] public BattleCell ToCell;
        [JsonProperty("weapon_type")] public string WeaponType;
        [JsonProperty("kind")] public string Kind;
        [JsonProperty("hit")] public bool Hit;
        [JsonProperty("damage")] public int Damage;
        [JsonProperty("target_killed")] public bool TargetKilled;
        [JsonProperty("movement_action_id")] public string MovementActionId;
        [JsonProperty("skill_procs")] public List<BattleSkillProcState> SkillProcs = new();
    }

    public sealed class BattleSkillProcState
    {
        [JsonProperty("actor_id")] public string ActorId;
        [JsonProperty("actor_name")] public string ActorName;
        [JsonProperty("skill_key")] public string SkillKey;
        [JsonProperty("skill_name")] public string SkillName;
    }

    public sealed class MatchResultState
    {
        [JsonProperty("match_id")] public string MatchId;
        [JsonProperty("winner")] public int? Winner;
        [JsonProperty("xp_awarded")] public int Xp;
        [JsonProperty("level_before")] public int LevelBefore;
        [JsonProperty("level_after")] public int LevelAfter;
        [JsonProperty("loot_part")] public PartState Loot;
    }
}
