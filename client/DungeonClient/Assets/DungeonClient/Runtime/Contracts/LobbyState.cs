using System.Collections.Generic;
using Newtonsoft.Json;

namespace DungeonClient.Contracts
{
    public sealed class LobbySummary
    {
        [JsonProperty("id")] public string Id;
        [JsonProperty("name")] public string Name;
        [JsonProperty("players_num")] public int Capacity;
        [JsonProperty("vs_bot")] public bool VsBot;
        [JsonProperty("team_1_connected_players")] public int TeamOneCount;
        [JsonProperty("team_2_connected_players")] public int TeamTwoCount;
        [JsonProperty("created_by_player_id")] public string HostId;
        [JsonProperty("game_started")] public bool Started;
    }

    public sealed class LobbyParticipant
    {
        [JsonProperty("player_id")] public string PlayerId;
        [JsonProperty("name")] public string Name;
        [JsonProperty("team")] public int Team;
        [JsonProperty("is_bot")] public bool IsBot;
    }

    public sealed class LobbyRoomState
    {
        [JsonProperty("status")] public string Status;
        [JsonProperty("players_num")] public int Capacity;
        [JsonProperty("vs_bot")] public bool VsBot;
        [JsonProperty("created_by_player_id")] public string HostId;
        [JsonProperty("participants")] public List<LobbyParticipant> Participants = new List<LobbyParticipant>();
    }

    public sealed class LobbyCommandResponse
    {
        [JsonProperty("result")] public bool Result;
        [JsonProperty("detail")] public string Detail;
        [JsonProperty("lobby_id")] public string LobbyId;
    }

    public sealed class CreatedLobbyResponse
    {
        [JsonProperty("lobby_id")] public string LobbyId;
    }
}
