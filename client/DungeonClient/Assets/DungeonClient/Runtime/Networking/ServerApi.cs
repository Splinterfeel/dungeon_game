using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using DungeonClient.Contracts;
using Newtonsoft.Json;
using UnityEngine.Networking;

namespace DungeonClient.Networking
{
    /// <summary>
    /// REST-вызовы первого вертикального среза. Один объект владеет адресом сервера.
    /// </summary>
    public sealed class ServerApi
    {
        private const int RequestTimeoutSeconds = 10;

        private readonly string httpUrl;

        public ServerApi(string httpUrl)
        {
            this.httpUrl = httpUrl.TrimEnd('/');
        }

        public string WebSocketUrl => ServerEndpoint.ToWebSocketUrl(httpUrl);

        public IEnumerator GetLobbies(Action<List<LobbySummary>> success, Action<string> failure)
        {
            yield return GetJson("/lobbies", success, failure);
        }

        public IEnumerator CreateLobby(string name, string pilotId, bool vsBot,
            Action<CreatedLobbyResponse> success, Action<string> failure)
        {
            yield return PostJson("/lobbies", new { name, players_num = 2,
                created_by_player_id = pilotId, vs_bot = vsBot }, success, failure);
        }

        public IEnumerator JoinLobby(string lobbyId, string pilotId, int team,
            Action<LobbyCommandResponse> success, Action<string> failure)
        {
            yield return PostJson("/connect_lobby", new { lobby_id = lobbyId,
                player = new { id = pilotId, team, mech_presets = new string[2] } }, success, failure);
        }

        public IEnumerator LeaveLobby(string lobbyId, string pilotId,
            Action<LobbyCommandResponse> success, Action<string> failure)
        {
            yield return PostJson("/leave_lobby", new { lobby_id = lobbyId, player_id = pilotId }, success, failure);
        }

        public IEnumerator StartLobby(string lobbyId, string pilotId,
            Action<LobbyCommandResponse> success, Action<string> failure)
        {
            yield return PostJson("/start_game", new { lobby_id = lobbyId, host_player_id = pilotId }, success, failure);
        }

        public IEnumerator Rematch(string lobbyId, string pilotId,
            Action<LobbyCommandResponse> success, Action<string> failure)
        {
            yield return PostJson("/debug/rematch", new { lobby_id = lobbyId, host_player_id = pilotId }, success, failure);
        }

        public IEnumerator GetPilots(
            Action<List<PilotSummary>> onSuccess,
            Action<string> onFailure
        )
        {
            yield return GetJson("/pilots", onSuccess, onFailure);
        }

        public IEnumerator GetGarage(
            string playerId,
            Action<GarageState> onSuccess,
            Action<string> onFailure
        )
        {
            yield return GetJson($"/garages/{playerId}", onSuccess, onFailure);
        }

        public IEnumerator CreatePilot(
            string name,
            Action<GarageState> onSuccess,
            Action<string> onFailure
        )
        {
            var request = new CreatePilotRequest
            {
                Name = name,
                MechPresets = new string[2],
            };
            yield return PostJson("/pilots", request, onSuccess, onFailure);
        }

        public IEnumerator EquipGaragePart(
            string playerId,
            string loadoutId,
            string partId,
            Action<GarageState> onSuccess,
            Action<string> onFailure
        )
        {
            var request = new EquipGaragePartRequest
            {
                PlayerId = playerId,
                LoadoutId = loadoutId,
                PartId = partId,
            };
            yield return PostJson("/garages/equip", request, onSuccess, onFailure);
        }

        public IEnumerator UpdateGarageTuning(
            string playerId,
            string loadoutId,
            string reactorMode,
            string fireControlMode,
            Action<GarageState> onSuccess,
            Action<string> onFailure
        )
        {
            var request = new UpdateGarageTuningRequest
            {
                PlayerId = playerId,
                LoadoutId = loadoutId,
                ReactorMode = reactorMode,
                FireControlMode = fireControlMode,
            };
            yield return PostJson("/garages/tuning", request, onSuccess, onFailure);
        }

        public IEnumerator ChooseGarageSkill(
            string playerId,
            string skillKey,
            Action<GarageState> onSuccess,
            Action<string> onFailure
        )
        {
            var request = new ChooseGarageSkillRequest
            {
                PlayerId = playerId,
                SkillKey = skillKey,
            };
            yield return PostJson("/garages/choose_skill", request, onSuccess, onFailure);
        }

        private IEnumerator GetJson<T>(
            string path,
            Action<T> onSuccess,
            Action<string> onFailure
        )
        {
            using var request = UnityWebRequest.Get(BuildUrl(path));
            request.timeout = RequestTimeoutSeconds;
            yield return request.SendWebRequest();
            HandleResponse(request, onSuccess, onFailure);
        }

        private IEnumerator PostJson<TRequest, TResponse>(
            string path,
            TRequest payload,
            Action<TResponse> onSuccess,
            Action<string> onFailure
        )
        {
            var body = Encoding.UTF8.GetBytes(JsonConvert.SerializeObject(payload));
            using var request = new UnityWebRequest(BuildUrl(path), UnityWebRequest.kHttpVerbPOST)
            {
                uploadHandler = new UploadHandlerRaw(body),
                downloadHandler = new DownloadHandlerBuffer(),
                timeout = RequestTimeoutSeconds,
            };
            request.SetRequestHeader("Content-Type", "application/json");
            yield return request.SendWebRequest();
            HandleResponse(request, onSuccess, onFailure);
        }

        private static void HandleResponse<T>(
            UnityWebRequest request,
            Action<T> onSuccess,
            Action<string> onFailure
        )
        {
            if (request.result != UnityWebRequest.Result.Success)
            {
                onFailure(BuildErrorMessage(request));
                return;
            }

            try
            {
                var response = JsonConvert.DeserializeObject<T>(request.downloadHandler.text);
                if (response == null)
                {
                    onFailure("Сервер вернул пустой ответ");
                    return;
                }

                onSuccess(response);
            }
            catch (JsonException)
            {
                onFailure("Сервер вернул ответ в неизвестном формате");
            }
        }

        private string BuildUrl(string path)
        {
            return $"{httpUrl}/{path.TrimStart('/')}";
        }

        private static string BuildErrorMessage(UnityWebRequest request)
        {
            if (!string.IsNullOrWhiteSpace(request.downloadHandler?.text))
            {
                try
                {
                    var detail = Newtonsoft.Json.Linq.JObject.Parse(request.downloadHandler.text)["detail"];
                    if (detail is Newtonsoft.Json.Linq.JArray validation)
                    {
                        return "Некорректный запрос: " + string.Join("; ",
                            System.Linq.Enumerable.Select(validation, item => (string)item["msg"]));
                    }
                    if (detail?.Type == Newtonsoft.Json.Linq.JTokenType.String)
                        return (string)detail;
                }
                catch (JsonException)
                {
                    // Неформатированный ответ ниже заменяется понятным сообщением.
                }
            }

            if (request.responseCode > 0)
            {
                return $"Сервер ответил ошибкой {request.responseCode}";
            }

            return "Не удалось связаться с сервером. Проверь, что он запущен.";
        }

        [Serializable]
        private sealed class CreatePilotRequest
        {
            [JsonProperty("name")]
            public string Name { get; set; }

            [JsonProperty("mech_presets")]
            public string[] MechPresets { get; set; }
        }

        [Serializable]
        private sealed class EquipGaragePartRequest
        {
            [JsonProperty("player_id")]
            public string PlayerId { get; set; }

            [JsonProperty("loadout_id")]
            public string LoadoutId { get; set; }

            [JsonProperty("part_id")]
            public string PartId { get; set; }
        }

        [Serializable]
        private sealed class UpdateGarageTuningRequest
        {
            [JsonProperty("player_id")]
            public string PlayerId { get; set; }

            [JsonProperty("loadout_id")]
            public string LoadoutId { get; set; }

            [JsonProperty("reactor_mode")]
            public string ReactorMode { get; set; }

            [JsonProperty("fire_control_mode")]
            public string FireControlMode { get; set; }
        }

        [Serializable]
        private sealed class ChooseGarageSkillRequest
        {
            [JsonProperty("player_id")]
            public string PlayerId { get; set; }

            [JsonProperty("skill_key")]
            public string SkillKey { get; set; }
        }

    }
}
