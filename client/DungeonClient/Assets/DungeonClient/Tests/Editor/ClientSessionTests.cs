using System;
using DungeonClient.App;
using DungeonClient.Contracts;
using NUnit.Framework;

namespace DungeonClient.Tests.Editor
{
    public sealed class ClientSessionTests
    {
        [Test]
        public void SetGarage_AcceptsSelectedPilotGarage()
        {
            var session = new ClientSession();
            session.SelectPilot(new PilotSummary { Id = "pilot-1", Name = "Пилот" });
            var garage = new GarageState { PlayerId = "pilot-1" };

            session.SetGarage(garage);

            Assert.That(session.Garage, Is.SameAs(garage));
        }

        [Test]
        public void SetGarage_RejectsAnotherPilotGarage()
        {
            var session = new ClientSession();
            session.SelectPilot(new PilotSummary { Id = "pilot-1", Name = "Пилот" });

            Assert.Throws<InvalidOperationException>(
                () => session.SetGarage(new GarageState { PlayerId = "pilot-2" })
            );
        }
    }
}