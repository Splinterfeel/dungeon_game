using DungeonClient.App;
using UnityEngine;
using UnityEngine.UIElements;

namespace DungeonClient.Screens
{
    [RequireComponent(typeof(UIDocument))]
    public sealed class PilotHubScreen : MonoBehaviour
    {
        [SerializeField]
        private StyleSheet styleSheet;

        private UIDocument document;
        private VisualElement root;
        private VisualElement screenRoot;
        private Label pilotLabel;
        private Label statusLabel;
        private Button garageButton;
        private Button lobbyButton;
        private Button changePilotButton;

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

            screenRoot = root.Q<VisualElement>(className: "hub-shell");
            pilotLabel = root.Q<Label>("HubPilotLabel");
            statusLabel = root.Q<Label>("HubStatusLabel");
            garageButton = root.Q<Button>("OpenGarageButton");
            lobbyButton = root.Q<Button>("OpenLobbyButton");
            changePilotButton = root.Q<Button>("ChangePilotButton");

            garageButton.clicked += OpenGarage;
            lobbyButton.clicked += ShowLobbyPlaceholder;
            changePilotButton.clicked += ChangePilot;
            ClientApp.Instance.Screens.Changed += OnScreenChanged;
            OnScreenChanged(ClientApp.Instance.Screens.Current);
        }

        private void OnDestroy()
        {
            if (garageButton != null)
            {
                garageButton.clicked -= OpenGarage;
            }

            if (lobbyButton != null)
            {
                lobbyButton.clicked -= ShowLobbyPlaceholder;
            }

            if (changePilotButton != null)
            {
                changePilotButton.clicked -= ChangePilot;
            }

            if (ClientApp.Instance != null)
            {
                ClientApp.Instance.Screens.Changed -= OnScreenChanged;
            }
        }

        private void OnScreenChanged(ScreenId screen)
        {
            var visible = screen == ScreenId.PilotHub;
            screenRoot.style.display = visible ? DisplayStyle.Flex : DisplayStyle.None;
            if (!visible)
            {
                return;
            }

            var pilot = ClientApp.Instance.Session.Pilot;
            if (pilot == null)
            {
                ClientApp.Instance.Screens.NavigateTo(ScreenId.PilotSelection);
                return;
            }

            pilotLabel.text = $"Пилот: {pilot.Name} · уровень {pilot.Level} · XP {pilot.Xp}";
            statusLabel.text = "Выбери следующий маршрут.";
        }

        private void OpenGarage()
        {
            ClientApp.Instance.Screens.NavigateTo(ScreenId.Garage);
        }

        private void ShowLobbyPlaceholder()
        {
            statusLabel.text = "Лобби появится на следующем этапе клиента.";
        }

        private void ChangePilot()
        {
            ClientApp.Instance.Screens.NavigateTo(ScreenId.PilotSelection);
        }
    }
}
