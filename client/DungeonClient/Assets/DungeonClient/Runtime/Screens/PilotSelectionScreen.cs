using System.Collections;
using System.Collections.Generic;
using DungeonClient.App;
using DungeonClient.Contracts;
using UnityEngine;
using UnityEngine.UIElements;

namespace DungeonClient.Screens
{
    /// <summary>
    /// Временный вход: выбор существующего постоянного профиля или создание нового.
    /// </summary>
    [RequireComponent(typeof(UIDocument))]
    public sealed class PilotSelectionScreen : MonoBehaviour
    {
        private const string LastPilotIdKey = "dungeon-client.last-pilot-id";

        private UIDocument document;
        private Label statusLabel;
        private Label selectedPilotLabel;
        private Label garageSummaryLabel;
        private ScrollView pilotList;
        private TextField newPilotName;
        private Button refreshButton;
        private Button createPilotButton;
        [SerializeField]
        private StyleSheet styleSheet;
        private bool isRequestRunning;
        private List<PilotSummary> pilots = new();

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
            var root = document.rootVisualElement;
            if (styleSheet != null)
            {
                root.styleSheets.Add(styleSheet);
            }

            statusLabel = root.Q<Label>("StatusLabel");
            selectedPilotLabel = root.Q<Label>("SelectedPilotLabel");
            garageSummaryLabel = root.Q<Label>("GarageSummaryLabel");
            pilotList = root.Q<ScrollView>("PilotList");
            newPilotName = root.Q<TextField>("NewPilotName");
            refreshButton = root.Q<Button>("RefreshPilotsButton");
            createPilotButton = root.Q<Button>("CreatePilotButton");

            refreshButton.clicked += RefreshPilots;
            createPilotButton.clicked += CreatePilot;
            RefreshPilots();
        }

        private void OnDestroy()
        {
            if (refreshButton != null)
            {
                refreshButton.clicked -= RefreshPilots;
            }

            if (createPilotButton != null)
            {
                createPilotButton.clicked -= CreatePilot;
            }
        }

        private void RefreshPilots()
        {
            if (isRequestRunning)
            {
                return;
            }

            SetBusy(true, "Загружаем список пилотов…");
            StartCoroutine(ClientApp.Instance.Server.GetPilots(OnPilotsLoaded, OnRequestFailed));
        }

        private void OnPilotsLoaded(List<PilotSummary> loadedPilots)
        {
            pilots = loadedPilots;
            pilotList.Clear();
            foreach (var pilot in pilots)
            {
                var button = new Button(() => SelectPilot(pilot))
                {
                    text = $"{pilot.Name}  ·  Ур. {pilot.Level}  ·  матчей: {pilot.MatchesFinished}",
                };
                button.AddToClassList("pilot-button");
                pilotList.Add(button);
            }

            if (pilots.Count == 0)
            {
                pilotList.Add(new Label("Сохранённых пилотов пока нет."));
            }

            SetBusy(false, "Выбери пилота или создай нового.");
            RestoreLastPilot();
        }

        private void RestoreLastPilot()
        {
            if (ClientApp.Instance.Session.HasPilot)
            {
                return;
            }

            var lastPilotId = PlayerPrefs.GetString(LastPilotIdKey, string.Empty);
            foreach (var pilot in pilots)
            {
                if (pilot.Id == lastPilotId)
                {
                    SelectPilot(pilot);
                    return;
                }
            }
        }

        private void SelectPilot(PilotSummary pilot)
        {
            if (isRequestRunning)
            {
                return;
            }

            ClientApp.Instance.Session.SelectPilot(pilot);
            PlayerPrefs.SetString(LastPilotIdKey, pilot.Id);
            PlayerPrefs.Save();
            selectedPilotLabel.text = $"Пилот: {pilot.Name} · уровень {pilot.Level} · XP {pilot.Xp}";
            SetBusy(true, "Загружаем гараж…");
            StartCoroutine(ClientApp.Instance.Server.GetGarage(pilot.Id, ShowGarage, OnRequestFailed));
        }

        private void CreatePilot()
        {
            var name = newPilotName.value?.Trim();
            if (string.IsNullOrWhiteSpace(name))
            {
                statusLabel.text = "Введи имя нового пилота.";
                return;
            }

            if (isRequestRunning)
            {
                return;
            }

            SetBusy(true, "Создаём пилота и стартовые сборки…");
            StartCoroutine(
                ClientApp.Instance.Server.CreatePilot(
                    name,
                    garage => OnPilotCreated(name, garage),
                    OnRequestFailed
                )
            );
        }

        private void OnPilotCreated(string name, GarageState garage)
        {
            newPilotName.value = string.Empty;
            var pilot = new PilotSummary
            {
                Id = garage.PlayerId,
                Name = name,
                Xp = garage.Xp,
                Level = garage.Level,
                MatchesFinished = 0,
            };
            ClientApp.Instance.Session.SelectPilot(pilot);
            PlayerPrefs.SetString(LastPilotIdKey, pilot.Id);
            PlayerPrefs.Save();
            selectedPilotLabel.text = $"Пилот: {pilot.Name} · уровень {pilot.Level} · XP {pilot.Xp}";
            ShowGarage(garage);
            RefreshPilots();
        }

        private void ShowGarage(GarageState garage)
        {
            var loadoutNames = new List<string>();
            foreach (var loadout in garage.Loadouts)
            {
                var preset = string.IsNullOrWhiteSpace(loadout.PresetName)
                    ? loadout.Name
                    : $"{loadout.Name} ({loadout.PresetName})";
                loadoutNames.Add(preset);
            }

            garageSummaryLabel.text = loadoutNames.Count == 0
                ? "В гараже пока нет сборок."
                : $"Гараж: {string.Join("  ·  ", loadoutNames)}";
            SetBusy(false, "Профиль загружен. Следующий экран — лобби.");
        }

        private void OnRequestFailed(string error)
        {
            SetBusy(false, error);
        }

        private void SetBusy(bool value, string message)
        {
            isRequestRunning = value;
            refreshButton?.SetEnabled(!value);
            createPilotButton?.SetEnabled(!value);
            statusLabel.text = message;
        }
    }
}
