using System.Collections.Generic;
using System.Linq;
using DungeonClient.Contracts;
using UnityEngine;
using UnityEngine.InputSystem;

namespace DungeonClient.Battle
{
    /// <summary>Примитивная арена; визуальные позиции не являются игровым состоянием.</summary>
    public sealed class BattleArenaView : MonoBehaviour
    {
        [SerializeField] private Material surfaceMaterial;
        [SerializeField] private Material markerMaterial;
        private readonly List<Material> materials = new();
        private readonly Dictionary<string, GameObject> figures = new();
        private readonly Dictionary<string, Vector3> targets = new();
        private readonly Dictionary<string, Queue<Vector3?>> movement = new();
        private readonly Dictionary<string, float> retiring = new();
        private readonly Dictionary<string, string> sightingRoutes = new();
        private readonly List<BattleCell> moveCells = new();
        private GameObject world, terrain;
        private Camera arenaCamera;
        private BattleAttackEffects attackEffects;
        private BattleMapState map;
        private int viewingTeam;
        private Material floor, wall, blue, red, gray, yellow, white, moveFloor, fogFloor, fogWall, fogMoveFloor;
        private Renderer[,] terrainCells;
        private bool[,] visibleCells;
        private LineRenderer hover, active, inspected;
        private Vector3 focus, cameraVelocity;
        private const float DefaultPitch = 55f;
        private float yaw = 45f, targetYaw = 45f;
        private float pitch = DefaultPitch, targetPitch = DefaultPitch, viewSize = 5f;
        private bool tilting;
        public Camera Camera => arenaCamera;
        public BattleAttackEffects AttackEffects => attackEffects;
        public bool IsAnimating => movement.Values.Any(path => path.Count > 0) ||
            (attackEffects != null && attackEffects.IsPlaying);
        public IEnumerable<KeyValuePair<string, GameObject>> Figures => figures;

        public void Configure(Material surface, Material marker)
        {
            surfaceMaterial = surface;
            markerMaterial = marker;
        }

        private Material ColorMaterial(Material source, Color color, float smoothness = .18f, float metallic = 0f)
        {
            var material = new Material(source) { color = color };
            if (material.HasProperty("_Smoothness")) material.SetFloat("_Smoothness", smoothness);
            if (material.HasProperty("_Metallic")) material.SetFloat("_Metallic", metallic);
            materials.Add(material);
            return material;
        }

        public void Initialize()
        {
            if (world != null) return;
            floor = ColorMaterial(surfaceMaterial, new Color(.17f, .23f, .29f));
            wall = ColorMaterial(surfaceMaterial, new Color(.32f, .36f, .4f));
            blue = ColorMaterial(surfaceMaterial, new Color(.1f, .48f, .95f), .38f, .2f);
            red = ColorMaterial(surfaceMaterial, new Color(.9f, .16f, .16f), .38f, .2f);
            gray = ColorMaterial(surfaceMaterial, new Color(.58f, .58f, .58f), .32f, .15f);
            yellow = ColorMaterial(markerMaterial, new Color(1f, .8f, .12f));
            white = ColorMaterial(markerMaterial, Color.white);
            // Заливка использует существующий пол: сетка остаётся видна без новых мешей.
            moveFloor = ColorMaterial(surfaceMaterial, Color.Lerp(floor.color, new Color(.08f, .48f, 1f), .7f));
            fogFloor = ColorMaterial(surfaceMaterial, floor.color * .2f);
            fogWall = ColorMaterial(surfaceMaterial, wall.color * .2f);
            fogMoveFloor = ColorMaterial(surfaceMaterial, moveFloor.color * .2f);
            world = new GameObject("BattleWorld");
            world.transform.SetParent(transform, false);
            attackEffects = gameObject.AddComponent<BattleAttackEffects>();
            attackEffects.Initialize(this, markerMaterial, world.transform);
            var cameraObject = new GameObject("BattleCamera");
            cameraObject.transform.SetParent(transform, false);
            arenaCamera = cameraObject.AddComponent<Camera>();
            arenaCamera.orthographic = false;
            arenaCamera.fieldOfView = 40f;
            arenaCamera.depth = 10;
            arenaCamera.nearClipPlane = .1f;
            arenaCamera.farClipPlane = 250;
            arenaCamera.clearFlags = CameraClearFlags.SolidColor;
            arenaCamera.backgroundColor = new Color(.035f, .045f, .06f);
            hover = Square("HoverCell", white, .47f);
            active = Ring("ActiveMech", yellow, .46f);
            inspected = Ring("InspectedMech", white, .55f);
            SetVisible(false);
        }

        public void SetVisible(bool visible)
        {
            if (!visible) { tilting = false; cameraVelocity = Vector3.zero; }
            if (!visible) StopMovement();
            if (world != null) world.SetActive(visible);
            if (arenaCamera != null) arenaCamera.enabled = visible;
        }

        private GameObject Primitive(PrimitiveType type, string name, Transform parent, Vector3 position, Vector3 scale, Material material, bool collider)
        {
            var item = GameObject.CreatePrimitive(type);
            item.name = name;
            item.transform.SetParent(parent, false);
            item.transform.position = position;
            item.transform.localScale = scale;
            item.GetComponent<Renderer>().sharedMaterial = material;
            if (!collider)
            {
                var existing = item.GetComponent<Collider>();
                existing.enabled = false;
                Destroy(existing);
            }
            return item;
        }

        public void Apply(BattleState state, int team)
        {
            viewingTeam = team;
            var nextMap = state.Arena.Map;
            // Террейн неизменен внутри матча; новый снимок не пересоздаёт тысячи кубов.
            if (map == null || map.Width != nextMap.Width || map.Height != nextMap.Height ||
                !map.Tiles.SelectMany(column => column).Select(tile => tile == " # ").SequenceEqual(
                    nextMap.Tiles.SelectMany(column => column).Select(tile => tile == " # ")))
                BuildMap(nextMap);
            ApplyVisibility(state.Players.Where(actor => actor.Team == team && actor.Stats.Health > 0).ToList());
            var actors = state.Players.Concat(state.Enemies).Where(actor => actor.Stats.Health > 0).ToList();
            var ids = actors.Select(actor => actor.Id).ToHashSet();
            foreach (var id in figures.Keys.Where(id => !ids.Contains(id)).ToList())
            {
                // Итоговый снимок может уже не содержать погибшего/скрытого актора.
                if (movement[id].Count > 0 || retiring.ContainsKey(id) || sightingRoutes.ContainsKey(id) || attackEffects.ReferencesActor(id))
                    retiring.TryAdd(id, Time.unscaledTime + .15f);
                else RemoveFigure(id);
            }
            foreach (var actor in actors)
            {
                var position = Position(actor.Position) + Vector3.up * .45f;
                if (!figures.TryGetValue(actor.Id, out var figure))
                    figure = CreateFigure(actor, position);
                else if (targets[actor.Id] != position)
                {
                    // Без события маршрута снимок восстанавливает позицию сразу.
                    movement[actor.Id].Clear();
                    figure.transform.position = position;
                    figure.SetActive(true);
                }
                retiring.Remove(actor.Id);
                sightingRoutes.Remove(actor.Id);
                targets[actor.Id] = position;
            }
        }

        private GameObject CreateFigure(BattleActorState actor, Vector3 position)
        {
            var figure = Primitive(PrimitiveType.Cylinder, actor.Name, world.transform, position,
                new Vector3(.6f, .45f, .6f), actor.Team == 1 ? blue : actor.Team == 2 ? red : gray, true);
            figure.AddComponent<BattleActorMarker>().ActorId = actor.Id;
            figures.Add(actor.Id, figure);
            targets.Add(actor.Id, position);
            movement.Add(actor.Id, new Queue<Vector3?>());
            return figure;
        }

        private void RemoveFigure(string id)
        {
            figures[id].SetActive(false);
            Destroy(figures[id]);
            figures.Remove(id); targets.Remove(id); movement.Remove(id); retiring.Remove(id); sightingRoutes.Remove(id);
        }

        public void StopMovement()
        {
            if (attackEffects != null) attackEffects.Clear();
            foreach (var id in retiring.Keys.ToList()) RemoveFigure(id);
            sightingRoutes.Clear();
            foreach (var figure in figures)
            {
                movement[figure.Key].Clear();
                figure.Value.transform.position = targets[figure.Key];
                figure.Value.SetActive(true);
            }
        }

        public void AnimateMovement(BattleMovementState route)
        {
            if (route.Actor == null || route.Paths.Count == 0) return;
            var id = route.Actor.Id;
            var firstCell = route.Paths.FirstOrDefault(path => path.Count > 0)?.First();
            if (firstCell == null) return;
            attackEffects.NotifyMovement(route.ActionId);
            var firstPosition = Position(firstCell) + Vector3.up * .45f;
            if (!figures.ContainsKey(id)) CreateFigure(route.Actor, firstPosition);
            retiring.Remove(id);
            sightingRoutes.Remove(id);
            var steps = movement[id];
            if (route.Actor.Team == viewingTeam)
                foreach (var figure in figures.Where(figure => figure.Key != id))
                    sightingRoutes.TryAdd(figure.Key, id);
            var first = true;
            foreach (var path in route.Paths.Where(path => path.Count > 0))
            {
                var start = Position(path[0]) + Vector3.up * .45f;
                // null разделяет видимые участки: скрытый путь не интерполируем.
                if (!first || targets[id] != start) steps.Enqueue(null);
                foreach (var cell in path) steps.Enqueue(Position(cell) + Vector3.up * .45f);
                targets[id] = Position(path[^1]) + Vector3.up * .45f;
                first = false;
            }
            foreach (var sighting in route.Sightings)
            {
                if (!figures.ContainsKey(sighting.Id))
                    CreateFigure(sighting, Position(sighting.Position) + Vector3.up * .45f);
                sightingRoutes[sighting.Id] = id;
            }
        }

        public void ShowAttack(BattleAttackState attack) => attackEffects.Enqueue(attack);

        public bool TryGetActorPosition(string id, out Vector3 position)
        {
            position = Vector3.zero;
            if (id == null || !figures.TryGetValue(id, out var figure) || !figure.activeSelf) return false;
            position = figure.transform.position;
            return true;
        }

        private void BuildMap(BattleMapState nextMap)
        {
            if (terrain != null) { terrain.SetActive(false); Destroy(terrain); }
            map = nextMap;
            moveCells.Clear();
            terrainCells = new Renderer[map.Width, map.Height];
            visibleCells = new bool[map.Width, map.Height];
            terrain = new GameObject("Terrain");
            terrain.transform.SetParent(world.transform, false);
            for (var x = 0; x < map.Width; x++)
            for (var y = 0; y < map.Height; y++)
            {
                var isFloor = map.IsFloor(x, y);
                terrainCells[x, y] = Primitive(PrimitiveType.Cube, isFloor ? "Floor" : "Wall", terrain.transform,
                    new Vector3(x, isFloor ? -.05f : .45f, y),
                    isFloor ? new Vector3(.96f, .1f, .96f) : new Vector3(1f, .9f, 1f), isFloor ? floor : wall, !isFloor).GetComponent<Renderer>();
                if (isFloor) terrainCells[x, y].shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            }
            ResetCamera();
        }

        private void ApplyVisibility(List<BattleActorState> allies)
        {
            for (var x = 0; x < map.Width; x++)
            for (var y = 0; y < map.Height; y++)
            {
                visibleCells[x, y] = allies.Any(actor => CanSee(actor, x, y));
                terrainCells[x, y].sharedMaterial = TerrainMaterial(x, y);
            }
        }

        private Material TerrainMaterial(int x, int y) => map.IsFloor(x, y) ?
            (visibleCells[x, y] ? floor : fogFloor) : (visibleCells[x, y] ? wall : fogWall);

        private bool CanSee(BattleActorState actor, int targetX, int targetY)
        {
            var startX = actor.Position.X; var startY = actor.Position.Y;
            var dx = Mathf.Abs(targetX - startX); var dy = Mathf.Abs(targetY - startY);
            if (dx * dx + dy * dy > actor.Stats.ViewDistance * actor.Stats.ViewDistance) return false;
            // Брезенхем повторяет src/base.py: старт и конечная клетка не перекрывают луч.
            var x = startX; var y = startY;
            var sx = startX > targetX ? -1 : 1; var sy = startY > targetY ? -1 : 1;
            var error = (dx > dy ? dx : dy) / 2f;
            while (x != targetX || y != targetY)
            {
                if ((x != startX || y != startY) && !map.IsFloor(x, y)) return false;
                if (dx > dy)
                {
                    error -= dy;
                    if (error < 0) { y += sy; error += dx; }
                    x += sx;
                }
                else
                {
                    error -= dx;
                    if (error < 0) { x += sx; error += dy; }
                    y += sy;
                }
            }
            return true;
        }

        public void ResetCamera()
        {
            if (map == null) return;
            cameraVelocity = Vector3.zero;
            focus = new Vector3((map.Width - 1) * .5f, 0, (map.Height - 1) * .5f);
            targetYaw = yaw = 45f;
            targetPitch = pitch = DefaultPitch;
            tilting = false;
            var inverseRotation = Quaternion.Inverse(Quaternion.Euler(pitch, yaw, 0));
            var tanVertical = Mathf.Tan(arenaCamera.fieldOfView * .5f * Mathf.Deg2Rad);
            var tanHorizontal = tanVertical * Mathf.Max(.5f, arenaCamera.aspect);
            var distance = 0f;
            // Все углы объёма карты должны помещаться в перспективную проекцию.
            foreach (var x in new[] { -.5f, map.Width - .5f })
            foreach (var y in new[] { 0f, 1f })
            foreach (var z in new[] { -.5f, map.Height - .5f })
            {
                var corner = inverseRotation * (new Vector3(x, y, z) - focus);
                distance = Mathf.Max(distance, Mathf.Abs(corner.x) / tanHorizontal - corner.z,
                    Mathf.Abs(corner.y) / tanVertical - corner.z);
            }
            viewSize = (distance + 2f) * tanVertical;
            PositionCamera();
        }

        public void StartCamera(BattleCell ownPosition)
        {
            if (map == null) return;
            cameraVelocity = Vector3.zero;
            focus = ownPosition != null ? Position(ownPosition) :
                new Vector3((map.Width - 1) * .5f, 0, (map.Height - 1) * .5f);
            targetYaw = yaw = 45f;
            targetPitch = pitch = DefaultPitch;
            tilting = false;
            viewSize = 5f;
            PositionCamera();
        }

        public void SetViewport(float bottomFraction)
        {
            if (arenaCamera != null) arenaCamera.rect = new Rect(0, bottomFraction, 1, 1 - bottomFraction);
        }

        public void MoveCamera(bool allowKeyboard, bool allowPointer)
        {
            if (map == null || arenaCamera == null) return;
            var keyboard = Keyboard.current;
            var desiredVelocity = Vector3.zero;
            if (allowKeyboard && keyboard != null)
            {
                var x = (keyboard.dKey.isPressed || keyboard.rightArrowKey.isPressed ? 1 : 0) - (keyboard.aKey.isPressed || keyboard.leftArrowKey.isPressed ? 1 : 0);
                var y = (keyboard.wKey.isPressed || keyboard.upArrowKey.isPressed ? 1 : 0) - (keyboard.sKey.isPressed || keyboard.downArrowKey.isPressed ? 1 : 0);
                var right = arenaCamera.transform.right; right.y = 0; right.Normalize();
                var forward = arenaCamera.transform.forward; forward.y = 0; forward.Normalize();
                desiredVelocity = (right * x + forward * y).normalized * Mathf.Max(5, viewSize) * 1.56f;
                if (keyboard.qKey.wasPressedThisFrame) targetYaw += 45;
                if (keyboard.eKey.wasPressedThisFrame) targetYaw -= 45;
            }
            if (!allowKeyboard || keyboard == null) cameraVelocity = Vector3.zero;
            else
            {
                // Короткий разгон и более быстрое торможение без зависимости от FPS.
                var response = desiredVelocity.sqrMagnitude > 0 ? 15f : 20f;
                cameraVelocity = Vector3.Lerp(cameraVelocity, desiredVelocity, 1 - Mathf.Exp(-response * Time.unscaledDeltaTime));
                if (cameraVelocity.sqrMagnitude < .0001f) cameraVelocity = Vector3.zero;
                focus += cameraVelocity * Time.unscaledDeltaTime;
                var clampedX = Mathf.Clamp(focus.x, -3, map.Width + 2);
                var clampedZ = Mathf.Clamp(focus.z, -3, map.Height + 2);
                if (clampedX != focus.x) cameraVelocity.x = 0;
                if (clampedZ != focus.z) cameraVelocity.z = 0;
                focus.x = clampedX; focus.z = clampedZ;
            }
            var mouse = Mouse.current;
            if (!allowKeyboard || mouse == null || !mouse.middleButton.isPressed) tilting = false;
            else if (allowPointer && mouse.middleButton.wasPressedThisFrame && arenaCamera.pixelRect.Contains(mouse.position.ReadValue()))
                tilting = true;
            if (tilting)
                targetPitch = Mathf.Clamp(targetPitch + mouse.delta.ReadValue().y * .15f, 25f, 75f);
            if (allowPointer && mouse != null && mouse.scroll.ReadValue().y != 0)
                viewSize = Mathf.Clamp(viewSize - mouse.scroll.ReadValue().y / 120f * 36f,
                    3f, Mathf.Max(map.Width, map.Height) * 1.3f);
            var smoothing = 1 - Mathf.Exp(-12 * Time.unscaledDeltaTime);
            yaw = Mathf.LerpAngle(yaw, targetYaw, smoothing);
            pitch = Mathf.Lerp(pitch, targetPitch, smoothing);
            PositionCamera();
        }

        private void OnApplicationFocus(bool focused)
        {
            if (!focused) { cameraVelocity = Vector3.zero; tilting = false; }
        }

        private void PositionCamera()
        {
            arenaCamera.transform.rotation = Quaternion.Euler(pitch, yaw, 0);
            var distance = viewSize / Mathf.Tan(arenaCamera.fieldOfView * .5f * Mathf.Deg2Rad);
            arenaCamera.transform.position = focus - arenaCamera.transform.forward * distance;
        }

        public bool Pick(Vector2 screen, out BattleCell cell, out string actorId)
        {
            actorId = null; cell = null;
            if (map == null || !arenaCamera.pixelRect.Contains(screen)) return false;
            var ray = arenaCamera.ScreenPointToRay(screen);
            if (Physics.Raycast(ray, out var hit, 200f))
            {
                var marker = hit.collider.GetComponent<BattleActorMarker>();
                if (marker != null && targets.TryGetValue(marker.ActorId, out var target))
                {
                    actorId = marker.ActorId;
                    cell = new BattleCell(Mathf.RoundToInt(target.x), Mathf.RoundToInt(target.z));
                    return true;
                }
                // Попадание в стену не должно выбирать пол за ней.
                return false;
            }
            if (!new Plane(Vector3.up, Vector3.zero).Raycast(ray, out var distance)) return false;
            var point = ray.GetPoint(distance);
            var x = Mathf.RoundToInt(point.x); var y = Mathf.RoundToInt(point.z);
            if (!map.IsFloor(x, y)) return false;
            cell = new BattleCell(x, y);
            return true;
        }

        public void Mark(BattleCell hovered, BattleActorState current, BattleActorState selection, IEnumerable<BattleCell> available)
        {
            hover.gameObject.SetActive(hovered != null);
            if (hovered != null) hover.transform.position = Position(hovered) + Vector3.up * .025f;
            MarkActor(active, current); MarkActor(inspected, selection);
            foreach (var cell in moveCells)
                terrainCells[cell.X, cell.Y].sharedMaterial = TerrainMaterial(cell.X, cell.Y);
            moveCells.Clear();
            foreach (var cell in available)
            {
                if (!map.IsFloor(cell.X, cell.Y)) continue;
                moveCells.Add(cell);
                terrainCells[cell.X, cell.Y].sharedMaterial = visibleCells[cell.X, cell.Y] ? moveFloor : fogMoveFloor;
            }
        }

        private void MarkActor(LineRenderer line, BattleActorState actor)
        {
            var figure = actor != null && figures.TryGetValue(actor.Id, out var item) ? item : null;
            line.gameObject.SetActive(figure != null && figure.activeSelf);
            if (figure != null) line.transform.position = figure.transform.position - Vector3.up * .415f;
        }

        private LineRenderer Line(string name, Material material, Vector3[] points)
        {
            var item = new GameObject(name); item.transform.SetParent(world.transform, false);
            var line = item.AddComponent<LineRenderer>();
            line.sharedMaterial = material; line.useWorldSpace = false; line.loop = true;
            line.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            line.widthMultiplier = .035f; line.positionCount = points.Length; line.SetPositions(points);
            return line;
        }

        private LineRenderer Square(string name, Material material, float radius) => Line(name, material,
            new[] { new Vector3(-radius, 0, -radius), new Vector3(radius, 0, -radius), new Vector3(radius, 0, radius), new Vector3(-radius, 0, radius) });

        private LineRenderer Ring(string name, Material material, float radius) => Line(name, material,
            Enumerable.Range(0, 32).Select(index => new Vector3(Mathf.Cos(index * Mathf.PI / 16) * radius, 0, Mathf.Sin(index * Mathf.PI / 16) * radius)).ToArray());

        public static Vector3 Position(BattleCell cell) => new GridCoordinate(cell.X, cell.Y).ToWorldPosition();

        private void Update()
        {
            if (world == null || !world.activeSelf) return;
            foreach (var figure in figures)
            {
                if (attackEffects.PausesActor(figure.Key)) continue;
                var path = movement[figure.Key];
                var remaining = Time.unscaledDeltaTime * 6.4f;
                // Маршрут приходит целиком; проигрываем его без промежуточных снимков.
                while (path.Count > 0 && remaining > 0)
                {
                    if (path.Peek() == null)
                    {
                        path.Dequeue();
                        figure.Value.SetActive(false);
                        if (path.Count == 0) break;
                        figure.Value.transform.position = path.Dequeue().Value;
                        figure.Value.SetActive(true);
                        if (retiring.ContainsKey(figure.Key)) retiring[figure.Key] = Time.unscaledTime + .15f;
                        continue;
                    }
                    var next = path.Peek().Value;
                    var distance = Vector3.Distance(figure.Value.transform.position, next);
                    figure.Value.transform.position = Vector3.MoveTowards(figure.Value.transform.position, next, remaining);
                    if (distance > remaining) break;
                    remaining -= distance;
                    path.Dequeue();
                    attackEffects.TryPlayReady();
                    if (attackEffects.PausesActor(figure.Key)) break;
                }
            }
            foreach (var id in retiring.Keys.Where(id => movement[id].Count == 0 &&
                (!sightingRoutes.TryGetValue(id, out var mover) || !movement.TryGetValue(mover, out var path) || path.Count == 0) &&
                !attackEffects.ReferencesActor(id) && Time.unscaledTime >= retiring[id]).ToList())
                RemoveFigure(id);
        }

        private void OnDestroy()
        {
            foreach (var material in materials) Destroy(material);
        }
    }
}
