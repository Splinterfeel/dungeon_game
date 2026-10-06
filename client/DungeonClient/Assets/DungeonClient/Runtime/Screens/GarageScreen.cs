using System;
using System.Collections.Generic;
using System.Linq;
using DungeonClient.App;
using DungeonClient.Contracts;
using UnityEngine;
using UnityEngine.UIElements;

namespace DungeonClient.Screens
{
    [RequireComponent(typeof(UIDocument))]
    public sealed class GarageScreen : MonoBehaviour
    {
        private static readonly SlotDefinition[] Slots =
        {
            new("arms", "Руки"),
            new("legs", "Ноги"),
            new("torso", "Корпус"),
            new("head", "Голова"),
        };

        private static readonly ModeDefinition[] ReactorModes =
        {
            new("fortified", "Бронезащита", "+2 HP, −1 AP"),
            new("neutral", "Норма", "без изменений"),
            new("overdrive", "Форсаж", "−2 HP, +1 AP"),
        };

        private static readonly ModeDefinition[] FireControlModes =
        {
            new("precision", "Точная настройка", "+5 точности, −1 урон"),
            new("neutral", "Норма", "без изменений"),
            new("impact", "Форсированный выстрел", "−5 точности, +1 урон"),
        };

        [SerializeField]
        private StyleSheet styleSheet;

        private UIDocument document;
        private VisualElement root;
        private VisualElement screenRoot;
        private Label pilotLabel;
        private Label progressLabel;
        private Label metricsLabel;
        private Label statusLabel;
        private VisualElement loadoutsContainer;
        private Button backButton;
        private Button refreshButton;
        private GarageState garage;
        private string selectedLoadoutId;
        // null означает вкладку тюнинга, остальные значения — слоты деталей.
        private string selectedSlot;
        private string selectedPartId;
        private string selectedSkillKey;
        private bool isPilotTabSelected;
        private bool isRequestRunning;
        private bool reloadBeforeNextMutation;

        private void Awake()
        {
            document = GetComponent<UIDocument>();
        }

        public void SetStyleSheet(StyleSheet value)
        {
            styleSheet = value;
        }

        private void Start()
        {
            root = document.rootVisualElement;
            if (styleSheet != null)
            {
                root.styleSheets.Add(styleSheet);
            }

            screenRoot = root.Q<VisualElement>(className: "garage-shell");
            pilotLabel = root.Q<Label>("GaragePilotLabel");
            progressLabel = root.Q<Label>("GarageProgressLabel");
            metricsLabel = root.Q<Label>("GarageMetricsLabel");
            statusLabel = root.Q<Label>("GarageStatusLabel");
            loadoutsContainer = root.Q<VisualElement>("LoadoutsContainer");
            backButton = root.Q<Button>("BackButton");
            refreshButton = root.Q<Button>("RefreshGarageButton");

            backButton.clicked += Back;
            refreshButton.clicked += Refresh;
            ClientApp.Instance.Screens.Changed += OnScreenChanged;
            OnScreenChanged(ClientApp.Instance.Screens.Current);
        }

        private void OnDestroy()
        {
            if (backButton != null)
            {
                backButton.clicked -= Back;
            }

            if (refreshButton != null)
            {
                refreshButton.clicked -= Refresh;
            }

            if (ClientApp.Instance != null)
            {
                ClientApp.Instance.Screens.Changed -= OnScreenChanged;
            }
        }

        private void OnScreenChanged(ScreenId screen)
        {
            var visible = screen == ScreenId.Garage;
            screenRoot.style.display = visible ? DisplayStyle.Flex : DisplayStyle.None;
            if (!visible)
            {
                return;
            }

            if (ClientApp.Instance.Session.Garage == null)
            {
                Refresh();
                return;
            }

            Render(ClientApp.Instance.Session.Garage);
            SetStatus("Гараж загружен.");
        }

        private void Back()
        {
            if (!isRequestRunning)
            {
                ClientApp.Instance.Screens.NavigateTo(ScreenId.LobbyList);
            }
        }

        private void Refresh()
        {
            var session = ClientApp.Instance.Session;
            if (!session.HasPilot)
            {
                ClientApp.Instance.Screens.NavigateTo(ScreenId.PilotSelection);
                return;
            }

            if (isRequestRunning)
            {
                return;
            }

            SetBusy(true, "Обновляем гараж…");
            StartCoroutine(
                ClientApp.Instance.Server.GetGarage(session.Pilot.Id, OnGarageLoaded, OnRequestFailed)
            );
        }

        private void OnGarageLoaded(GarageState updatedGarage)
        {
            reloadBeforeNextMutation = false;
            ClientApp.Instance.Session.SetGarage(updatedGarage);
            Render(updatedGarage);
            SetBusy(false, "Данные гаража актуальны.");
        }

        private void OnRequestFailed(string error)
        {
            reloadBeforeNextMutation = true;
            SetBusy(false, error);
        }

        private void Render(GarageState updatedGarage)
        {
            garage = updatedGarage;
            EnsureSelection();

            var pilot = ClientApp.Instance.Session.Pilot;
            pilotLabel.text = pilot == null ? "Гараж" : $"Гараж пилота «{pilot.Name}»";
            progressLabel.text = $"Уровень {garage.Level}  ·  XP {garage.Xp}";
            metricsLabel.text = garage.Metrics == null
                ? string.Empty
                : $"Матчей: {garage.Metrics.MatchesFinished}  ·  Наград: {garage.Metrics.RewardsReceived}";

            BuildLoadouts();
        }

        private void BuildLoadouts()
        {
            loadoutsContainer.Clear();
            var tabs = new VisualElement();
            tabs.AddToClassList("loadout-tabs");
            foreach (var loadout in garage.Loadouts)
            {
                var tabLoadout = loadout;
                var tab = new Button(() => SelectLoadout(tabLoadout.Id))
                {
                    text = string.IsNullOrWhiteSpace(tabLoadout.Name) ? "Сборка" : tabLoadout.Name,
                };
                tab.AddToClassList("loadout-tab");
                if (!isPilotTabSelected && tabLoadout.Id == selectedLoadoutId)
                {
                    tab.AddToClassList("is-selected");
                }

                tabs.Add(tab);
            }

            var pilotTab = new Button(SelectPilotTab) { text = "Пилот" };
            pilotTab.AddToClassList("loadout-tab");
            if (isPilotTabSelected)
            {
                pilotTab.AddToClassList("is-selected");
            }

            tabs.Add(pilotTab);

            loadoutsContainer.Add(tabs);
            if (isPilotTabSelected)
            {
                loadoutsContainer.Add(BuildPilotCard());
                return;
            }

            if (garage.Loadouts.Count == 0)
            {
                loadoutsContainer.Add(EmptyState("Сборок пока нет."));
                return;
            }

            loadoutsContainer.Add(BuildLoadoutCard(SelectedLoadout));
        }

        private VisualElement BuildPilotCard()
        {
            var card = new VisualElement();
            card.AddToClassList("loadout-card");
            card.Add(Text("Навыки пилота", "loadout-title"));
            BuildSkills(card);
            return card;
        }

        private VisualElement BuildLoadoutCard(GarageLoadoutState loadout)
        {
            var card = new VisualElement();
            card.AddToClassList("loadout-card");
            var preset = string.IsNullOrWhiteSpace(loadout.PresetName)
                ? loadout.Name
                : $"{loadout.Name} · {loadout.PresetName}";
            card.Add(Text(preset, "loadout-title"));

            if (loadout.Stats != null)
            {
                card.Add(
                    Text(
                        $"HP {loadout.Stats.Health}/{loadout.Stats.MaxHealth}  ·  AP {loadout.Stats.ActionPoints}"
                        + $"  ·  Скорость {loadout.Stats.Speed}  ·  Точность {loadout.Stats.Accuracy}"
                        + $"  ·  Обзор {loadout.Stats.ViewDistance}  ·  Ближний бой {loadout.Stats.MeleePower}",
                        "stats"
                    )
                );
            }

            if (loadout.Mech != null)
            {
                var weaponsWeight = loadout.Weapons.Sum(weapon => weapon.Weight);
                card.Add(
                    Text(
                        $"Вес: {loadout.Mech.PartsWeight + weaponsWeight}/{loadout.Mech.WeightCapacity}"
                        + $" (детали {loadout.Mech.PartsWeight}, оружие {weaponsWeight})",
                        "weight"
                    )
                );
            }

            card.Add(BuildMechTabs());
            if (selectedSlot == null)
            {
                card.Add(BuildTuningControls(loadout));
            }
            else
            {
                card.Add(Text("Установленная деталь", "subsection-title"));
                card.Add(BuildInstalledPart(SelectedSlot, GetInstalledPart(loadout, selectedSlot)));
                if (selectedSlot == "arms")
                {
                    BuildWeapons(card, loadout);
                }
                card.Add(BuildStoredParts());
            }

            return card;
        }

        private static void BuildWeapons(VisualElement card, GarageLoadoutState loadout)
        {
            card.Add(Text("Оружие", "subsection-title"));
            if (loadout.Weapons.Count == 0)
            {
                card.Add(EmptyState("Оружие не установлено."));
            }
            else
            {
                foreach (var weapon in loadout.Weapons)
                {
                    var hand = weapon.Hand == "left" ? "левая" : weapon.Hand == "right" ? "правая" : "—";
                    card.Add(
                        Text(
                            $"{weapon.Name} · рука: {hand} · урон {weapon.Damage} · AP {weapon.CostAp}"
                            + $" · дальность {weapon.Range} · точность {weapon.Accuracy}% · вес {weapon.Weight}",
                            "item-row"
                        )
                    );
                }
            }

        }

        private VisualElement BuildTuningControls(GarageLoadoutState loadout)
        {
            var tuning = new VisualElement();
            tuning.AddToClassList("tuning-controls");
            tuning.Add(Text("Тюнинг", "subsection-title"));
            tuning.Add(
                BuildModeSelector(
                    "Реактор",
                    loadout.ReactorMode,
                    ReactorModes,
                    mode => UpdateTuning(loadout, mode, loadout.FireControlMode)
                )
            );
            tuning.Add(
                BuildModeSelector(
                    "Наведение",
                    loadout.FireControlMode,
                    FireControlModes,
                    mode => UpdateTuning(loadout, loadout.ReactorMode, mode)
                )
            );
            return tuning;
        }

        private static VisualElement BuildModeSelector(
            string title,
            string currentMode,
            IEnumerable<ModeDefinition> modes,
            Action<string> onSelected
        )
        {
            var control = new VisualElement();
            control.AddToClassList("mode-control");
            control.Add(Text(title, "mode-label"));
            var buttons = new VisualElement();
            buttons.AddToClassList("mode-buttons");
            foreach (var mode in modes)
            {
                var modeDefinition = mode;
                var button = new Button(() => onSelected(modeDefinition.Key))
                {
                    text = modeDefinition.Name,
                    tooltip = modeDefinition.Effect,
                };
                button.AddToClassList("mode-button");
                if (modeDefinition.Key == currentMode)
                {
                    button.AddToClassList("is-selected");
                }

                buttons.Add(button);
            }

            control.Add(buttons);
            var selectedMode = modes.FirstOrDefault(mode => mode.Key == currentMode);
            control.Add(Text(selectedMode?.Effect ?? "без изменений", "mode-effect"));
            return control;
        }

        private VisualElement BuildMechTabs()
        {
            var buttons = new VisualElement();
            buttons.AddToClassList("mech-tabs");
            var tuningTab = new Button(() => SelectSlot(null)) { text = "Тюнинг" };
            tuningTab.AddToClassList("mech-tab");
            if (selectedSlot == null)
            {
                tuningTab.AddToClassList("is-selected");
            }
            buttons.Add(tuningTab);
            foreach (var slot in Slots)
            {
                var slotDefinition = slot;
                var button = new Button(() => SelectSlot(slotDefinition.Key))
                {
                    text = slotDefinition.Name,
                };
                button.AddToClassList("mech-tab");
                if (slotDefinition.Key == selectedSlot)
                {
                    button.AddToClassList("is-selected");
                }

                buttons.Add(button);
            }

            return buttons;
        }

        private static VisualElement BuildInstalledPart(SlotDefinition slot, PartState part)
        {
            var row = new VisualElement();
            row.AddToClassList("installed-part");
            row.Add(Text(slot.Name, "part-slot-title"));
            if (part == null)
            {
                row.Add(EmptyState("Не установлено"));
                return row;
            }

            row.Add(Text($"{part.Name} [{TranslateRarity(part.Rarity)}]", "item-row"));
            row.Add(Text(DescribePart(part), "muted"));
            return row;
        }

        private VisualElement BuildStoredParts()
        {
            var storedPartsContainer = new VisualElement();
            storedPartsContainer.AddToClassList("stored-parts");
            storedPartsContainer.Add(Text("Склад · " + SelectedSlot.Name, "subsection-title"));
            var candidates = garage.StoredParts.Where(part => part.Slot == selectedSlot).ToList();
            if (candidates.Count == 0)
            {
                storedPartsContainer.Add(EmptyState("Свободных деталей для этого слота нет."));
                return storedPartsContainer;
            }

            var selectedPart = candidates.FirstOrDefault(part => part.Id == selectedPartId);
            if (selectedPart != null && garage.Loadouts.Count > 0 && !isPilotTabSelected)
            {
                storedPartsContainer.Add(BuildComparison(selectedPart));
            }

            foreach (var part in candidates)
            {
                storedPartsContainer.Add(BuildStoredPart(part));
            }
            return storedPartsContainer;
        }

        private VisualElement BuildStoredPart(PartState part)
        {
            var row = new VisualElement();
            row.AddToClassList("stored-part");
            if (part.Id == selectedPartId)
            {
                row.AddToClassList("is-selected");
            }

            row.Add(Text($"{part.Name} [{TranslateRarity(part.Rarity)}]", "item-title"));
            row.Add(Text(DescribePart(part), "muted"));
            var actions = new VisualElement();
            actions.AddToClassList("part-actions");
            var compareButton = new Button(() => SelectPart(part.Id))
            {
                text = part.Id == selectedPartId ? "Выбрано" : "Сравнить",
            };
            compareButton.AddToClassList("part-action");
            actions.Add(compareButton);
            var equipButton = new Button(() => EquipPart(part)) { text = "Установить" };
            equipButton.AddToClassList("primary-action");
            actions.Add(equipButton);
            row.Add(actions);
            return row;
        }

        private VisualElement BuildComparison(PartState candidate)
        {
            var comparison = new VisualElement();
            comparison.AddToClassList("comparison-panel");
            var installed = GetInstalledPart(SelectedLoadout, selectedSlot);
            comparison.Add(Text("Сравнение деталей", "subsection-title"));
            comparison.Add(Text($"Установлено: {installed?.Name ?? "нет детали"}", "muted"));
            comparison.Add(Text($"Кандидат: {candidate.Name}", "item-row"));
            comparison.Add(ComparisonRow("HP", installed?.Health ?? 0, candidate.Health));
            comparison.Add(ComparisonRow("Скорость", installed?.Speed ?? 0, candidate.Speed));
            comparison.Add(ComparisonRow("Точность", installed?.Accuracy ?? 0, candidate.Accuracy));
            comparison.Add(ComparisonRow("Ближний бой", installed?.MeleePower ?? 0, candidate.MeleePower));
            comparison.Add(ComparisonRow("Обзор", installed?.ViewDistance ?? 0, candidate.ViewDistance));
            comparison.Add(ComparisonRow("Грузоподъёмность", installed?.CarryCapacity ?? 0, candidate.CarryCapacity));
            comparison.Add(ComparisonRow("Вес", installed?.Weight ?? 0, candidate.Weight));
            comparison.Add(Text($"Аффикс: {DescribeAffix(candidate)}. Бонус уже учтён в характеристиках детали.", "muted"));
            return comparison;
        }

        private void BuildSkills(VisualElement container)
        {
            foreach (var skill in garage.OwnedSkills)
            {
                var row = new VisualElement();
                row.AddToClassList("skill-row");
                row.Add(Text($"{skill.Name} · шанс {Mathf.RoundToInt(skill.ProcChance * 100f)}%", "item-title"));
                row.Add(Text($"Условие: {skill.Trigger}", "muted"));
                row.Add(Text(skill.Description, "muted"));
                container.Add(row);
            }

            var pending = garage.PendingSkillChoices.FirstOrDefault();
            if (pending == null)
            {
                if (garage.OwnedSkills.Count == 0)
                {
                    container.Add(EmptyState("Навыки ещё не открыты."));
                }

                return;
            }

            container.Add(Text($"Выбор навыка на уровне {pending.Level}", "subsection-title"));
            if (pending.Options.Count == 0)
            {
                container.Add(EmptyState("Для этого уровня сервер не вернул доступных навыков."));
                return;
            }

            foreach (var skill in pending.Options)
            {
                container.Add(BuildSkillOption(skill));
            }
        }

        private VisualElement BuildSkillOption(SkillState skill)
        {
            var card = new VisualElement();
            card.AddToClassList("skill-row");
            if (skill.SkillKey == selectedSkillKey)
            {
                card.AddToClassList("is-selected");
            }

            card.Add(Text(skill.Name, "item-title"));
            card.Add(Text($"Условие: {skill.Trigger} · шанс {Mathf.RoundToInt(skill.ProcChance * 100f)}%", "muted"));
            card.Add(Text(skill.Description, "muted"));
            var selectButton = new Button(() => SelectSkill(skill.SkillKey))
            {
                text = skill.SkillKey == selectedSkillKey ? "Выбрано" : "Выбрать",
            };
            selectButton.AddToClassList("part-action");
            card.Add(selectButton);
            if (skill.SkillKey == selectedSkillKey)
            {
                var confirmButton = new Button(() => ChooseSkill(skill)) { text = "Подтвердить выбор" };
                confirmButton.AddToClassList("primary-action");
                card.Add(confirmButton);
            }

            return card;
        }

        private void SelectLoadout(string loadoutId)
        {
            if (!isRequestRunning && (isPilotTabSelected || selectedLoadoutId != loadoutId))
            {
                isPilotTabSelected = false;
                selectedLoadoutId = loadoutId;
                selectedPartId = null;
                Render(garage);
            }
        }

        private void SelectPilotTab()
        {
            if (!isRequestRunning && !isPilotTabSelected)
            {
                isPilotTabSelected = true;
                selectedPartId = null;
                Render(garage);
            }
        }

        private void SelectSlot(string slot)
        {
            if (!isRequestRunning && selectedSlot != slot)
            {
                selectedSlot = slot;
                selectedPartId = null;
                Render(garage);
            }
        }

        private void SelectPart(string partId)
        {
            if (!isRequestRunning)
            {
                selectedPartId = partId;
                Render(garage);
            }
        }

        private void SelectSkill(string skillKey)
        {
            if (!isRequestRunning)
            {
                selectedSkillKey = skillKey;
                Render(garage);
            }
        }

        private void UpdateTuning(GarageLoadoutState loadout, string reactorMode, string fireControlMode)
        {
            if (reactorMode == loadout.ReactorMode && fireControlMode == loadout.FireControlMode)
            {
                return;
            }

            if (!BeginMutation("Сохраняем тюнинг…"))
            {
                return;
            }

            StartCoroutine(
                ClientApp.Instance.Server.UpdateGarageTuning(
                    ClientApp.Instance.Session.Pilot.Id,
                    loadout.Id,
                    reactorMode,
                    fireControlMode,
                    updated => OnMutationSucceeded(updated, "Тюнинг сохранён."),
                    OnMutationFailed
                )
            );
        }

        private void EquipPart(PartState part)
        {
            if (!BeginMutation("Устанавливаем деталь…"))
            {
                return;
            }

            StartCoroutine(
                ClientApp.Instance.Server.EquipGaragePart(
                    ClientApp.Instance.Session.Pilot.Id,
                    SelectedLoadout.Id,
                    part.Id,
                    updated => OnMutationSucceeded(updated, "Деталь установлена."),
                    OnMutationFailed
                )
            );
        }

        private void ChooseSkill(SkillState skill)
        {
            if (!BeginMutation("Подтверждаем навык…"))
            {
                return;
            }

            StartCoroutine(
                ClientApp.Instance.Server.ChooseGarageSkill(
                    ClientApp.Instance.Session.Pilot.Id,
                    skill.SkillKey,
                    updated => OnMutationSucceeded(updated, $"Выбран навык «{skill.Name}»."),
                    OnMutationFailed
                )
            );
        }

        private bool BeginMutation(string status)
        {
            if (isRequestRunning)
            {
                return false;
            }

            if (reloadBeforeNextMutation)
            {
                Refresh();
                return false;
            }

            SetBusy(true, status);
            return true;
        }

        private void OnMutationSucceeded(GarageState updatedGarage, string status)
        {
            reloadBeforeNextMutation = false;
            selectedPartId = null;
            selectedSkillKey = null;
            ClientApp.Instance.Session.SetGarage(updatedGarage);
            Render(updatedGarage);
            SetBusy(false, status);
        }

        private void OnMutationFailed(string error)
        {
            reloadBeforeNextMutation = true;
            SetBusy(false, $"{error} Перед следующей командой гараж будет перечитан.");
        }

        private void EnsureSelection()
        {
            if (garage.Loadouts.Count == 0)
            {
                isPilotTabSelected = true;
            }

            if (garage.Loadouts.All(loadout => loadout.Id != selectedLoadoutId))
            {
                selectedLoadoutId = garage.Loadouts.FirstOrDefault()?.Id;
            }

            if (garage.StoredParts.All(part => part.Id != selectedPartId || part.Slot != selectedSlot))
            {
                selectedPartId = null;
            }

            var pending = garage.PendingSkillChoices.FirstOrDefault();
            if (pending == null || pending.Options.All(skill => skill.SkillKey != selectedSkillKey))
            {
                selectedSkillKey = null;
            }
        }

        private void SetBusy(bool value, string message)
        {
            isRequestRunning = value;
            root?.SetEnabled(!value);
            refreshButton?.SetEnabled(!value);
            backButton?.SetEnabled(!value);
            SetStatus(message);
        }

        private void SetStatus(string message)
        {
            if (statusLabel != null)
            {
                statusLabel.text = message;
            }
        }

        private GarageLoadoutState SelectedLoadout => garage.Loadouts.First(loadout => loadout.Id == selectedLoadoutId);

        private SlotDefinition SelectedSlot => Slots.First(slot => slot.Key == selectedSlot);

        private static PartState GetInstalledPart(GarageLoadoutState loadout, string slot)
        {
            if (loadout?.Mech == null)
            {
                return null;
            }

            return slot switch
            {
                "torso" => loadout.Mech.Torso,
                "legs" => loadout.Mech.Legs,
                "arms" => loadout.Mech.ArmsLeft,
                "head" => loadout.Mech.Head,
                _ => null,
            };
        }

        private static Label ComparisonRow(string label, int installed, int candidate)
        {
            var difference = candidate - installed;
            var differenceText = difference > 0 ? $"+{difference}" : difference.ToString();
            return Text($"{label}: {installed} → {candidate} ({differenceText})", "comparison-row");
        }

        private static string DescribePart(PartState part)
        {
            return $"Вес {part.Weight} · HP {part.Health} · скорость {part.Speed} · точность {part.Accuracy}"
                + $" · ближний бой {part.MeleePower} · обзор {part.ViewDistance}"
                + $" · грузоподъёмность {part.CarryCapacity} · {DescribeAffix(part)}";
        }

        private static string DescribeAffix(PartState part)
        {
            return part.AffixTier > 0
                ? $"аффикс +{part.AffixValue} {part.AffixStat}"
                : "без аффикса";
        }

        private static Label Text(string value, string className)
        {
            var label = new Label(value);
            label.AddToClassList(className);
            return label;
        }

        private static Label EmptyState(string value)
        {
            return Text(value, "empty-state");
        }

        private static string TranslateRarity(string rarity)
        {
            return rarity switch
            {
                "rare" => "редкая",
                "epic" => "эпическая",
                "legendary" => "легендарная",
                _ => "обычная",
            };
        }

        private sealed class SlotDefinition
        {
            public SlotDefinition(string key, string name)
            {
                Key = key;
                Name = name;
            }

            public string Key { get; }

            public string Name { get; }
        }

        private sealed class ModeDefinition
        {
            public ModeDefinition(string key, string name, string effect)
            {
                Key = key;
                Name = name;
                Effect = effect;
            }

            public string Key { get; }

            public string Name { get; }

            public string Effect { get; }
        }
    }
}
