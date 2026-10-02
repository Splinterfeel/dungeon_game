using System;

namespace DungeonClient.App
{
    /// <summary>
    /// Хранит текущий экран; визуальные контроллеры подпишутся на это событие.
    /// </summary>
    public sealed class ScreenNavigator
    {
        public ScreenId Current { get; private set; } = ScreenId.PilotSelection;

        public event Action<ScreenId> Changed;

        public void NavigateTo(ScreenId screen)
        {
            if (Current == screen)
            {
                return;
            }

            Current = screen;
            Changed?.Invoke(Current);
        }
    }
}
