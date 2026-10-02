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
        private UIDocument document;
        private VisualElement root;
        private Label pilotLabel;
        private Label progressLabel;
        private Label metricsLabel;
        private Label statusLabel;
        private VisualElement loadoutsContainer;
        private VisualElement storedPartsContainer;
        private VisualElement skillsContainer;
        private Button backButton;
        private Button refreshButton;
        [SerializeField]
        private StyleSheet styleSheet;
        private bool isRequestRunning;

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

            pilotLabel = root.Q<Label>("GaragePilotLabel");
            progressLabel = root.Q<Label>("GarageProgressLabel");
            metricsLabel = root.Q<Label>("GarageMetricsLabel");
            statusLabel = root.Q<Label>("GarageStatusLabel");
            loadoutsContainer = root.Q<VisualElement>("LoadoutsContainer");
            storedPartsContainer = root.Q<VisualElement>("StoredPartsContainer");
            skillsContainer = root.Q<VisualElement>("SkillsContainer");
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
            root.style.display = visible ? DisplayStyle.Flex : DisplayStyle.None;
            if (!visible)
            {
                return;
            }

            if (ClientApp.Instance.Session.Garage != null)
            {
                Render(ClientApp.Instance.Session.Garage);
            }
            else
            {
                Refresh();
            }
        }

        private void Back()
        {
            if (!isRequestRunning)
            {
                ClientApp.Instance.Screens.NavigateTo(ScreenId.PilotSelection);
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
                ClientApp.Instance.Server.GetGarage(
                    session.Pilot.Id,
                    OnGarageLoaded,
                    OnRequestFailed
                )
            );
        }

        private void OnGarageLoaded(GarageState garage)
        {
            ClientApp.Instance.Session.SetGarage(garage);
            Render(garage);
            SetBusy(false, "Данные гаража актуальны.");
        }

        private void OnRequestFailed(string error)
        {
            SetBusy(false, error);
        }

        private void SetBusy(bool value, string message)
        {
            isRequestRunning = value;
            refreshButton?.SetEnabled(!value);
            backButton?.SetEnabled(!value);
            statusLabel.text = message;
        }

        private void Render(GarageState garage)
        {
            var pilot = ClientApp.Instance.Session.Pilot;
            pilotLabel.text = pilot == null ? "Гараж" : $"Гараж пилота «{pilot.Name}»";
            progressLabel.text = $"Уровень {garage.Level}  ·  XP {garage.Xp}";
            metricsLabel.text = garage.Metrics == null
                ? string.Empty
                : $"Матчей: {garage.Metrics.MatchesFinished}  ·  Наград: {garage.Metrics.RewardsReceived}";

            loadoutsContainer.Clear();
            foreach (var loadout in garage.Loadouts)
            {
                loadoutsContainer.Add(BuildLoadoutCard(loadout));
            }

            if (garage.Loadouts.Count == 0)
            {
                loadoutsContainer.Add(EmptyState("Сборок пока нет."));
            }

            storedPartsContainer.Clear();
            if (garage.StoredParts.Count == 0)
            {
                storedPartsContainer.Add(EmptyState("Свободных деталей пока нет."));
            }
            else
            {
                foreach (var part in garage.StoredParts)
                {
                    storedPartsContainer.Add(BuildStoredPart(part));
                }
            }

            skillsContainer.Clear();
            foreach (var skill in garage.OwnedSkills)
            {
                var row = new VisualElement();
                row.AddToClassList("skill-row");
                row.Add(Text($"{skill.Name} · шанс {Mathf.RoundToInt(skill.ProcChance * 100f)}%", "item-title"));
                row.Add(Text(skill.Description, "muted"));
                skillsContainer.Add(row);
            }

            foreach (var pending in garage.PendingSkillChoices)
            {
                skillsContainer.Add(
                    EmptyState(
                        $"На уровне {pending.Level} доступен выбор: "
                        + string.Join(", ", pending.Options.Select(option => option.Name))
                    )
                );
            }

            if (garage.OwnedSkills.Count == 0 && garage.PendingSkillChoices.Count == 0)
            {
                skillsContainer.Add(EmptyState("Навыки ещё не открыты."));
            }

            SetBusy(false, "Гараж загружен.");
        }

        private static VisualElement BuildLoadoutCard(GarageLoadoutState loadout)
        {
            var card = new VisualElement();
            card.AddToClassList("loadout-card");
            var preset = string.IsNullOrWhiteSpace(loadout.PresetName)
                ? loadout.Name
                : $"{loadout.Name} · {loadout.PresetName}";
            card.Add(Text(preset, "loadout-title"));
            card.Add(
                Text(
                    $"Реактор: {TranslateMode(loadout.ReactorMode)}  ·  Огонь: {TranslateMode(loadout.FireControlMode)}",
                    "muted"
                )
            );

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
                card.Add(Text("Детали", "subsection-title"));
                card.Add(BuildPartRow("Корпус", loadout.Mech.Torso));
                card.Add(BuildPartRow("Ноги", loadout.Mech.Legs));
                card.Add(BuildPartRow("Левая рука", loadout.Mech.ArmsLeft));
                card.Add(BuildPartRow("Правая рука", loadout.Mech.ArmsRight));
                card.Add(BuildPartRow("Голова", loadout.Mech.Head));
            }

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

            return card;
        }

        private static VisualElement BuildPartRow(string slot, PartState part)
        {
            if (part == null)
            {
                return EmptyState($"{slot}: не установлено");
            }

            var affix = part.AffixTier > 0
                ? $" · аффикс +{part.AffixValue} {part.AffixStat}"
                : string.Empty;
            return Text(
                $"{slot}: {part.Name} [{TranslateRarity(part.Rarity)}] · вес {part.Weight}{affix}",
                "item-row"
            );
        }

        private static VisualElement BuildStoredPart(PartState part)
        {
            var row = new VisualElement();
            row.AddToClassList("stored-part");
            row.Add(Text($"{part.Name} [{TranslateRarity(part.Rarity)}]", "item-title"));
            row.Add(
                Text(
                    $"Слот: {TranslateSlot(part.Slot)} · вес {part.Weight}"
                    + $" · HP +{part.Health} · скорость +{part.Speed} · точность +{part.Accuracy}",
                    "muted"
                )
            );
            return row;
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

        private static string TranslateMode(string mode)
        {
            return mode switch
            {
                "fortified" => "защита",
                "overdrive" => "форсаж",
                "precision" => "точность",
                "impact" => "мощность",
                _ => "нейтральный",
            };
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

        private static string TranslateSlot(string slot)
        {
            return slot switch
            {
                "torso" => "корпус",
                "legs" => "ноги",
                "arms" => "руки",
                "head" => "голова",
                _ => slot,
            };
        }
    }
}