using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace DungeonClient.Contracts
{
    [Serializable]
    public sealed class GarageState
    {
        [JsonProperty("player_id")]
        public string PlayerId { get; set; }

        [JsonProperty("xp")]
        public int Xp { get; set; }

        [JsonProperty("level")]
        public int Level { get; set; }

        [JsonProperty("owned_skills")]
        public List<SkillState> OwnedSkills { get; set; } = new();

        [JsonProperty("pending_skill_choices")]
        public List<PendingSkillChoiceState> PendingSkillChoices { get; set; } = new();

        [JsonProperty("loadouts")]
        public List<GarageLoadoutState> Loadouts { get; set; } = new();

        [JsonProperty("stored_parts")]
        public List<PartState> StoredParts { get; set; } = new();

        [JsonProperty("reward_chances")]
        public Dictionary<string, float> RewardChances { get; set; } = new();

        [JsonProperty("metrics")]
        public GarageMetricsState Metrics { get; set; }
    }

    [Serializable]
    public sealed class GarageLoadoutState
    {
        [JsonProperty("id")]
        public string Id { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("preset_name")]
        public string PresetName { get; set; }

        [JsonProperty("reactor_mode")]
        public string ReactorMode { get; set; }

        [JsonProperty("fire_control_mode")]
        public string FireControlMode { get; set; }

        [JsonProperty("mech")]
        public GarageMechState Mech { get; set; }

        [JsonProperty("stats")]
        public CharacterStatsState Stats { get; set; }

        [JsonProperty("weapons")]
        public List<WeaponState> Weapons { get; set; } = new();
    }

    [Serializable]
    public sealed class GarageMechState
    {
        [JsonProperty("torso")]
        public PartState Torso { get; set; }

        [JsonProperty("legs")]
        public PartState Legs { get; set; }

        [JsonProperty("arms_left")]
        public PartState ArmsLeft { get; set; }

        [JsonProperty("arms_right")]
        public PartState ArmsRight { get; set; }

        [JsonProperty("head")]
        public PartState Head { get; set; }

        [JsonProperty("preset_name")]
        public string PresetName { get; set; }

        [JsonProperty("parts_weight")]
        public int PartsWeight { get; set; }

        [JsonProperty("weight_capacity")]
        public int WeightCapacity { get; set; }
    }

    [Serializable]
    public sealed class CharacterStatsState
    {
        [JsonProperty("health")]
        public int Health { get; set; }

        [JsonProperty("max_health")]
        public int MaxHealth { get; set; }

        [JsonProperty("melee_power")]
        public int MeleePower { get; set; }

        [JsonProperty("speed")]
        public int Speed { get; set; }

        [JsonProperty("action_points")]
        public int ActionPoints { get; set; }

        [JsonProperty("view_distance")]
        public int ViewDistance { get; set; }

        [JsonProperty("accuracy")]
        public int Accuracy { get; set; }
    }

    [Serializable]
    public sealed class WeaponState
    {
        [JsonProperty("id")]
        public string Id { get; set; }

        [JsonProperty("type")]
        public string Type { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("damage")]
        public int Damage { get; set; }

        [JsonProperty("cost_ap")]
        public int CostAp { get; set; }

        [JsonProperty("range")]
        public int Range { get; set; }

        [JsonProperty("accuracy")]
        public int Accuracy { get; set; }

        [JsonProperty("weight")]
        public int Weight { get; set; }

        [JsonProperty("hand")]
        public string Hand { get; set; }
    }

    [Serializable]
    public sealed class PartState
    {
        [JsonProperty("id")]
        public string Id { get; set; }

        [JsonProperty("catalog_key")]
        public string CatalogKey { get; set; }

        [JsonProperty("slot")]
        public string Slot { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("rarity")]
        public string Rarity { get; set; }

        [JsonProperty("health")]
        public int Health { get; set; }

        [JsonProperty("speed")]
        public int Speed { get; set; }

        [JsonProperty("accuracy")]
        public int Accuracy { get; set; }

        [JsonProperty("melee_power")]
        public int MeleePower { get; set; }

        [JsonProperty("view_distance")]
        public int ViewDistance { get; set; }

        [JsonProperty("max_health")]
        public int MaxHealth { get; set; }

        [JsonProperty("current_health")]
        public int CurrentHealth { get; set; }

        [JsonProperty("destroyed")]
        public bool Destroyed { get; set; }

        [JsonProperty("weight")]
        public int Weight { get; set; }

        [JsonProperty("carry_capacity")]
        public int CarryCapacity { get; set; }

        [JsonProperty("affix_tier")]
        public int AffixTier { get; set; }

        [JsonProperty("affix_stat")]
        public string AffixStat { get; set; }

        [JsonProperty("affix_value")]
        public int AffixValue { get; set; }
    }

    [Serializable]
    public sealed class SkillState
    {
        [JsonProperty("skill_key")]
        public string SkillKey { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("trigger")]
        public string Trigger { get; set; }

        [JsonProperty("proc_chance")]
        public float ProcChance { get; set; }

        [JsonProperty("description")]
        public string Description { get; set; }
    }

    [Serializable]
    public sealed class PendingSkillChoiceState
    {
        [JsonProperty("level")]
        public int Level { get; set; }

        [JsonProperty("options")]
        public List<SkillState> Options { get; set; } = new();
    }

    [Serializable]
    public sealed class GarageMetricsState
    {
        [JsonProperty("matches_finished")]
        public int MatchesFinished { get; set; }

        [JsonProperty("reward_rolls")]
        public int RewardRolls { get; set; }

        [JsonProperty("rewards_received")]
        public int RewardsReceived { get; set; }

        [JsonProperty("parts_equipped")]
        public int PartsEquipped { get; set; }

        [JsonProperty("rematches_started")]
        public int RematchesStarted { get; set; }
    }
}