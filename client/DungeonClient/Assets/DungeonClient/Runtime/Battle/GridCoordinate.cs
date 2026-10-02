using UnityEngine;

namespace DungeonClient.Battle
{
    /// <summary>
    /// Серверная клетка (x, y); в сцене она отображается как (x, 0, y).
    /// </summary>
    public readonly struct GridCoordinate
    {
        public GridCoordinate(int x, int y)
        {
            X = x;
            Y = y;
        }

        public int X { get; }

        public int Y { get; }

        public Vector3 ToWorldPosition(float cellSize = 1f)
        {
            return new Vector3(X * cellSize, 0f, Y * cellSize);
        }
    }
}
