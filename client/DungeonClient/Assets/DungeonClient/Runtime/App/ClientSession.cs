using DungeonClient.Contracts;

namespace DungeonClient.App
{
    /// <summary>
    /// Выбранный локально пилот. Постоянные данные всегда загружаются с сервера.
    /// </summary>
    public sealed class ClientSession
    {
        public PilotSummary Pilot { get; private set; }

        public bool HasPilot => Pilot != null;

        public void SelectPilot(PilotSummary pilot)
        {
            Pilot = pilot;
        }

        public void ClearPilot()
        {
            Pilot = null;
        }
    }
}
