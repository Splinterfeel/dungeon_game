using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using DungeonClient.App;
using DungeonClient.Contracts;
using UnityEngine;
using UnityEngine.UIElements;

namespace DungeonClient.Screens
{
    [RequireComponent(typeof(UIDocument))]
    public sealed class LobbyScreen : MonoBehaviour
    {
        [SerializeField] private StyleSheet styleSheet;
        private VisualElement shell, listPanel, roomPanel, battlePanel;
        private ScrollView rows;
        private Label pilotLabel, status, roomTitle, teams, battleInfo;
        private TextField lobbyName;
        private Toggle vsBot;
        private DropdownField team;
        private Button refresh, create, join, start, leave, reconnect, rematch, back, garage, disconnect;
        private List<LobbySummary> lobbies = new List<LobbySummary>();
        private LobbySummary selected, created;
        private bool busy, refreshing;
        private float nextRefresh;
        private string notice;
        private string listError;
        private int listVersion;
        private ClientApp App => ClientApp.Instance;
        public void SetStyleSheet(StyleSheet value) => styleSheet = value;

        private void Start()
        {
            var root = GetComponent<UIDocument>().rootVisualElement;
            if (styleSheet != null) root.styleSheets.Add(styleSheet);
            shell = root.Q("LobbyShell");
            listPanel = root.Q("LobbyListPanel"); roomPanel = root.Q("LobbyRoomPanel"); battlePanel = root.Q("LobbyBattlePanel");
            rows = root.Q<ScrollView>("LobbyRows");
            pilotLabel = root.Q<Label>("LobbyPilot"); status = root.Q<Label>("LobbyStatus");
            roomTitle = root.Q<Label>("RoomTitle"); teams = root.Q<Label>("RoomTeams"); battleInfo = root.Q<Label>("BattleInfo");
            lobbyName = root.Q<TextField>("LobbyName"); vsBot = root.Q<Toggle>("VsBot");
            team = root.Q<DropdownField>("LobbyTeam"); team.choices = new List<string> { "Команда 1", "Команда 2" }; team.index = 0;
            team.RegisterValueChangedCallback(_ => Render());
            refresh = Bind(root, "RefreshLobbies", Refresh);
            create = Bind(root, "CreateLobby", () => StartCoroutine(Create()));
            join = Bind(root, "JoinLobby", () => StartCoroutine(Join(created ?? selected)));
            start = Bind(root, "StartLobby", () => StartCoroutine(Command(false)));
            leave = Bind(root, "LeaveLobby", () => StartCoroutine(Leave()));
            reconnect = Bind(root, "ReconnectLobby", () => App.Lobby.Reconnect());
            rematch = Bind(root, "RematchLobby", () => StartCoroutine(Command(true)));
            back = Bind(root, "LobbyBack", () => App.Screens.NavigateTo(ScreenId.PilotSelection));
            garage = Bind(root, "LobbyGarage", () => App.Screens.NavigateTo(ScreenId.Garage));
            disconnect = Bind(root, "DisconnectBattle", () =>
            {
                App.Lobby.Clear(); notice = "Клиент отключён от матча. Это не сдача; место на сервере сохранено.";
                App.Screens.NavigateTo(ScreenId.LobbyList);
            });
            App.Screens.Changed += OnScreen;
            App.Lobby.Changed += OnConnection;
            OnScreen(App.Screens.Current);
        }

        private static Button Bind(VisualElement root, string name, Action action)
        {
            var button = root.Q<Button>(name); button.clicked += action; return button;
        }

        private void OnDestroy()
        {
            if (ClientApp.Instance == null) return;
            App.Screens.Changed -= OnScreen; App.Lobby.Changed -= OnConnection;
        }

        private void OnScreen(ScreenId screen)
        {
            listVersion++;
            var visible = screen == ScreenId.LobbyList || screen == ScreenId.LobbyRoom || screen == ScreenId.Battle || screen == ScreenId.MatchResult;
            shell.style.display = visible ? DisplayStyle.Flex : DisplayStyle.None;
            if (!visible) return;
            if (!App.Session.HasPilot) { App.Screens.NavigateTo(ScreenId.PilotSelection); return; }
            if (screen == ScreenId.LobbyList && App.Lobby.Lobby != null)
            { App.Screens.NavigateTo(App.Lobby.Battle == null ? ScreenId.LobbyRoom : ScreenId.Battle); return; }
            pilotLabel.text = "Пилот: " + App.Session.Pilot.Name;
            if (created != null && created.HostId != App.Session.Pilot.Id) created = null;
            listPanel.style.display = screen == ScreenId.LobbyList ? DisplayStyle.Flex : DisplayStyle.None;
            roomPanel.style.display = screen == ScreenId.LobbyRoom ? DisplayStyle.Flex : DisplayStyle.None;
            battlePanel.style.display = screen == ScreenId.Battle || screen == ScreenId.MatchResult ? DisplayStyle.Flex : DisplayStyle.None;
            Render();
            if (screen == ScreenId.LobbyList) Refresh();
        }

        private void Update()
        {
            if (App != null && App.Screens.Current == ScreenId.LobbyList && Time.unscaledTime >= nextRefresh && !busy && !refreshing) Refresh();
        }

        private void Refresh()
        {
            if (refreshing || busy) return;
            nextRefresh = Time.unscaledTime + 5;
            StartCoroutine(Fetch());
        }

        private IEnumerator Fetch()
        {
            refreshing = true; Render();
            var version = listVersion;
            yield return App.Server.GetLobbies(result =>
            {
                if (version != listVersion) return;
                lobbies = result;
                if (selected != null) selected = lobbies.Find(item => item.Id == selected.Id);
                listError = null; DrawRows();
            }, error => { if (version == listVersion) listError = error + " Список может быть устаревшим."; });
            refreshing = false; Render();
        }

        private void DrawRows()
        {
            rows.Clear();
            if (lobbies.Count == 0) rows.Add(new Label("Лобби пока нет. Создай своё."));
            foreach (var lobby in lobbies)
            {
                var state = lobby.Started ? "Матч начат" : lobby.Capacity != 2 ? "Другой формат" : "Ожидание";
                var row = new Button(() =>
                {
                    selected = lobby; created = null;
                    team.index = lobby.VsBot || lobby.TeamOneCount == 0 ? 0 : 1;
                    notice = null; DrawRows(); Render();
                }) { text = $"{lobby.Name} · {Short(lobby.Id)}\n{(lobby.VsBot ? "Против бота" : "PvP")} · команды: {lobby.TeamOneCount} / {lobby.TeamTwoCount} · мест: {lobby.Capacity}\n{state} · хост: {Short(lobby.HostId)}" };
                row.AddToClassList("lobby-row");
                if (selected?.Id == lobby.Id) row.AddToClassList("selected");
                rows.Add(row);
            }
        }

        private IEnumerator Create()
        {
            if (busy || App.Lobby.Lobby != null) yield break;
            busy = true; notice = "Создаём лобби…"; Render();
            var pilotId = App.Session.Pilot.Id;
            var name = lobbyName.value.Trim(); var bot = vsBot.value;
            yield return App.Server.CreateLobby(name, pilotId, bot, result =>
            {
                created = new LobbySummary { Id = result.LobbyId, Name = string.IsNullOrEmpty(name) ? "Лобби · " + Short(result.LobbyId) : name,
                    Capacity = 2, VsBot = bot, HostId = pilotId };
            }, error => notice = error);
            if (created != null && string.IsNullOrEmpty(name))
                yield return App.Server.GetLobbies(result =>
                {
                    var actual = result.Find(item => item.Id == created.Id);
                    if (actual != null) created = actual;
                }, _ => { });
            busy = false;
            if (created != null) { team.index = 0; yield return Join(created); }
            Render();
        }

        private IEnumerator Join(LobbySummary lobby)
        {
            if (busy || lobby == null || App.Lobby.Lobby != null) yield break;
            busy = true; notice = "Присоединяемся…"; Render();
            var pilotId = App.Session.Pilot.Id;
            var joined = false;
            yield return App.Server.JoinLobby(lobby.Id, pilotId, lobby.VsBot ? 1 : team.index + 1,
                result => { joined = result.Result || result.Detail == "player already in lobby"; notice = result.Detail; }, error => notice = error);
            busy = false;
            if (joined)
            {
                created = null; App.Lobby.Enter(lobby, pilotId);
                notice = null; App.Screens.NavigateTo(ScreenId.LobbyRoom);
            }
            else if (created != null) notice += " Можно повторить вступление в созданное лобби.";
            Render();
        }

        private IEnumerator Command(bool isRematch)
        {
            if (busy || !App.Lobby.Connected || App.Lobby.Lobby == null) yield break;
            var id = App.Lobby.Lobby.Id; var pilot = App.Lobby.PilotId;
            busy = true; notice = isRematch ? "Запускаем рематч…" : "Запускаем матч…"; Render();
            Action<LobbyCommandResponse> success = result =>
            { if (App.Lobby.Lobby?.Id == id) notice = result.Result ? "Ждём снимок матча…" : result.Detail; };
            Action<string> failure = error => { if (App.Lobby.Lobby?.Id == id) notice = error; };
            yield return isRematch ? App.Server.Rematch(id, pilot, success, failure) : App.Server.StartLobby(id, pilot, success, failure);
            busy = false; Render();
        }

        private IEnumerator Leave()
        {
            if (busy || App.Lobby.Lobby == null) yield break;
            var id = App.Lobby.Lobby.Id; var pilot = App.Lobby.PilotId;
            busy = true; notice = "Выходим…"; Render();
            var left = false;
            yield return App.Server.LeaveLobby(id, pilot, result =>
            { left = result.Result; notice = result.Detail; }, error => notice = error + " Выход не подтверждён.");
            busy = false;
            if (left && App.Lobby.Lobby?.Id == id)
            { App.Lobby.Clear(); App.Screens.NavigateTo(ScreenId.LobbyList); }
            Render();
        }

        private void OnConnection()
        {
            var connection = App.Lobby;
            if (connection.Lobby == null)
            {
                notice = connection.Error ?? notice;
                if (App.Screens.Current == ScreenId.LobbyRoom || App.Screens.Current == ScreenId.Battle || App.Screens.Current == ScreenId.MatchResult)
                    App.Screens.NavigateTo(ScreenId.LobbyList);
            }
            else if (connection.MatchResult != null) App.Screens.NavigateTo(ScreenId.MatchResult);
            else if (connection.Battle != null)
            { notice = null; App.Screens.NavigateTo(ScreenId.Battle); }
            Render();
        }

        private void Render()
        {
            if (shell == null || App == null) return;
            var connection = App.Lobby; var room = connection.Room;
            status.text = connection.Error ?? (App.Screens.Current == ScreenId.LobbyList ? listError : null) ?? notice ?? (connection.Connecting ? "Подключаемся к комнате…" : refreshing ? "Обновляем список…" : "");
            rows.SetEnabled(!busy);
            refresh.SetEnabled(!busy && !refreshing);
            create.SetEnabled(!busy && created == null);
            lobbyName.SetEnabled(!busy && created == null); vsBot.SetEnabled(!busy && created == null);
            var target = created ?? selected;
            var canJoin = target != null && target.Capacity == 2 && !target.Started &&
                (target.VsBot ? target.TeamOneCount == 0 : target.TeamOneCount + target.TeamTwoCount < 2 && (team.index == 0 ? target.TeamOneCount : target.TeamTwoCount) == 0);
            join.SetEnabled(!busy && canJoin); join.text = created == null ? "Присоединиться" : "Повторить вступление";
            team.SetEnabled(!busy && target != null && !target.VsBot);
            back.SetEnabled(!busy); garage.SetEnabled(!busy);
            var participants = room?.Participants ?? new List<LobbyParticipant>();
            var host = (room?.HostId ?? connection.Lobby?.HostId) == App.Session.Pilot?.Id;
            var ready = room != null && room.Capacity == 2 && (room.VsBot ?
                participants.Count(p => !p.IsBot) == 1 && participants.Any(p => !p.IsBot && p.Team == 1) :
                participants.Count == 2 && participants.Count(p => p.Team == 1) == 1 && participants.Count(p => p.Team == 2) == 1);
            start.SetEnabled(!busy && host && ready && connection.Connected && connection.Battle == null && room?.Status != "game started");
            leave.SetEnabled(!busy && connection.Battle == null && room?.Status != "game started");
            leave.text = host ? "Закрыть лобби" : "Выйти из лобби";
            reconnect.SetEnabled(!busy && connection.Lobby != null && !connection.Connecting && !connection.Connected);
            reconnect.style.display = connection.Lobby == null || connection.Connected ? DisplayStyle.None : DisplayStyle.Flex;
            roomTitle.text = connection.Lobby == null ? "" : connection.Lobby.Name + " · " + Short(connection.Lobby.Id);
            teams.text = room == null ? "Ждём состав комнаты…" : string.Join("\n\n", new[] {1, 2}.Select(number =>
                "Команда " + number + "\n" + string.Join("\n", participants.Where(p => p.Team == number).Select(p =>
                    p.Name + (p.PlayerId == connection.PilotId ? " · Вы" : "") + (p.PlayerId == room.HostId ? " · Хост" : "") + (p.IsBot ? " · Бот" : "") + " · 2 меха"))
                + (room.VsBot && number == 2 && !participants.Any(p => p.IsBot) ? "Бот появится при старте · 2 меха" : "")))
                + "\n\n" + (room.Status == "game started" ? "Матч запускается…" : ready ? "Ожидание старта хостом" : "Ожидание участников");
            var result = connection.MatchResult;
            battleInfo.text = result == null ? "Матч начат. Снимок сервера получен.\nУправление боем будет реализовано следующим этапом.\nСокет остаётся подключённым." :
                $"Матч завершён · победитель: {result["winner"]}\nXP: {result["xp_awarded"]} · уровень: {result["level_before"]} → {result["level_after"]}\nНаграда: {(result["loot_part"] is Newtonsoft.Json.Linq.JObject loot ? (string)loot["name"] : "нет")}";
            rematch.SetEnabled(!busy && host && connection.Connected && result != null);
            disconnect.SetEnabled(!busy);
        }

        private static string Short(string id) => string.IsNullOrEmpty(id) ? "—" : id.Substring(0, Math.Min(8, id.Length));
    }
}
