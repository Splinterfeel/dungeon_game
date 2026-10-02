using System;

namespace DungeonClient.Networking
{
    public static class ServerEndpoint
    {
        public const string DefaultHttpUrl = "http://127.0.0.1:8000";

        public static string ToWebSocketUrl(string httpUrl)
        {
            var uri = new Uri(httpUrl);
            var builder = new UriBuilder(uri)
            {
                Scheme = uri.Scheme == Uri.UriSchemeHttps ? "wss" : "ws",
            };
            return builder.Uri.ToString().TrimEnd('/');
        }
    }
}
