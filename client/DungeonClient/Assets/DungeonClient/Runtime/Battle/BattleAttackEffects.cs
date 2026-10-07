using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using DungeonClient.Contracts;
using UnityEngine;

namespace DungeonClient.Battle
{
    /// <summary>Короткие эффекты подтверждённых атак; игровые расчёты остаются на сервере.</summary>
    public sealed class BattleAttackEffects : MonoBehaviour
    {
        public event Action<BattleAttackState> AttackPlayed;
        public event Action Cleared;
        private readonly List<BattleAttackState> pending = new();
        private readonly List<BattleAttackState> active = new();
        private readonly HashSet<string> movementIds = new();
        private BattleArenaView arena;
        private Transform effects;
        private Material tracerMaterial, sparkMaterial, missMaterial;
        public bool IsPlaying => pending.Count > 0 || active.Count > 0;

        public void Initialize(BattleArenaView view, Material source, Transform world)
        {
            arena = view;
            effects = new GameObject("AttackEffects").transform;
            effects.SetParent(world, false);
            tracerMaterial = new Material(source) { color = new Color(1f, .96f, .7f) };
            sparkMaterial = new Material(source) { color = new Color(1f, .7f, .16f) };
            missMaterial = new Material(source) { color = new Color(.6f, .65f, .7f) };
        }

        public void Enqueue(BattleAttackState attack)
        {
            if (attack == null || (attack.FromCell == null && attack.ToCell == null)) return;
            pending.Add(attack);
            TryPlayReady();
        }

        public void NotifyMovement(string actionId)
        {
            if (actionId != null) movementIds.Add(actionId);
        }

        public bool ReferencesActor(string id) => id != null &&
            (pending.Any(attack => Uses(attack, id)) || active.Any(attack => Uses(attack, id)));

        public bool PausesActor(string id) => active.Any(attack => Uses(attack, id)) ||
            (pending.Count > 0 && Uses(pending[0], id) &&
                AtCell(id, pending[0].AttackerId == id ? pending[0].FromCell : pending[0].ToCell));

        private static bool Uses(BattleAttackState attack, string id) => attack.AttackerId == id || attack.TargetId == id;

        private bool AtCell(string id, BattleCell cell) => cell == null ||
            !arena.TryGetActorPosition(id, out var position) ||
            Vector2.Distance(new Vector2(position.x, position.z), new Vector2(cell.X, cell.Y)) < .08f;

        public void TryPlayReady()
        {
            if (active.Count > 0 || pending.Count == 0) return;
            var attack = pending[0];
            var routeReady = attack.MovementActionId == null || attack.ToCell == null || movementIds.Contains(attack.MovementActionId);
            // Обычная атака уже дождалась предыдущего действия в общей очереди.
            // Overwatch ждёт точную клетку своего маршрута, без таймера пропуска.
            if (!routeReady || (attack.MovementActionId != null && attack.ToCell != null &&
                (!AtCell(attack.AttackerId, attack.FromCell) || !AtCell(attack.TargetId, attack.ToCell)))) return;
            pending.RemoveAt(0);
            active.Add(attack);
            StartCoroutine(Play(attack));
        }

        private void Update()
        {
            if (effects != null && effects.gameObject.activeInHierarchy) TryPlayReady();
        }

        private LineRenderer Stroke(Transform parent, Material material, Vector3 start, Vector3 end, float width)
        {
            var line = new GameObject("Stroke").AddComponent<LineRenderer>();
            line.transform.SetParent(parent, false);
            line.sharedMaterial = material;
            line.useWorldSpace = true;
            line.positionCount = 2;
            line.SetPosition(0, start); line.SetPosition(1, end);
            line.widthMultiplier = width;
            line.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            line.receiveShadows = false;
            return line;
        }

        private IEnumerator Play(BattleAttackState attack)
        {
            AttackPlayed?.Invoke(attack);
            var root = new GameObject(attack.Kind == "overwatch" ? "OverwatchEffect" : "AttackEffect");
            root.transform.SetParent(effects, false);
            var source = attack.FromCell != null ? BattleArenaView.Position(attack.FromCell) + Vector3.up * .65f : Vector3.zero;
            var target = attack.ToCell != null ? BattleArenaView.Position(attack.ToCell) + Vector3.up * .55f : Vector3.zero;
            var material = attack.Hit ? tracerMaterial : missMaterial;
            LineRenderer beam = null;
            if (attack.FromCell != null && attack.ToCell != null)
            {
                var end = target;
                if (!attack.Hit)
                {
                    var side = Vector3.Cross((target - source).normalized, Vector3.up);
                    end += side * .4f + Vector3.up * .2f;
                }
                beam = Stroke(root.transform, material, source, end, attack.WeaponType == "melee" ? .09f : .045f);
            }
            else if (!attack.Hit && attack.ToCell != null)
            {
                // Промах неизвестного стрелка отмечаем у цели без направления выстрела.
                beam = Stroke(root.transform, missMaterial, target, target, .035f);
                beam.positionCount = 5;
                beam.SetPositions(new[] { target + new Vector3(-.4f, .1f, -.4f), target + new Vector3(.4f, .1f, -.4f),
                    target + new Vector3(.4f, .1f, .4f), target + new Vector3(-.4f, .1f, .4f), target + new Vector3(-.4f, .1f, -.4f) });
            }
            GameObject flash = null;
            if (attack.FromCell != null)
            {
                flash = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                flash.name = attack.WeaponType == "ranged" ? "MuzzleFlash" : "StrikeFlash";
                flash.transform.SetParent(root.transform, false);
                flash.transform.position = source;
                flash.transform.localScale = Vector3.one * .2f;
                var collider = flash.GetComponent<Collider>();
                collider.enabled = false; Destroy(collider);
                var renderer = flash.GetComponent<Renderer>();
                renderer.sharedMaterial = tracerMaterial;
                renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            }
            const float actionDuration = .45f;
            const float sparkDuration = .8f;
            const float trailDuration = .75f;
            var impact = target;
            if (attack.FromCell != null && attack.ToCell != null)
                impact -= (target - source).normalized * .32f;
            var sparks = new List<(LineRenderer line, TrailRenderer trail, Vector3 velocity)>();
            if (attack.Hit && attack.ToCell != null)
                for (var index = 0; index < 24; index++)
                {
                    var direction = UnityEngine.Random.onUnitSphere;
                    direction.y = Mathf.Abs(direction.y) + .25f;
                    var velocity = direction.normalized * UnityEngine.Random.Range(1.8f, 3.2f);
                    var line = Stroke(root.transform, index % 2 == 0 ? sparkMaterial : tracerMaterial,
                        impact, impact + velocity.normalized * .3f, .075f);
                    line.transform.position = impact;
                    var trail = line.gameObject.AddComponent<TrailRenderer>();
                    trail.sharedMaterial = sparkMaterial;
                    trail.time = trailDuration;
                    trail.minVertexDistance = .035f;
                    trail.widthMultiplier = .09f;
                    trail.widthCurve = AnimationCurve.Linear(0, 1, 1, 0);
                    trail.startColor = Color.white;
                    trail.endColor = new Color(1f, .5f, .12f);
                    trail.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                    trail.receiveShadows = false;
                    sparks.Add((line, trail, velocity));
                }
            var duration = sparks.Count > 0 ? sparkDuration + trailDuration : actionDuration;
            var elapsed = 0f;
            var released = false;
            while (elapsed < duration)
            {
                if (beam != null) beam.enabled = elapsed < .18f;
                if (flash != null)
                {
                    flash.SetActive(elapsed < .12f);
                    flash.transform.localScale = Vector3.one * Mathf.Max(0, .2f * (1 - elapsed / .12f));
                }
                foreach (var spark in sparks)
                {
                    var flight = Mathf.Min(elapsed, sparkDuration);
                    var point = impact + spark.velocity * flight + Vector3.down * (2.5f * flight * flight);
                    point.y = Mathf.Max(.04f, point.y);
                    spark.line.transform.position = point;
                    spark.line.SetPosition(0, point);
                    spark.line.SetPosition(1, point + spark.velocity.normalized * .3f * (1 - flight / sparkDuration));
                    spark.line.widthMultiplier = .075f * (1 - flight / sparkDuration);
                    spark.trail.emitting = elapsed < sparkDuration;
                    // После полёта след сужается и исчезает, без новых текстур/материалов.
                    spark.trail.widthMultiplier = .09f * Mathf.Clamp01((duration - elapsed) / trailDuration);
                }
                // Долгий след не держит очередь действий и не останавливает overwatch-маршрут.
                if (!released && elapsed >= actionDuration)
                {
                    active.Remove(attack);
                    released = true;
                }
                elapsed += Time.unscaledDeltaTime;
                yield return null;
            }
            active.Remove(attack);
            Destroy(root);
        }

        public void Clear()
        {
            StopAllCoroutines();
            pending.Clear(); active.Clear(); movementIds.Clear();
            Cleared?.Invoke();
            if (effects != null)
                foreach (Transform child in effects)
                {
                    child.gameObject.SetActive(false);
                    Destroy(child.gameObject);
                }
        }

        private void OnDestroy()
        {
            if (tracerMaterial != null) Destroy(tracerMaterial);
            if (sparkMaterial != null) Destroy(sparkMaterial);
            if (missMaterial != null) Destroy(missMaterial);
        }
    }
}
