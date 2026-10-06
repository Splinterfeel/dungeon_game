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
        private VisualElement root, shell, hud, weapons, labels, detailsPanel, resultPanel;
        private Label phase, infoName, infoStats, infoParts, status, actionsTitle, details, journal, resultTitle, resultInfo;
        private Button overwatch, endTurn, reconnect, resultGarage, resultLobby, rematch, resultReconnect;
        private BattleArenaView arena;
        private BattleState state;
        private readonly List<string> events = new();
        private readonly Dictionary<string, Label> actorLabels = new();
        private readonly List<(Label label, Vector3 position, float started, float offset)> combatTexts = new();
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
        private MatchResultState Result => App.Lobby.Outcome;
        private bool CanAct => state != null && !state.Ended && Result == null && Active?.OwnerId == App.Session.Pilot?.Id &&
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
            visible = screen == ScreenId.Battle || screen == ScreenId.MatchResult;
            shell.style.display = visible ? DisplayStyle.Flex : DisplayStyle.None;
            arena.SetVisible(visible);
            if (visible)
            {
                if (state == null)
                    foreach (var message in App.Lobby.RecentMessages.Where(message => (string)message["type"] == "game_event"))
                        AddEvent((string)message["message"]);
                OnConnection();
            }
        }

        private BattleActorState Find(string id) => id == null || state == null ? null :
            state.Players.Concat(state.Enemies).FirstOrDefault(actor => actor.Id == id && actor.Stats.Health > 0);

        private void OnConnection()
        {
            if (!visible) return;
            if (!App.Lobby.SnapshotReady) arena.StopMovement();
            var next = App.Lobby.State;
            if (next != null && !ReferenceEquals(next, state))
            {
                var wasEnded = state?.Ended == true || loadedResultId != null;
                var startingMatch = state == null || (wasEnded && !next.Ended && App.Lobby.MatchResult == null);
                state = next;
                if (wasEnded && !state.Ended && App.Lobby.MatchResult == null)
                {
                    inspectedId = null; weaponId = null; weaponActorId = null; loadedResultId = null;
                    resultBusy = false; events.Clear();
                }
                var own = state.Players.FirstOrDefault(actor => actor.OwnerId == App.Session.Pilot?.Id);
                if (own != null) ownTeam = own.Team;
                if (Active?.OwnerId == App.Session.Pilot?.Id) lastOwnId = Active.Id;
                if (Find(inspectedId) == null) inspectedId = null;
                if (startingMatch) arena.StopMovement();
                arena.Apply(state, ownTeam);
                if (startingMatch) arena.StartCamera(OwnCurrent?.Position);
                SyncLabels();
            }
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
            if ((string)message["type"] == "actor_attacked")
                arena.ShowAttack(message.ToObject<BattleAttackState>());
            if ((string)message["type"] == "actor_moved")
            {
                var route = message.ToObject<BattleMovementState>();
                arena.AnimateMovement(route);
                if (route.Actor != null) SetActorLabel(route.Actor);
                foreach (var sighting in route.Sightings) SetActorLabel(sighting);
            }
            if ((string)message["type"] == "game_event") AddEvent((string)message["message"]);
            if ((string)message["type"] == "action_result" && (bool?)message["performed"] == false)
                AddEvent((string)message["detail"]);
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
            phase.text = $"Раунд {state.Turn.Number} · " + (state.Ended ? "Матч завершён" : state.Turn.Phase == 2 ? "Ход нейтральных врагов" :
                Active == null ? "Ход противника" : $"Ход: {Active.Name} · ОД {Active.CurrentAp}/{Active.Stats.ActionPoints}");
            status.text = App.Lobby.Error ?? App.Lobby.ActionNotice ?? (App.Lobby.Connecting ? "Восстанавливаем соединение…" : "ЛКМ — осмотр · ПКМ — действие · WASD/стрелки — камера · Q/E — поворот · СКМ + мышь — наклон · Колесо — зум");
            reconnect.style.display = !App.Lobby.Connected || App.Lobby.ActionUncertain ? DisplayStyle.Flex : DisplayStyle.None;
            reconnect.SetEnabled(!App.Lobby.Connecting && App.Lobby.Lobby != null);
            RenderInfo(); RenderWeapons();
            var actor = OwnCurrent; var weapon = SelectedWeapon;
            actionsTitle.text = actor == null ? "Нет живых мехов" : "Действия: " + actor.Name;
            overwatch.SetEnabled(CanAct && weapon?.Type == "ranged" && actor.WeaponUsable(weapon) && actor.CurrentAp >= weapon.CostAp && actor.Overwatch == null);
            endTurn.SetEnabled(CanAct);
            RenderResult();
        }

        private void RenderInfo()
        {
            var actor = InfoActor;
            if (actor == null) { infoName.text = "Нет живых мехов"; infoStats.text = infoParts.text = details.text = ""; return; }
            infoName.text = actor.Name + (actor.Team == 0 ? " · Нейтрал" : " · Команда " + actor.Team) + (Inspected != null ? " · Осмотр" : "");
            var stats = actor.Stats;
            infoStats.text = $"HP {stats.Health}/{stats.MaxHealth} · AP {actor.CurrentAp}/{stats.ActionPoints} · Движение {Math.Max(0, stats.Speed - actor.SpeedSpent)}/{stats.Speed}\n"
                + $"Точность {stats.Accuracy} · Ближний бой {stats.MeleePower} · Обзор {stats.ViewDistance}" + (actor.Overwatch != null ? " · OVERWATCH" : "");
            var mech = actor.Mech;
            infoParts.text = mech == null ? "" : string.Join(" · ", new[] { PartHp("Корпус", mech.Torso), PartHp("Ноги", mech.Legs), PartHp("Голова", mech.Head), PartHp("Л. рука", mech.ArmsLeft), PartHp("П. рука", mech.ArmsRight) });
            details.text = actor.Name + "\n\n" + string.Join("\n", actor.Inventory.Weapons.Select(item =>
                $"{Hand(item.Hand)}: {item.Name} · урон {item.Damage} · AP {item.CostAp} · дальность {item.Range} · точность {item.Accuracy}%" + (!actor.WeaponUsable(item) ? " · рука уничтожена" : "")))
                + "\n\n" + string.Join("\n", actor.Skills.Select(skill => $"{skill.Name}: {skill.Description} · шанс {Mathf.RoundToInt(skill.ProcChance * 100)}%"));
            if (mech != null)
                details.text += "\n\n" + string.Join("\n", new[] { mech.Torso, mech.Legs, mech.Head, mech.ArmsLeft, mech.ArmsRight }.Where(part => part != null).Select(part =>
                    $"{part.Name}: {part.CurrentHealth}/{part.MaxHealth} · вес {part.Weight} · HP {part.Health} · скорость {part.Speed} · точность {part.Accuracy} · ближний бой {part.MeleePower} · обзор {part.ViewDistance}"));
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
            App.Session.InvalidateGarage();
            state = null; inspectedId = lastOwnId = weaponId = weaponActorId = loadedResultId = null;
            events.Clear(); journal.text = "";
            // Гараж всё равно перечитывается при следующем открытии, если награды не загрузились.
            App.Screens.NavigateTo(destination);
        }

        private void Send(BattleActionType type, BattleCell cell)
        {
            if (!CanAct || cell == null) return;
            var weapon = SelectedWeapon;
            if ((type == BattleActionType.ATTACK || type == BattleActionType.OVERWATCH) &&
                (weapon == null || !Active.WeaponUsable(weapon) || Active.CurrentAp < weapon.CostAp)) return;
            var action = new BattleActionRequest { Id = Guid.NewGuid().ToString(), ActorId = Active.Id, Type = type, Cell = cell };
            if (type == BattleActionType.ATTACK || type == BattleActionType.OVERWATCH) action.Params = new BattleWeaponParams { WeaponId = weapon.Id };
            App.Lobby.SendAction(action);
        }

        private void Update()
        {
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
            arena.Mark(hovered, Find(Active?.Id), Inspected, CanAct ? state.Turn.AvailableMoves : Array.Empty<BattleCell>());
            PositionLabels();
        }

        private void ActOnCell(BattleCell cell, BattleActorState target)
        {
            if (!CanAct || cell == null) return;
            if (target != null && (target.Team == 0 || target.Team != Active.Team))
                Send(BattleActionType.ATTACK, target.Position);
            else if (target == null && state.Turn.AvailableMoves.Any(move => move.X == cell.X && move.Y == cell.Y))
                Send(BattleActionType.MOVE, cell);
        }

        private void SyncLabels()
        {
            foreach (var actor in state.Players.Concat(state.Enemies))
                SetActorLabel(actor);
        }

        private void SetActorLabel(BattleActorState actor)
        {
            if (!actorLabels.TryGetValue(actor.Id, out var label))
            {
                label = new Label { pickingMode = PickingMode.Ignore };
                label.AddToClassList("actor-label"); labels.Add(label); actorLabels.Add(actor.Id, label);
            }
            label.text = actor.Name + "\n" + actor.Stats.Health + "/" + actor.Stats.MaxHealth;
            if (actor.Id == Active?.Id) label.text += $" · ОД {actor.CurrentAp}/{actor.Stats.ActionPoints}";
        }

        private void ShowCombatText(BattleAttackState attack)
        {
            // Не показываем исход для скрытой цели; используем только серверную клетку.
            if (attack.ToCell == null) return;
            var position = BattleArenaView.Position(attack.ToCell) + Vector3.up * 1.1f;
            var label = new Label(attack.Hit ? $"−{attack.Damage}" : "Промах") { pickingMode = PickingMode.Ignore };
            label.AddToClassList("combat-text");
            label.AddToClassList(attack.Hit ? "combat-damage" : "combat-miss");
            labels.Add(label);
            var offset = combatTexts.Count(item => (item.position - position).sqrMagnitude < .1f) * 28f;
            combatTexts.Add((label, position, Time.unscaledTime, offset));
        }

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
                actorLabels[id].RemoveFromHierarchy();
                actorLabels.Remove(id);
            }
            foreach (var figure in arena.Figures)
            {
                if (!actorLabels.TryGetValue(figure.Key, out var label)) continue;
                var screen = arena.Camera.WorldToScreenPoint(figure.Value.transform.position + Vector3.up * .65f);
                label.style.display = figure.Value.activeSelf && screen.z > 0 && arena.Camera.pixelRect.Contains(new Vector2(screen.x, screen.y)) ? DisplayStyle.Flex : DisplayStyle.None;
                var point = RuntimePanelUtils.ScreenToPanel(root.panel, new Vector2(screen.x, Screen.height - screen.y));
                label.style.left = point.x - 90; label.style.top = point.y - 30;
            }
            for (var index = combatTexts.Count - 1; index >= 0; index--)
            {
                var item = combatTexts[index];
                var age = Time.unscaledTime - item.started;
                const float duration = 1.2f;
                if (age >= duration)
                {
                    item.label.RemoveFromHierarchy(); combatTexts.RemoveAt(index);
                    continue;
                }
                var screen = arena.Camera.WorldToScreenPoint(item.position);
                item.label.style.display = screen.z > 0 && arena.Camera.pixelRect.Contains(new Vector2(screen.x, screen.y)) ? DisplayStyle.Flex : DisplayStyle.None;
                var point = RuntimePanelUtils.ScreenToPanel(root.panel, new Vector2(screen.x, Screen.height - screen.y));
                item.label.style.left = point.x - 90;
                item.label.style.top = point.y - 45 - age * 38f - item.offset;
                item.label.style.opacity = Mathf.Clamp01((duration - age) / .4f);
            }
        }

        private static string Hand(string hand) => hand == "left" ? "Л" : "П";
        private static string PartHp(string name, PartState part) => part == null ? name + ": —" : name + ": " + (part.Destroyed ? "×" : $"{part.CurrentHealth}/{part.MaxHealth}");
    }
}
