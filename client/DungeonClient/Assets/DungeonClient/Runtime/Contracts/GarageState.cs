using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace DungeonClient.Contracts
{
    /// <summary>
    /// Минимальная часть постоянного гаража, нужная для входа и первого экрана.
    /// Полный контракт добавляется вместе с редактированием гаража.
    /// </summary>
    [Serializable]
    public sealed class GarageState
    {
        [JsonProperty("player_id")]
        public string PlayerId { get; set; }

        [JsonProperty("xp")]
        public int Xp { get; set; }

        [JsonProperty("level")]
        public int Level { get; set; }

        [JsonProperty("loadouts")]
        public List<GarageLoadoutState> Loadouts { get; set; } = new();
    }

    [Serializable]
    public sealed class GarageLoadoutState
    {
        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("preset_name")]
        public string PresetName { get; set; }
    }
}
