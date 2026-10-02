using DungeonClient.Networking;
using UnityEngine;

namespace DungeonClient.App
{
    /// <summary>
    /// Долгоживущая точка входа клиента между сценами.
    /// </summary>
    public sealed class ClientApp : MonoBehaviour
    {
        public static ClientApp Instance { get; private set; }

        public ClientSession Session { get; private set; }

        public ScreenNavigator Screens { get; private set; }

        public ServerApi Server { get; private set; }

        [SerializeField]
        private string serverUrl = ServerEndpoint.DefaultHttpUrl;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }

            Instance = this;
            DontDestroyOnLoad(gameObject);
            Session = new ClientSession();
            Screens = new ScreenNavigator();
            Server = new ServerApi(serverUrl);
            Application.targetFrameRate = 30;
        }
    }
}
