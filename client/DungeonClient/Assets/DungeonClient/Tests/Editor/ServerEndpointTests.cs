using DungeonClient.Networking;
using NUnit.Framework;

namespace DungeonClient.Tests.Editor
{
    public sealed class ServerEndpointTests
    {
        [Test]
        public void ToWebSocketUrl_ConvertsHttpAndHttps()
        {
            Assert.That(
                ServerEndpoint.ToWebSocketUrl("http://127.0.0.1:8000"),
                Is.EqualTo("ws://127.0.0.1:8000")
            );
            Assert.That(
                ServerEndpoint.ToWebSocketUrl("https://game.example/api/"),
                Is.EqualTo("wss://game.example/api")
            );
        }
    }
}
