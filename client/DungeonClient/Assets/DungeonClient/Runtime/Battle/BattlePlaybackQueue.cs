using System.Collections.Generic;
using System.Linq;
using DungeonClient.Contracts;
using Newtonsoft.Json.Linq;

namespace DungeonClient.Battle
{
    /// <summary>Порядок показа сообщений; реакционные выстрелы относятся к своему маршруту.</summary>
    public sealed class BattlePlaybackQueue
    {
        private readonly Queue<JObject> messages = new();
        private readonly List<BattleAttackState> reactions = new();
        public bool Pending => messages.Count > 0 || reactions.Count > 0;
        public string NextActorId
        {
            get
            {
                foreach (var next in messages)
                {
                    var type = (string)next["type"];
                    if (type == "actor_attacked")
                    {
                        if ((string)next["movement_action_id"] != null && next["to_cell"] is JObject)
                            continue;
                        // Реакционный выстрел не является новым ходом своего стрелка.
                        return (string)next["kind"] == "overwatch" ? null : (string)next["attacker_id"];
                    }
                    return type == "actor_moved" ? (string)next["actor"]?["id"] : null;
                }
                return null;
            }
        }

        public void Enqueue(JObject message) => messages.Enqueue(message);

        public bool TryDequeue(out JObject message, out List<BattleAttackState> interruptions)
        {
            message = null;
            interruptions = new();
            while (messages.Count > 0)
            {
                var next = messages.Peek();
                var type = (string)next["type"];
                if (type == "actor_attacked")
                {
                    var attack = next.ToObject<BattleAttackState>();
                    if (attack.MovementActionId != null && attack.ToCell != null)
                    {
                        // Сервер сообщает overwatch до маршрута, рассчитанного по клеткам.
                        reactions.Add(attack);
                        messages.Dequeue();
                        continue;
                    }
                }
                if (type == "state_update" && reactions.Count > 0)
                {
                    // Если видимого маршрута нет, показываем известный выстрел перед снимком.
                    var attack = reactions[0];
                    reactions.RemoveAt(0);
                    attack.MovementActionId = null;
                    message = JObject.FromObject(attack);
                    message["type"] = "actor_attacked";
                    return true;
                }
                message = messages.Dequeue();
                if (type == "actor_moved")
                {
                    var actionId = (string)message["action_id"];
                    interruptions = reactions.Where(attack => attack.MovementActionId == actionId).ToList();
                    reactions.RemoveAll(attack => attack.MovementActionId == actionId);
                }
                return true;
            }
            return false;
        }

        public void Clear()
        {
            messages.Clear();
            reactions.Clear();
        }
    }
}
