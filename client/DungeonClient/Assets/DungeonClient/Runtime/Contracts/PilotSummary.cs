using System;
using Newtonsoft.Json;

namespace DungeonClient.Contracts
{
    /// <summary>
    /// Карточка пилота из GET /pilots.
    /// </summary>
    [Serializable]
    public sealed class PilotSummary
    {
        [JsonProperty("id")]
        public string Id { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("xp")]
        public int Xp { get; set; }

        [JsonProperty("level")]
        public int Level { get; set; }

        [JsonProperty("matches_finished")]
        public int MatchesFinished { get; set; }
    }
}
