using System;
using DungeonClient.Contracts;

namespace DungeonClient.App
{
    /// <summary>
    /// Выбранный локально пилот. Постоянные данные всегда загружаются с сервера.
    /// </summary>
    public sealed class ClientSession
    {
        public PilotSummary Pilot { get; private set; }

        public GarageState Garage { get; private set; }

        public bool HasPilot => Pilot != null;

        public void SelectPilot(PilotSummary pilot)
        {
            if (Pilot?.Id != pilot.Id)
            {
                Garage = null;
            }

            Pilot = pilot;
        }

        public void SetGarage(GarageState garage)
        {
            if (Pilot == null || garage.PlayerId != Pilot.Id)
            {
                throw new InvalidOperationException("Гараж не принадлежит выбранному пилоту");
            }

            Garage = garage;
        }

        public void ClearPilot()
        {
            Pilot = null;
            Garage = null;
        }
    }
}