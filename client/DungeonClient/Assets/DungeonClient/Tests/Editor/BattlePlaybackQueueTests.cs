using DungeonClient.Battle;
using DungeonClient.Contracts;
using Newtonsoft.Json.Linq;
using NUnit.Framework;

namespace DungeonClient.Tests.Editor
{
    public sealed class BattlePlaybackQueueTests
    {
        private static JObject Message(string type, string id = null) => new()
        {
            ["type"] = type,
            ["action_id"] = id,
        };

        private static JObject Reaction(string id, string attackId, bool visibleTarget = true)
        {
            var message = JObject.FromObject(new BattleAttackState
            {
                AttackId = attackId,
                MovementActionId = id,
                ToCell = visibleTarget ? new BattleCell(3, 2) : null,
                FromCell = new BattleCell(5, 2),
                Kind = "overwatch",
            });
            message["type"] = "actor_attacked";
            return message;
        }

        [Test]
        public void ActionsSnapshotsAndResultKeepServerOrder()
        {
            var queue = new BattlePlaybackQueue();
            var messages = new[]
            {
                Message("actor_moved", "enemy-1-move"), Message("state_update"),
                Message("actor_attacked"), Message("state_update"),
                Message("actor_moved", "neutral-1-move"), Message("state_update"),
                Message("match_result"),
            };
            foreach (var message in messages) queue.Enqueue(message);
            foreach (var expected in messages)
            {
                Assert.That(queue.TryDequeue(out var actual, out var reactions), Is.True);
                Assert.That(actual, Is.SameAs(expected));
                Assert.That(reactions, Is.Empty);
            }
            Assert.That(queue.Pending, Is.False);
        }

        [Test]
        public void OverwatchWaitsForRouteAndKeepsReactionOrder()
        {
            var queue = new BattlePlaybackQueue();
            queue.Enqueue(Reaction("move-1", "shot-1"));
            Assert.That(queue.TryDequeue(out _, out _), Is.False);
            Assert.That(queue.Pending, Is.True);
            queue.Enqueue(Reaction("move-1", "shot-2"));
            var route = Message("actor_moved", "move-1");
            queue.Enqueue(route);
            queue.Enqueue(Message("state_update"));
            Assert.That(queue.TryDequeue(out var actual, out var reactions), Is.True);
            Assert.That(actual, Is.SameAs(route));
            Assert.That(reactions.ConvertAll(attack => attack.AttackId), Is.EqualTo(new[] { "shot-1", "shot-2" }));
            Assert.That(queue.TryDequeue(out actual, out reactions), Is.True);
            Assert.That((string)actual["type"], Is.EqualTo("state_update"));
            Assert.That(reactions, Is.Empty);
            Assert.That(queue.Pending, Is.False);
        }

        [Test]
        public void AttackWithNoVisibleMovingTargetDoesNotWaitForHiddenRoute()
        {
            var queue = new BattlePlaybackQueue();
            var reaction = Reaction("hidden-move", "shot", false);
            queue.Enqueue(reaction);
            Assert.That(queue.TryDequeue(out var actual, out var reactions), Is.True);
            Assert.That(actual, Is.SameAs(reaction));
            Assert.That(reactions, Is.Empty);
            Assert.That(queue.Pending, Is.False);
        }

        [Test]
        public void MissingRouteFallsBackToKnownAttackBeforeSnapshot()
        {
            var queue = new BattlePlaybackQueue();
            queue.Enqueue(Reaction("missing-move", "shot"));
            var snapshot = Message("state_update");
            queue.Enqueue(snapshot);
            Assert.That(queue.TryDequeue(out var actual, out _), Is.True);
            Assert.That((string)actual["type"], Is.EqualTo("actor_attacked"));
            Assert.That(actual.ToObject<BattleAttackState>().MovementActionId, Is.Null);
            Assert.That(queue.TryDequeue(out actual, out _), Is.True);
            Assert.That(actual, Is.SameAs(snapshot));
            Assert.That(queue.Pending, Is.False);
        }

        [Test]
        public void ResyncDiscardsBufferedReactionsAndMessages()
        {
            var queue = new BattlePlaybackQueue();
            queue.Enqueue(Reaction("old-move", "old-shot"));
            Assert.That(queue.TryDequeue(out _, out _), Is.False);
            queue.Enqueue(Message("state_update"));
            queue.Clear();
            Assert.That(queue.Pending, Is.False);
            Assert.That(queue.TryDequeue(out _, out _), Is.False);
            queue.Enqueue(Message("actor_moved", "old-move"));
            Assert.That(queue.TryDequeue(out _, out var reactions), Is.True);
            Assert.That(reactions, Is.Empty);
        }

        [Test]
        public void NextActorKeepsMessagesAndGroupsOverwatchWithItsMovingActor()
        {
            var queue = new BattlePlaybackQueue();
            var reaction = Reaction("move-1", "shot-1");
            reaction["attacker_id"] = "watcher";
            var route = Message("actor_moved", "move-1");
            route["actor"] = new JObject { ["id"] = "mover" };
            var attack = Message("actor_attacked");
            attack["attacker_id"] = "next-mech";
            queue.Enqueue(reaction);
            queue.Enqueue(route);
            queue.Enqueue(Message("state_update"));
            queue.Enqueue(attack);

            Assert.That(queue.NextActorId, Is.EqualTo("mover"));
            Assert.That(queue.NextActorId, Is.EqualTo("mover"));
            Assert.That(queue.TryDequeue(out var actual, out var reactions), Is.True);
            Assert.That(actual, Is.SameAs(route));
            Assert.That(reactions.Count, Is.EqualTo(1));
            Assert.That(queue.NextActorId, Is.Null);
            Assert.That(queue.TryDequeue(out actual, out _), Is.True);
            Assert.That((string)actual["type"], Is.EqualTo("state_update"));
            Assert.That(queue.NextActorId, Is.EqualTo("next-mech"));
            queue.Clear();
            Assert.That(queue.NextActorId, Is.Null);
        }
    }
}
