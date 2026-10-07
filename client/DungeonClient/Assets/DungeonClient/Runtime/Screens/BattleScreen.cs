using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using DungeonClient.App;
using DungeonClient.Battle;
using DungeonClient.Contracts;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UIElements;

namespace DungeonClient.Screens
{
    [RequireComponent(typeof(UIDocument), typeof(BattleArenaView))]
    public sealed class BattleScreen : MonoBehaviour
    {
        [SerializeField] private StyleSheet styleSheet;
        private VisualElement root, shell, hud, weapons, labels, detailsPanel, detailParts, resultPanel;
        private Label phase, infoName, infoStats, infoParts, status, actionsTitle, details, journal, resultTitle, resultInfo;
        private Button overwatch, endTurn, reconnect, resultGarage, resultLobby, rematch, resultReconnect;
        private BattleArenaView arena;
        private BattleState state;
        private readonly BattlePlaybackQueue playback = new();
        private BattleActorState playbackActor;
        private MatchResultState presentedResult;
        private bool awaitingSnapshot = true;
        private bool playbackWasPlaying;
        private const float ActorChangePause = .35f;
        private float playbackResumeAt;
        private string lastPlaybackActorId;
        private readonly List<string> events = new();
        private readonly Dictionary<string, (VisualElement root, Label name, ProgressBar health, ProgressBar ap)> actorLabels = new();
        private readonly List<(Label label, Vector3 position, float started, float offset, float duration)> combatTexts = new();
        private string inspectedId, lastOwnId, weaponId, weaponActorId, loadedResultId;
        private BattleCell hovered;
        private bool visible, resultBusy, recoveringGarage;
        private int ownTeam;
        private ClientApp App => ClientApp.Instance;
        private BattleActorState Active => state?.Turn?.CurrentActor;
        private BattleActorState OwnCurrent => Active?.OwnerId == App.Session.Pilot?.Id ? Find(Active.Id) :
            Find(lastOwnId) ?? state?.Players.FirstOrDefault(actor => actor.OwnerId == App.Session.Pilot?.Id && actor.Stats.Health > 0);
        private BattleActorState Inspected => Find(inspectedId);
        private BattleActorState InfoActor => Inspected ?? OwnCurrent;
        private WeaponState SelectedWeapon => OwnCurrent?.Inventory?.Weapons.FirstOrDefault(weapon => weapon.Id == weaponId);
        private MatchResultState Result => presentedResult;
        private bool Playing => playback.Pending || arena.IsAnimating || Time.unscaledTime < playbackResumeAt;
        private bool CanAct => state != null && !state.Ended && Result == null && Active?.OwnerId == App.Session.Pilot?.Id &&
            !Playing && ReferenceEquals(state, App.Lobby.State) &&
            App.Lobby.Connected && App.Lobby.SnapshotReady && App.Lobby.PendingActionId == null && !App.Lobby.ActionUncertain;

        public void SetStyleSheet(StyleSheet value) => styleSheet = value;

        private void Start()
        {
            root = GetComponent<UIDocument>().rootVisualElement;
            if (styleSheet != null) root.styleSheets.Add(styleSheet);
            shell = root.Q("BattleShell"); shell.pickingMode = PickingMode.Ignore;
            hud = root.Q("BattleHud"); weapons = root.Q("BattleWeapons");
            labels = root.Q("BattleLabels"); labels.pickingMode = PickingMode.Ignore;
            detailsPanel = root.Q("BattleDetailsPanel"); resultPanel = root.Q("BattleResultPanel");
            detailParts = root.Q("BattleDetailParts");
            phase = root.Q<Label>("BattlePhase"); infoName = root.Q<Label>("BattleActorName");
            infoStats = root.Q<Label>("BattleStats"); infoParts = root.Q<Label>("BattleParts");
            status = root.Q<Label>("BattleStatus"); actionsTitle = root.Q<Label>("BattleActionsTitle");
            details = root.Q<Label>("BattleDetails"); journal = root.Q<Label>("BattleJournal");
            resultTitle = root.Q<Label>("BattleResultTitle"); resultInfo = root.Q<Label>("BattleResultInfo");
            overwatch = Bind("BattleOverwatch", () => Send(BattleActionType.OVERWATCH, Active?.Position));
            endTurn = Bind("BattleEndTurn", () => Send(BattleActionType.END_TURN, Active?.Position));
            reconnect = Bind("BattleReconnect", () => App.Lobby.Reconnect());
            Bind("BattleShowDetails", () => detailsPanel.style.display = DisplayStyle.Flex);
            Bind("BattleCloseDetails", () => detailsPanel.style.display = DisplayStyle.None);
            Bind("BattleExit", () => Exit(ScreenId.LobbyList));
            Bind("BattleCenter", () => arena.ResetCamera());
            resultGarage = Bind("ResultGarage", () => Exit(ScreenId.Garage));
            resultLobby = Bind("ResultLobby", () => Exit(ScreenId.LobbyList));
            rematch = Bind("ResultRematch", () => StartCoroutine(Rematch()));
            resultReconnect = Bind("ResultReconnect", () => App.Lobby.Reconnect());
            arena = GetComponent<BattleArenaView>(); arena.Initialize();
            arena.AttackEffects.AttackPlayed += ShowCombatText;
            arena.AttackEffects.Cleared += ClearCombatTexts;
            App.Screens.Changed += OnScreen;
            App.Lobby.Changed += OnConnection;
            App.Lobby.MessageReceived += OnMessage;
            OnScreen(App.Screens.Current);
        }

        private Button Bind(string name, Action action)
        {
            var button = root.Q<Button>(name); button.clicked += action; return button;
        }

        private void OnDestroy()
        {
            if (arena != null && arena.AttackEffects != null)
            {
                arena.AttackEffects.AttackPlayed -= ShowCombatText;
                arena.AttackEffects.Cleared -= ClearCombatTexts;
            }
            if (ClientApp.Instance == null) return;
            App.Screens.Changed -= OnScreen;
            App.Lobby.Changed -= OnConnection;
            App.Lobby.MessageReceived -= OnMessage;
        }

        private void OnScreen(ScreenId screen)
        {
            var wasVisible = visible;
            visible = screen == ScreenId.Battle || screen == ScreenId.MatchResult;
            shell.style.display = visible ? DisplayStyle.Flex : DisplayStyle.None;
            arena.SetVisible(visible);
            if (visible)
            {
                if (!wasVisible) awaitingSnapshot = true;
                if (state == null)
                    foreach (var message in App.Lobby.RecentMessages.Where(message => (string)message["type"] == "game_event"))
                        AddEvent((string)message["message"]);
                OnConnection();
            }
            else ClearPlayback();
        }

        private BattleActorState Find(string id) => id == null || state == null ? null :
            state.Players.Concat(state.Enemies).FirstOrDefault(actor => actor.Id == id && actor.Stats.Health > 0);

        private void OnConnection()
        {
            if (!visible) return;
            if (!App.Lobby.SnapshotReady)
            {
                ClearPlayback();
                awaitingSnapshot = true;
            }
            else if (awaitingSnapshot && App.Lobby.State != null)
            {
                ClearPlayback();
                ApplyState(App.Lobby.State);
                presentedResult = App.Lobby.Outcome;
                awaitingSnapshot = false;
            }
            SelectDefaultWeapon();
            Render();
        }

        private void ClearPlayback()
        {
            playback.Clear(); playbackActor = null; playbackWasPlaying = false;
            playbackResumeAt = 0; lastPlaybackActorId = null;
            arena.StopMovement();
        }

        private void ApplyState(BattleState next)
        {
            var wasEnded = state?.Ended == true || loadedResultId != null;
            var startingMatch = state == null || (wasEnded && !next.Ended);
            state = next;
            if (wasEnded && !state.Ended)
            {
                inspectedId = null; lastOwnId = null; weaponId = null; weaponActorId = null; loadedResultId = null;
                presentedResult = null; resultBusy = false; events.Clear(); journal.text = "";
            }
            var own = state.Players.FirstOrDefault(actor => actor.OwnerId == App.Session.Pilot?.Id);
            if (own != null) ownTeam = own.Team;
            if (Active?.OwnerId == App.Session.Pilot?.Id) lastOwnId = Active.Id;
            if (Find(inspectedId) == null) inspectedId = null;
            if (startingMatch)
            {
                arena.StopMovement();
                lastPlaybackActorId = Active?.Id;
            }
            arena.Apply(state, ownTeam);
            if (startingMatch) arena.StartCamera(OwnCurrent?.Position);
            SyncLabels();
            SelectDefaultWeapon();
            Render();
        }

        private void SelectDefaultWeapon()
        {
            var actor = OwnCurrent;
            if (actor == null) { weaponId = null; weaponActorId = null; return; }
            if (weaponActorId != actor.Id || !actor.WeaponUsable(SelectedWeapon))
            {
                weaponActorId = actor.Id;
                weaponId = actor.Inventory.Weapons.FirstOrDefault(actor.WeaponUsable)?.Id;
            }
        }

        private void OnMessage(JObject message)
        {
            if (!visible) return;
            var type = (string)message["type"];
            if (type == "state_update" && awaitingSnapshot) return;
            if (type == "actor_attacked" || type == "actor_moved" || type == "state_update" ||
                type == "game_event" || type == "action_result" || type == "match_result")
                playback.Enqueue(message);
        }

        private void AdvancePlayback()
        {
            if (!App.Lobby.SnapshotReady || Time.unscaledTime < playbackResumeAt) return;
            while (!arena.IsAnimating && Time.unscaledTime >= playbackResumeAt)
            {
                var nextActorId = playback.NextActorId;
                if (nextActorId != null && lastPlaybackActorId != null && nextActorId != lastPlaybackActorId)
                {
                    lastPlaybackActorId = nextActorId;
                    playbackResumeAt = Time.unscaledTime + ActorChangePause;
                    break;
                }
                if (!playback.TryDequeue(out var message, out var interruptions)) break;
                playbackActor = null;
                switch ((string)message["type"])
                {
                    case "actor_attacked":
                        var attack = message.ToObject<BattleAttackState>();
                        playbackActor = Find(attack.AttackerId);
                        if (attack.Kind != "overwatch" && attack.AttackerId != null) lastPlaybackActorId = attack.AttackerId;
                        arena.ShowAttack(attack);
                        break;
                    case "actor_moved":
                        var route = message.ToObject<BattleMovementState>();
                        playbackActor = route.Actor;
                        if (route.Actor != null) lastPlaybackActorId = route.Actor.Id;
                        // Реакции известны заранее: маршрут останавливается на клетках выстрелов.
                        foreach (var reaction in interruptions) arena.ShowAttack(reaction);
                        arena.AnimateMovement(route);
                        if (route.Actor != null) SetActorLabel(route.Actor);
                        foreach (var sighting in route.Sightings) SetActorLabel(sighting);
                        break;
                    case "state_update":
                        // Используем именно этот снимок, а не последнее уже полученное состояние.
                        var next = App.Lobby.Battle == message ? App.Lobby.State : message["payload"].ToObject<BattleState>();
                        var previousActorId = Active?.Id;
                        ApplyState(next);
                        if (!next.Ended && Active != null && previousActorId != Active.Id)
                        {
                            if (lastPlaybackActorId != null && lastPlaybackActorId != Active.Id)
                                playbackResumeAt = Time.unscaledTime + ActorChangePause;
                            lastPlaybackActorId = Active.Id;
                        }
                        break;
                    case "game_event": AddEvent((string)message["message"]); break;
                    case "action_result":
                        if ((bool?)message["performed"] == false) ReportActionFailure((string)message["detail"]);
                        break;
                    case "match_result": presentedResult = message.ToObject<MatchResultState>(); break;
                }
                Render();
            }
            if (playbackWasPlaying != Playing)
            {
                playbackWasPlaying = Playing;
                if (!Playing) playbackActor = null;
                SelectDefaultWeapon(); Render();
            }
        }

        private void AddEvent(string message)
        {
            if (string.IsNullOrEmpty(message)) return;
            events.Add(message);
            if (events.Count > 100) events.RemoveAt(0);
            journal.text = string.Join("\n", events.TakeLast(20));
        }

        private void Render()
        {
            if (state == null) { status.text = "Ждём состояние боя…"; return; }
            phase.text = $"Раунд {state.Turn.Number} · " + (arena.IsAnimating && playbackActor != null ? $"Ход: {playbackActor.Name}" :
                state.Ended ? "Матч завершён" : state.Turn.Phase == 2 ? "Ход нейтральных врагов" :
                Active == null ? "Ход противника" : $"Ход: {Active.Name} · ОД {Active.CurrentAp}/{Active.Stats.ActionPoints}");
            status.text = App.Lobby.Error ?? (App.Lobby.Connecting ? "Восстанавливаем соединение…" :
                Playing ? "Проигрываем действия по порядку…" : App.Lobby.ActionNotice ?? "ЛКМ — осмотр · ПКМ — действие · WASD/стрелки — камера · Q/E — поворот · СКМ + мышь — наклон · Колесо — зум");
            reconnect.style.display = !App.Lobby.Connected || App.Lobby.ActionUncertain ? DisplayStyle.Flex : DisplayStyle.None;
            reconnect.SetEnabled(!App.Lobby.Connecting && App.Lobby.Lobby != null);
            RenderInfo(); RenderWeapons();
            var actor = OwnCurrent;
            actionsTitle.text = actor == null ? "Нет живых мехов" : "Действия: " + actor.Name;
            // Неподходящее оружие/AP объясняем по клику, а не только серой кнопкой.
            overwatch.SetEnabled(CanAct);
            endTurn.SetEnabled(CanAct);
            RenderResult();
        }

        private void RenderInfo()
        {
            var actor = InfoActor;
            if (actor == null) { infoName.text = "Нет живых мехов"; infoStats.text = infoParts.text = details.text = ""; detailParts.Clear(); return; }
            infoName.text = actor.Name + (actor.Team == 0 ? " · Нейтрал" : " · Команда " + actor.Team) + (Inspected != null ? " · Осмотр" : "");
            var stats = actor.Stats;
            var movement = actor.SpeedSpent > 0 ? "Движение: использовано" :
                $"Движение: до {Math.Max(0, Math.Min(stats.Speed, actor.CurrentAp))} кл.";
            infoStats.text = $"HP {stats.Health}/{stats.MaxHealth} · AP {actor.CurrentAp}/{stats.ActionPoints} · {movement}\n"
                + $"Точность {stats.Accuracy} · Ближний бой {stats.MeleePower} · Обзор {stats.ViewDistance}" + (actor.Overwatch != null ? " · OVERWATCH" : "");
            infoStats.tooltip = "Одно перемещение за ход; каждая пройденная клетка стоит 1 AP. Атака не расходует возможность перемещения.";
            var mech = actor.Mech;
            infoParts.text = mech == null ? "" : string.Join(" · ", new[] { PartHp("Корпус", mech.Torso), PartHp("Ноги", mech.Legs), PartHp("Голова", mech.Head), PartHp("Л. рука", mech.ArmsLeft), PartHp("П. рука", mech.ArmsRight) });
            RenderDetailParts(actor);
            details.text = "Оружие\n" + string.Join("\n", actor.Inventory.Weapons.Select(item =>
                $"{Hand(item.Hand)}: {item.Name} · урон {item.Damage} · AP {item.CostAp} · дальность {item.Range} · точность {item.Accuracy}%" + (!actor.WeaponUsable(item) ? " · рука уничтожена" : "")))
                + "\n\nНавыки\n" + (actor.Skills.Count == 0 ? "Нет навыков" :
                    string.Join("\n", actor.Skills.Select(skill => $"{skill.Name}: {skill.Description} · шанс {Mathf.RoundToInt(skill.ProcChance * 100)}%")));
        }

        private void RenderDetailParts(BattleActorState actor)
        {
            detailParts.Clear();
            var title = new Label(actor.Name + $" · HP {actor.Stats.Health}/{actor.Stats.MaxHealth}");
            title.AddToClassList("actor-name");
            detailParts.Add(title);
            var mech = actor.Mech;
            if (mech == null)
            {
                detailParts.Add(new Label("У нейтрала нет отдельных частей тела."));
                return;
            }
            foreach (var (slot, part) in new[] { ("Корпус", mech.Torso), ("Ноги", mech.Legs),
                ("Голова", mech.Head), ("Левая рука", mech.ArmsLeft), ("Правая рука", mech.ArmsRight) })
            {
                if (part == null) continue;
                var row = new VisualElement();
                row.AddToClassList("detail-part");
                var heading = new VisualElement();
                heading.AddToClassList("detail-part-heading");
                var name = new Label(slot + " · " + part.Name + (part.Destroyed ? " · Уничтожена" : ""));
                name.AddToClassList("detail-part-name");
                var health = new ProgressBar { pickingMode = PickingMode.Ignore, focusable = false };
                health.AddToClassList("part-health");
                SetActorBar(health, "HP", part.CurrentHealth, part.MaxHealth);
                heading.Add(name); heading.Add(health);
                row.Add(heading);
                var stats = new Label($"Вес {part.Weight} · HP меха +{part.Health} · Скорость {part.Speed} · Точность {part.Accuracy} · Ближний бой {part.MeleePower} · Обзор {part.ViewDistance}");
                stats.AddToClassList("detail-part-stats");
                row.Add(stats);
                detailParts.Add(row);
            }
        }

        private void RenderWeapons()
        {
            weapons.Clear();
            var actor = OwnCurrent;
            if (actor == null) return;
            foreach (var item in actor.Inventory.Weapons)
            {
                var weapon = item;
                var button = new Button(() => { weaponId = weapon.Id; Render(); })
                { text = $"{Hand(weapon.Hand)}: {weapon.Name}\nУрон {weapon.Damage} · AP {weapon.CostAp} · Дальность {weapon.Range}" };
                button.AddToClassList("weapon-button");
                if (weapon.Id == weaponId) button.AddToClassList("selected");
                button.SetEnabled(CanAct && actor.WeaponUsable(weapon));
                if (!actor.WeaponUsable(weapon)) button.tooltip = "Рука уничтожена";
                weapons.Add(button);
            }
        }

        private void RenderResult()
        {
            var result = Result;
            resultPanel.style.display = state.Ended || result != null ? DisplayStyle.Flex : DisplayStyle.None;
            if (!state.Ended && result == null) return;
            var winner = result?.Winner ?? state.Winner;
            resultTitle.text = winner == null ? "Ничья" : winner == ownTeam ? "Победа" : "Поражение";
            resultInfo.text = result == null ? "Получаем результаты и награды…" :
                $"XP: +{result.Xp} · Уровень {result.LevelBefore} → {result.LevelAfter}\n" + (result.Loot == null ? "Деталь не выпала" : "Награда: " + result.Loot.Name);
            if (result != null && loadedResultId != result.MatchId)
            {
                loadedResultId = result.MatchId;
                StartCoroutine(RefreshGarage(result.MatchId));
            }
            if (recoveringGarage) resultInfo.text += "\nОбновляем гараж…";
            if (App.Lobby.Error != null) resultInfo.text += "\n" + App.Lobby.Error;
            resultReconnect.style.display = !App.Lobby.Connected ? DisplayStyle.Flex : DisplayStyle.None;
            resultReconnect.SetEnabled(!App.Lobby.Connecting && App.Lobby.Lobby != null);
            resultGarage.SetEnabled(result != null && !recoveringGarage && !resultBusy);
            resultLobby.SetEnabled(!resultBusy);
            rematch.SetEnabled(result != null && !resultBusy && !recoveringGarage && App.Lobby.Connected && App.Lobby.Lobby?.HostId == App.Session.Pilot.Id);
        }

        private IEnumerator RefreshGarage(string matchId)
        {
            recoveringGarage = true;
            var pilotId = App.Session.Pilot.Id;
            yield return App.Server.GetGarage(pilotId, garage =>
            {
                if (App.Session.Pilot?.Id != pilotId) return;
                App.Session.SetGarage(garage);
                var pilot = App.Session.Pilot;
                pilot.Xp = garage.Xp; pilot.Level = garage.Level;
            }, error => { if (loadedResultId == matchId) AddEvent("Не удалось обновить гараж: " + error); });
            recoveringGarage = false;
            if (visible) Render();
        }

        private IEnumerator Rematch()
        {
            if (resultBusy || App.Lobby.Lobby == null) yield break;
            resultBusy = true; Render();
            var lobbyId = App.Lobby.Lobby.Id;
            yield return App.Server.Rematch(lobbyId, App.Session.Pilot.Id, response =>
            {
                if (!response.Result) AddEvent(response.Detail);
            }, AddEvent);
            resultBusy = false; Render();
        }

        private void Exit(ScreenId destination)
        {
            App.Lobby.Clear();
            ClearPlayback(); presentedResult = null; awaitingSnapshot = true;
            App.Session.InvalidateGarage();
            state = null; inspectedId = lastOwnId = weaponId = weaponActorId = loadedResultId = null;
            events.Clear(); journal.text = "";
            // Гараж всё равно перечитывается при следующем открытии, если награды не загрузились.
            App.Screens.NavigateTo(destination);
        }

        private void Send(BattleActionType type, BattleCell cell)
        {
            if (!CanAct)
            {
                ReportActionFailure(state == null ? "Ждём состояние боя" :
                    state.Ended || Result != null ? "Матч завершён" :
                    App.Lobby.ActionUncertain ? "Подключитесь повторно для обновления состояния" :
                    !App.Lobby.Connected ? "Нет соединения с сервером" :
                    !App.Lobby.SnapshotReady ? "Ждём актуальное состояние боя" :
                    Playing ? "Дождитесь проигрывания действий" :
                    App.Lobby.PendingActionId != null ? "Дождитесь завершения действия" : "Сейчас ход противника");
                return;
            }
            if (cell == null) return;
            if (type == BattleActionType.MOVE && Active.SpeedSpent > 0)
            {
                ReportActionFailure("Перемещение уже использовано");
                return;
            }
            var weapon = SelectedWeapon;
            if (type == BattleActionType.ATTACK || type == BattleActionType.OVERWATCH)
            {
                var reason = weapon == null ? "Нет доступного оружия" :
                    !Active.WeaponUsable(weapon) ? "Рука уничтожена — оружие недоступно" :
                    Active.CurrentAp < weapon.CostAp ? $"Недостаточно AP: нужно {weapon.CostAp}, осталось {Active.CurrentAp}" :
                    type == BattleActionType.OVERWATCH && weapon.Type != "ranged" ? "Для Overwatch нужно дальнобойное оружие" :
                    type == BattleActionType.OVERWATCH && Active.Overwatch != null ? "Мех уже в режиме Overwatch" : null;
                if (reason != null) { ReportActionFailure(reason); return; }
            }
            var action = new BattleActionRequest { Id = Guid.NewGuid().ToString(), ActorId = Active.Id, Type = type, Cell = cell };
            if (type == BattleActionType.ATTACK || type == BattleActionType.OVERWATCH) action.Params = new BattleWeaponParams { WeaponId = weapon.Id };
            App.Lobby.SendAction(action);
        }

        private void Update()
        {
            if (visible) AdvancePlayback();
            if (!visible || state == null || !Application.isFocused) return;
            var mouse = Mouse.current;
            if (mouse == null) return;
            var position = mouse.position.ReadValue();
            var panelPosition = RuntimePanelUtils.ScreenToPanel(root.panel, new Vector2(position.x, Screen.height - position.y));
            var hitUi = root.panel.Pick(panelPosition);
            var overUi = false;
            for (var item = hitUi; item != null; item = item.parent)
                if (item.ClassListContains("battle-ui")) { overUi = true; break; }
            var typing = root.focusController.focusedElement is TextField;
            arena.SetViewport(Mathf.Clamp(hud.worldBound.height / Math.Max(1f, root.worldBound.height), .15f, .4f));
            arena.MoveCamera(!typing && Result == null, !overUi && Result == null);
            hovered = null;
            string actorId = null;
            if (!overUi) arena.Pick(position, out hovered, out actorId);
            if (actorId == null && hovered != null)
                actorId = state.Players.Concat(state.Enemies).FirstOrDefault(actor => actor.Position.X == hovered.X && actor.Position.Y == hovered.Y)?.Id;
            if (!overUi && mouse.leftButton.wasPressedThisFrame)
            {
                inspectedId = actorId; Render();
            }
            if (mouse.rightButton.wasPressedThisFrame && !overUi)
                ActOnCell(hovered, Find(actorId));
            if (Keyboard.current?.escapeKey.wasPressedThisFrame == true)
                detailsPanel.style.display = DisplayStyle.None;
            arena.Mark(hovered, arena.IsAnimating ? playbackActor : Find(Active?.Id), Inspected,
                CanAct && Active.SpeedSpent == 0 ? state.Turn.AvailableMoves : Array.Empty<BattleCell>());
            PositionLabels();
        }

        private void ActOnCell(BattleCell cell, BattleActorState target)
        {
            if (cell == null) return;
            if (!CanAct) { Send(BattleActionType.MOVE, cell); return; }
            if (target != null && (target.Team == 0 || target.Team != Active.Team))
                Send(BattleActionType.ATTACK, target.Position);
            else if (target != null)
                ReportActionFailure(target.Id == Active.Id ? "Мех уже в этой клетке" : "Клетка занята союзником");
            else if (Active.SpeedSpent > 0)
                ReportActionFailure("Перемещение уже использовано");
            else if (state.Turn.AvailableMoves.Any(move => move.X == cell.X && move.Y == cell.Y))
                Send(BattleActionType.MOVE, cell);
            else
                ReportActionFailure(Active.CurrentAp <= 0 ? "Недостаточно AP для движения" :
                    Active.SpeedSpent >= Active.Stats.Speed ? "Запас движения исчерпан" : "Клетка недоступна для движения");
        }

        private void SyncLabels()
        {
            foreach (var actor in state.Players.Concat(state.Enemies))
                SetActorLabel(actor);
        }

        private void SetActorLabel(BattleActorState actor)
        {
            if (!actorLabels.TryGetValue(actor.Id, out var header))
            {
                var container = new VisualElement { pickingMode = PickingMode.Ignore };
                container.AddToClassList("actor-label");
                var name = new Label { pickingMode = PickingMode.Ignore };
                name.AddToClassList("actor-label-name");
                var health = new ProgressBar { pickingMode = PickingMode.Ignore, focusable = false };
                health.AddToClassList("actor-health");
                var ap = new ProgressBar { pickingMode = PickingMode.Ignore, focusable = false };
                ap.AddToClassList("actor-ap");
                container.Add(name); container.Add(health); container.Add(ap);
                labels.Add(container);
                header = (container, name, health, ap);
                actorLabels.Add(actor.Id, header);
            }
            header.name.text = actor.Name;
            SetActorBar(header.health, "HP", actor.Stats.Health, actor.Stats.MaxHealth);
            SetActorBar(header.ap, "AP", actor.CurrentAp, actor.Stats.ActionPoints);
        }

        private static void SetActorBar(ProgressBar bar, string caption, int current, int maximum)
        {
            bar.lowValue = 0;
            bar.highValue = Math.Max(1, maximum);
            bar.value = Mathf.Clamp(current, 0, Math.Max(0, maximum));
            bar.title = $"{caption} {current}/{maximum}";
        }

        private void ShowCombatText(BattleAttackState attack)
        {
            // Не показываем исход для скрытой цели; используем только серверную клетку.
            if (attack.ToCell != null)
            {
                var position = BattleArenaView.Position(attack.ToCell) + Vector3.up * 1.1f;
                ShowFloatingText(attack.Hit ? $"−{attack.Damage}" : "Промах", position, attack.Hit ? "combat-damage" : "combat-miss");
            }
            foreach (var proc in attack.SkillProcs)
            {
                var cell = proc.ActorId == attack.AttackerId ? attack.FromCell :
                    proc.ActorId == attack.TargetId ? attack.ToCell : null;
                if (cell == null) continue;
                ShowFloatingText($"{proc.ActorName}\n{proc.SkillName}", BattleArenaView.Position(cell) + Vector3.up * 1.1f,
                    "combat-skill", 3.2f);
            }
        }

        private void ReportActionFailure(string message)
        {
            if (string.IsNullOrWhiteSpace(message)) message = "Действие недоступно";
            AddEvent(message);
            var actor = OwnCurrent;
            if (actor?.Position == null) return;
            var position = arena.TryGetActorPosition(actor.Id, out var visualPosition) ?
                visualPosition + Vector3.up * .65f : BattleArenaView.Position(actor.Position) + Vector3.up * 1.1f;
            // Повторные клики продлевают одну и ту же подсказку, не забивая экран.
            var existing = combatTexts.FindIndex(item => item.label.ClassListContains("combat-error") &&
                item.label.text == message && (item.position - position).sqrMagnitude < .1f);
            if (existing >= 0)
            {
                var item = combatTexts[existing];
                item.started = Time.unscaledTime;
                combatTexts[existing] = item;
                return;
            }
            ShowFloatingText(message, position, "combat-error", 3.2f);
        }

        private void ShowFloatingText(string text, Vector3 position, string className, float duration = 2.4f)
        {
            var label = new Label(text) { pickingMode = PickingMode.Ignore };
            label.AddToClassList("combat-text");
            label.AddToClassList(className);
            labels.Add(label);
            var offset = combatTexts.Where(item => (item.position - position).sqrMagnitude < .1f)
                .Sum(item => FloatingTextHeight(item.label) + 6f);
            combatTexts.Add((label, position, Time.unscaledTime, offset, duration));
        }

        private static float FloatingTextHeight(Label label) => float.IsNaN(label.resolvedStyle.height) ? 36f : Mathf.Max(36f, label.resolvedStyle.height);

        private void ClearCombatTexts()
        {
            foreach (var item in combatTexts) item.label.RemoveFromHierarchy();
            combatTexts.Clear();
        }

        private void PositionLabels()
        {
            var visibleIds = arena.Figures.Select(figure => figure.Key).ToHashSet();
            foreach (var id in actorLabels.Keys.Where(id => !visibleIds.Contains(id)).ToList())
            {
                actorLabels[id].root.RemoveFromHierarchy();
                actorLabels.Remove(id);
            }
            foreach (var figure in arena.Figures)
            {
                if (!actorLabels.TryGetValue(figure.Key, out var header)) continue;
                var label = header.root;
                var screen = arena.Camera.WorldToScreenPoint(figure.Value.transform.position + Vector3.up * .65f);
                label.style.display = figure.Value.activeSelf && screen.z > 0 && arena.Camera.pixelRect.Contains(new Vector2(screen.x, screen.y)) ? DisplayStyle.Flex : DisplayStyle.None;
                var point = RuntimePanelUtils.ScreenToPanel(root.panel, new Vector2(screen.x, Screen.height - screen.y));
                label.style.left = point.x - 72; label.style.top = point.y - 52;
            }
            for (var index = combatTexts.Count - 1; index >= 0; index--)
            {
                var item = combatTexts[index];
                var age = Time.unscaledTime - item.started;
                if (age >= item.duration)
                {
                    item.label.RemoveFromHierarchy(); combatTexts.RemoveAt(index);
                    continue;
                }
                var screen = arena.Camera.WorldToScreenPoint(item.position);
                item.label.style.display = screen.z > 0 && arena.Camera.pixelRect.Contains(new Vector2(screen.x, screen.y)) ? DisplayStyle.Flex : DisplayStyle.None;
                var point = RuntimePanelUtils.ScreenToPanel(root.panel, new Vector2(screen.x, Screen.height - screen.y));
                item.label.style.left = point.x - 180;
                item.label.style.top = point.y - 54 - FloatingTextHeight(item.label) - age * 24f - item.offset;
                item.label.style.opacity = Mathf.Clamp01((item.duration - age) / .6f);
            }
        }

        private static string Hand(string hand) => hand == "left" ? "Л" : "П";
        private static string PartHp(string name, PartState part) => part == null ? name + ": —" : name + ": " + (part.Destroyed ? "×" : $"{part.CurrentHealth}/{part.MaxHealth}");
    }
}
