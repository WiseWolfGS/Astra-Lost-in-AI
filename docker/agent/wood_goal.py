"""Deterministic, bounded first skill. No model calls or arbitrary code execution."""
import asyncio
import math
import time

from perception import summarize

LOGS = frozenset("minecraft:" + name + "_log" for name in
                 ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry"))


class GoalHalt(Exception):
    pass


def inventory(observation):
    return sum(stack["count"] for stack in observation["player"].get("inventory", [])
               if stack.get("item") in LOGS)


def choose(observation):
    """Choose only bounded observed candidates; Fabric validates the actual path."""
    summary = summarize(observation)
    if not summary["available"]:
        raise GoalHalt("perception_unavailable")
    position = observation["player"]["position"]
    def distance(pos):
        return math.hypot(pos[0] - position[0], pos[2] - position[2])
    drops = [entity for entity in summary["entities"]
             if entity.get("type") == "minecraft:item" and entity.get("item") in LOGS
             and entity.get("onGround") and entity.get("lineOfSight")
             and distance(entity["position"]) <= 4
             and abs(entity["position"][1] - position[1]) <= 0.5]
    if drops:
        return {"type": "collect", "entityId": min(drops, key=lambda e: distance(e["position"]))["id"],
                "timeoutTicks": 200}
    terrain = observation["environment"]["terrain"]
    origin, palette = terrain["origin"], terrain["palette"]
    blocks = []
    for offset, index in enumerate(terrain["cells"]):
        if index < 0 or palette[index]["id"] not in LOGS:
            continue
        pos = [origin[0] + offset % 9, origin[1] + offset // 81, origin[2] + offset // 9 % 9]
        # Never mine the supporting floor or select logs high in a canopy.
        if math.floor(position[1]) <= pos[1] <= math.floor(position[1]) + 2:
            d = distance([pos[0] + .5, pos[1], pos[2] + .5])
            if d <= 4:
                blocks.append((d, pos))
    if not blocks:
        raise GoalHalt("no_local_log_or_drop")
    _, pos = min(blocks)
    return dict(type="approach", x=pos[0], y=pos[1], z=pos[2], timeoutTicks=200)


class WoodGoal:
    def __init__(self, observe, execute, record, max_actions):
        self.observe, self.execute = observe, execute
        self.record, self.max_actions = record, max_actions
        self.before = None
        self.current = None

    def check(self, snapshot):
        obs = snapshot.get("observation") or {}
        if not snapshot.get("connected") or not obs.get("ready") or obs.get("busy"):
            raise GoalHalt("world_not_ready")
        if time.time() * 1000 - snapshot.get("observedAt", 0) > 3000:
            raise GoalHalt("stale_observation")
        if not {"approach", "mine", "collect"}.issubset(obs.get("capabilities", [])):
            raise GoalHalt("missing_capabilities")
        if self.before:
            original = self.before["observation"]
            if (obs["session"] != original["session"] or
                    obs["player"]["dimension"] != original["player"]["dimension"]):
                raise GoalHalt("world_changed")
            if obs["player"]["health"] < original["player"]["health"]:
                raise GoalHalt("health_decreased")

    async def fresh(self, after):
        for _ in range(16):
            snapshot = await self.observe()
            self.check(snapshot)
            if snapshot["observedAt"] > after:
                self.current = snapshot
                return snapshot
            await asyncio.sleep(.2)
        raise GoalHalt("observation_not_advancing")

    def gained(self):
        delta = inventory(self.current["observation"]) - inventory(self.before["observation"])
        self.record["inventoryDelta"] = delta
        self.record["after"] = self.current
        return delta >= 1

    async def action(self, action):
        if len(self.record["steps"]) >= self.max_actions:
            raise GoalHalt("action_budget_exhausted")
        entry = {"action": action, "before": self.current}
        self.record["steps"].append(entry)
        entry["result"] = await self.execute(action, self.current)
        if entry["result"].get("status") != "completed":
            raise GoalHalt("action_" + entry["result"].get("status", "unknown"))
        # A result and its observation may arrive in adjacent heartbeats. Wait for
        # a heartbeat newer than a snapshot fetched after completion.
        baseline = await self.observe()
        self.check(baseline)
        await self.fresh(baseline["observedAt"])

    async def run(self):
        self.current = await self.observe()
        self.check(self.current)
        self.before = self.current
        self.record["before"] = self.before
        self.record["initialLogCount"] = inventory(self.before["observation"])
        action = choose(self.current["observation"])
        await self.action(action)
        if self.gained():
            return
        if action["type"] == "collect":
            raise GoalHalt("inventory_gain_not_observed")
        target = self.current["observation"].get("environment", {}).get("target", {})
        position = [action[axis] for axis in ("x", "y", "z")]
        if (target.get("type") != "block" or target.get("position") != position or
                target.get("block", {}).get("id") not in LOGS or not target.get("inReach") or
                not target.get("canHarvest") or target.get("hardness", -1) < 0):
            raise GoalHalt("mining_target_not_verified")
        await self.action({**action, "type": "mine"})
        if self.gained():
            return  # Automatic vanilla pickup while mining is valid inventory evidence.
        # Let the drop land; never start a second mining attempt in this run.
        for _ in range(12):
            candidate = None
            try:
                candidate = choose(self.current["observation"])
            except GoalHalt as exc:
                if str(exc) != "no_local_log_or_drop":
                    raise
            if candidate and candidate["type"] == "collect":
                await self.action(candidate)
                if self.gained():
                    return
                raise GoalHalt("inventory_gain_not_observed")
            await asyncio.sleep(.25)
            await self.fresh(self.current["observedAt"])
            if self.gained():
                return
        raise GoalHalt("no_settled_log_drop")
