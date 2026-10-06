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
        private readonly List<(BattleAttackState attack, float received)> pending = new();
        private readonly List<BattleAttackState> active = new();
        private readonly HashSet<string> movementIds = new();
        private BattleArenaView arena;
        private Transform effects;
        private Material tracerMaterial, sparkMaterial, missMaterial;

        public void Initialize(BattleArenaView view, Material source, Transform world)
        {
            arena = view;
            effects = new GameObject("AttackEffects").transform;
            effects.SetParent(world, false);
            tracerMaterial = new Material(source) { color = new Color(1f, .85f, .35f) };
            sparkMaterial = new Material(source) { color = new Color(1f, .45f, .1f) };
            missMaterial = new Material(source) { color = new Color(.6f, .65f, .7f) };
        }

        public void Enqueue(BattleAttackState attack)
        {
            if (attack == null || (attack.FromCell == null && attack.ToCell == null)) return;
            pending.Add((attack, Time.unscaledTime));
            TryPlayReady();
        }

        public void NotifyMovement(string actionId)
        {
            if (actionId != null) movementIds.Add(actionId);
        }

        public bool ReferencesActor(string id) => id != null &&
            (pending.Any(item => Uses(item.attack, id)) || active.Any(attack => Uses(attack, id)));

        public bool PausesActor(string id) => active.Any(attack => Uses(attack, id)) ||
            pending.Any(item => Uses(item.attack, id) &&
                AtCell(id, item.attack.AttackerId == id ? item.attack.FromCell : item.attack.ToCell));

        private static bool Uses(BattleAttackState attack, string id) => attack.AttackerId == id || attack.TargetId == id;

        private bool AtCell(string id, BattleCell cell) => cell == null ||
            !arena.TryGetActorPosition(id, out var position) ||
            Vector2.Distance(new Vector2(position.x, position.z), new Vector2(cell.X, cell.Y)) < .08f;

        public void TryPlayReady()
        {
            for (var index = 0; index < pending.Count;)
            {
                var item = pending[index];
                var attack = item.attack;
                var routeReady = attack.MovementActionId == null || attack.ToCell == null || movementIds.Contains(attack.MovementActionId);
                if ((routeReady && AtCell(attack.AttackerId, attack.FromCell) && AtCell(attack.TargetId, attack.ToCell)) ||
                    Time.unscaledTime - item.received > 5f)
                {
                    pending.RemoveAt(index);
                    active.Add(attack);
                    StartCoroutine(Play(attack));
                }
                else index++;
            }
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
            var sparks = new List<(LineRenderer line, Vector3 velocity)>();
            if (attack.Hit && attack.ToCell != null)
                for (var index = 0; index < 12; index++)
                {
                    var direction = UnityEngine.Random.onUnitSphere;
                    direction.y = Mathf.Abs(direction.y) + .25f;
                    var velocity = direction.normalized * UnityEngine.Random.Range(1.5f, 3f);
                    sparks.Add((Stroke(root.transform, index % 2 == 0 ? sparkMaterial : tracerMaterial,
                        target, target + velocity.normalized * .15f, .035f), velocity));
                }
            const float duration = .4f;
            var elapsed = 0f;
            while (elapsed < duration)
            {
                if (beam != null) beam.enabled = elapsed < .13f;
                if (flash != null)
                {
                    flash.SetActive(elapsed < .12f);
                    flash.transform.localScale = Vector3.one * Mathf.Max(0, .2f * (1 - elapsed / .12f));
                }
                foreach (var spark in sparks)
                {
                    var point = target + spark.velocity * elapsed + Vector3.down * (2f * elapsed * elapsed);
                    spark.line.SetPosition(0, point);
                    spark.line.SetPosition(1, point + spark.velocity.normalized * .15f * (1 - elapsed / duration));
                    spark.line.widthMultiplier = .035f * (1 - elapsed / duration);
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
