using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using DungeonClient.Contracts;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace DungeonClient.Networking
{
    /// <summary>Один сокет комнаты и матча; все уведомления применяются в главном потоке.</summary>
    public sealed class LobbyConnection : MonoBehaviour
    {
        private readonly ConcurrentQueue<Action> pending = new ConcurrentQueue<Action>();
        private ClientWebSocket socket;
        private CancellationTokenSource cancellation;
        private int generation;

        public LobbySummary Lobby { get; private set; }
        public string PilotId { get; private set; }
        public LobbyRoomState Room { get; private set; }
        public JObject Battle { get; private set; }
        public JObject MatchResult { get; private set; }
        public List<JObject> RecentMessages { get; } = new List<JObject>();
        public bool Connected { get; private set; }
        public bool Connecting { get; private set; }
        public string Error { get; private set; }
        public event Action Changed;
        public event Action<JObject> MessageReceived;

        public void Enter(LobbySummary lobby, string pilotId)
        {
            Clear();
            Lobby = lobby;
            PilotId = pilotId;
            Reconnect();
        }

        public void Reconnect()
        {
            if (Lobby == null || Connecting) return;
            StopSocket();
            Connected = false;
            Connecting = true;
            Room = null;
            Error = null;
            Changed?.Invoke();
            socket = new ClientWebSocket();
            cancellation = new CancellationTokenSource();
            var url = ClientAppUrl() + "/ws/" + Uri.EscapeDataString(Lobby.Id)
                + "/" + Uri.EscapeDataString(PilotId);
            _ = Receive(socket, cancellation.Token, generation, url);
        }

        private string ClientAppUrl() => App.ClientApp.Instance.Server.WebSocketUrl;

        private void Enqueue(int version, Action action)
        {
            pending.Enqueue(() => { if (generation == version) action(); });
        }

        private async Task Receive(ClientWebSocket client, CancellationToken token, int version, string url)
        {
            try
            {
                using (var timeout = CancellationTokenSource.CreateLinkedTokenSource(token))
                {
                    timeout.CancelAfter(TimeSpan.FromSeconds(10));
                    await client.ConnectAsync(new Uri(url), timeout.Token).ConfigureAwait(false);
                }
                Enqueue(version, () => { Connecting = false; Connected = true; Changed?.Invoke(); });
                var buffer = new byte[8192];
                while (!token.IsCancellationRequested)
                {
                    using var message = new MemoryStream();
                    WebSocketReceiveResult result;
                    do
                    {
                        result = await client.ReceiveAsync(new ArraySegment<byte>(buffer), token).ConfigureAwait(false);
                        if (result.MessageType == WebSocketMessageType.Close)
                        {
                            var reason = result.CloseStatusDescription ?? "Соединение закрыто сервером";
                            var code = (int?)result.CloseStatus;
                            Enqueue(version, () =>
                            {
                                Connected = false;
                                Connecting = false;
                                Error = reason;
                                // Эти коды означают отсутствие комнаты или участника.
                                if (code == 4001 || code == 4002) { Clear(); Error = reason; }
                                Changed?.Invoke();
                            });
                            return;
                        }
                        if (message.Length + result.Count > 8 * 1024 * 1024)
                            throw new InvalidDataException("Слишком большое сообщение сервера");
                        message.Write(buffer, 0, result.Count);
                    } while (!result.EndOfMessage);
                    var json = JObject.Parse(Encoding.UTF8.GetString(message.ToArray()));
                    Enqueue(version, () => Apply(json));
                }
            }
            catch (Exception exception)
            {
                if (!token.IsCancellationRequested)
                    Enqueue(version, () =>
                    {
                        Connected = false;
                        Connecting = false;
                        Error = "Соединение потеряно: " + exception.Message;
                        Changed?.Invoke();
                    });
            }
            finally { client.Dispose(); }
        }

        private void Apply(JObject message)
        {
            if ((string)message["type"] != "state_update" && (string)message["type"] != "lobby_state")
            {
                RecentMessages.Add(message);
                if (RecentMessages.Count > 100) RecentMessages.RemoveAt(0);
            }
            switch ((string)message["type"])
            {
                case "lobby_state": Room = message["payload"]?.ToObject<LobbyRoomState>(); break;
                case "state_update":
                    Battle = message;
                    if ((bool?)message["payload"]?["ended"] != true)
                        MatchResult = null;
                    break;
                case "match_result": MatchResult = message; break;
                case "lobby_closed":
                    var reason = (string)message["message"];
                    Clear();
                    Error = reason;
                    break;
            }
            MessageReceived?.Invoke(message);
            Changed?.Invoke();
        }

        private void Update()
        {
            while (pending.TryDequeue(out var action))
            {
                try { action(); }
                catch (Exception exception) { Error = "Ошибка сообщения: " + exception.Message; Changed?.Invoke(); }
            }
        }

        private void StopSocket()
        {
            generation++;
            cancellation?.Cancel();
            cancellation?.Dispose();
            cancellation = null;
            try { socket?.Abort(); }
            catch (ObjectDisposedException) { }
            socket = null;
        }

        public void Clear()
        {
            StopSocket();
            Lobby = null;
            PilotId = null;
            Room = null;
            Battle = null;
            MatchResult = null;
            RecentMessages.Clear();
            Connected = false;
            Connecting = false;
            Error = null;
        }

        private void OnDestroy() => StopSocket();
    }
}
