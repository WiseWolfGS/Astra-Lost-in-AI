"""Deterministic, bounded tool crafting and equipping skill. No model calls."""
import asyncio
import math
import time

from perception import summarize

TOOL_RECIPES = {
    "wooden_pickaxe": {"material": "planks", "material_count": 3, "sticks": 2},
    "wooden_axe": {"material": "planks", "material_count": 3, "sticks": 2},
    "wooden_sword": {"material": "planks", "material_count": 2, "sticks": 1},
    "wooden_shovel": {"material": "planks", "material_count": 1, "sticks": 2},
    "wooden_hoe": {"material": "planks", "material_count": 2, "sticks": 2},
    "stone_pickaxe": {"material": "stone_tool_materials", "material_count": 3, "sticks": 2},
    "stone_axe": {"material": "stone_tool_materials", "material_count": 3, "sticks": 2},
    "stone_sword": {"material": "stone_tool_materials", "material_count": 2, "sticks": 1},
    "stone_shovel": {"material": "stone_tool_materials", "material_count": 1, "sticks": 2},
    "stone_hoe": {"material": "stone_tool_materials", "material_count": 2, "sticks": 2},
}

PLANKS = frozenset(f"minecraft:{wood}_planks" for wood in
                   ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry"))
STONE_MATERIALS = frozenset({"minecraft:cobblestone", "minecraft:cobbled_deepslate", "minecraft:blackstone"})
STICKS = frozenset({"minecraft:stick"})


class GoalHalt(Exception):
    pass


def count_materials(inventory, material_type):
    if material_type == "planks":
        return sum(stack["count"] for stack in inventory if stack.get("item") in PLANKS)
    elif material_type == "stone_tool_materials":
        return sum(stack["count"] for stack in inventory if stack.get("item") in STONE_MATERIALS)
    elif material_type == "sticks":
        return sum(stack["count"] for stack in inventory if stack.get("item") in STICKS)
    return 0


def count_tool(inventory, tool_id):
    return sum(stack["count"] for stack in inventory if stack.get("item") == tool_id)


def find_workbench_pos(observation):
    target = observation.get("environment", {}).get("target", {})
    if (target.get("type") == "block" and
            target.get("block", {}).get("id") == "minecraft:crafting_table" and
            target.get("inReach")):
        return target.get("position")

    position = observation.get("player", {}).get("position", [0, 0, 0])
    terrain = observation.get("environment", {}).get("terrain", {})
    origin, palette = terrain.get("origin"), terrain.get("palette", [])
    if not origin or not palette:
        return None

    workbench_indices = {i for i, p in enumerate(palette) if p.get("id") == "minecraft:crafting_table"}
    if not workbench_indices:
        return None

    candidates = []
    for offset, index in enumerate(terrain.get("cells", [])):
        if index in workbench_indices:
            pos = [origin[0] + offset % 9, origin[1] + offset // 81, origin[2] + offset // 9 % 9]
            d = math.hypot(pos[0] + 0.5 - position[0], pos[2] + 0.5 - position[2])
            if d <= 4.5 and abs(pos[1] - position[1]) <= 3:
                candidates.append((d, pos))
    if candidates:
        return min(candidates, key=lambda c: c[0])[1]
    return None


def choose_tool_action(observation, recipe="wooden_pickaxe", slot=0):
    tool_id = "minecraft:" + recipe
    player = observation.get("player", {})
    inventory = player.get("inventory", [])
    main_hand = player.get("mainHand", {})
    selected_slot = player.get("selectedSlot")

    # If already held in main hand at target slot, nothing to do
    if main_hand.get("item") == tool_id and selected_slot == slot:
        return None

    # Check if tool is present in inventory
    tool_stacks = [s for s in inventory if s.get("item") == tool_id]
    if tool_stacks:
        # Check if already in target hotbar slot
        if any(s.get("slot") == slot for s in tool_stacks):
            if selected_slot != slot:
                return {"type": "select_hotbar", "slot": slot, "expectedItem": tool_id}
            return None

        # Check if in regular inventory (slots 9..35)
        main_inv_stacks = [s for s in tool_stacks if 9 <= s.get("slot", -1) <= 35]
        if main_inv_stacks:
            src = main_inv_stacks[0]
            target_stack = next((s for s in inventory if s.get("slot") == slot), None)
            target_item = target_stack.get("item", "minecraft:air") if target_stack else "minecraft:air"
            target_count = target_stack.get("count", 0) if target_stack else 0
            return {
                "type": "move_hotbar",
                "sourceSlot": src["slot"],
                "hotbarSlot": slot,
                "expectedSource": tool_id,
                "expectedTarget": target_item,
                "sourceCount": src["count"],
                "targetCount": target_count
            }

        # Tool is in another hotbar slot
        other_hotbar_stacks = [s for s in tool_stacks if 0 <= s.get("slot", -1) <= 8]
        if other_hotbar_stacks:
            other_slot = other_hotbar_stacks[0]["slot"]
            return {"type": "select_hotbar", "slot": other_slot, "expectedItem": tool_id}

    # Tool is not in inventory: craft it at workbench
    spec = TOOL_RECIPES.get(recipe)
    if not spec:
        raise GoalHalt("unsupported_recipe")

    mat_count = count_materials(inventory, spec["material"])
    stick_count = count_materials(inventory, "sticks")
    if mat_count < spec["material_count"] or stick_count < spec["sticks"]:
        raise GoalHalt("insufficient_materials")

    occupied = {s.get("slot") for s in inventory if s.get("count", 0) > 0}
    if len(occupied) >= 36:
        raise GoalHalt("inventory_full")

    wb_pos = find_workbench_pos(observation)
    if not wb_pos:
        raise GoalHalt("aim_at_workbench")

    return {
        "type": "craft_workbench",
        "recipe": recipe,
        "x": wb_pos[0],
        "y": wb_pos[1],
        "z": wb_pos[2]
    }


class CraftToolGoal:
    def __init__(self, observe, execute, record, max_actions, check_cancel=lambda: None,
                 recipe="wooden_pickaxe", slot=0):
        self.observe, self.execute = observe, execute
        self.record, self.max_actions = record, max_actions
        self.check_cancel = check_cancel
        self.recipe = recipe
        self.slot = slot
        self.before = None
        self.current = None

    def check(self, snapshot):
        self.check_cancel()
        obs = snapshot.get("observation") or {}
        if not snapshot.get("connected") or not obs.get("ready") or obs.get("busy"):
            raise GoalHalt("world_not_ready")
        if time.time() * 1000 - snapshot.get("observedAt", 0) > 3000:
            raise GoalHalt("stale_observation")

        required = {"craft_workbench", "move_hotbar", "select_hotbar"}
        if self.recipe.startswith("stone_"):
            required.add("stone_tools")
        if not required.issubset(obs.get("capabilities", [])):
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
            await asyncio.sleep(0.2)
        raise GoalHalt("observation_not_advancing")

    def is_equipped(self, observation):
        tool_id = "minecraft:" + self.recipe
        player = observation.get("player", {})
        main_hand = player.get("mainHand", {})
        selected_slot = player.get("selectedSlot")
        if main_hand.get("item") == tool_id:
            return True
        if selected_slot == self.slot:
            return any(s.get("slot") == self.slot and s.get("item") == tool_id
                       for s in player.get("inventory", []))
        return False

    async def action(self, action):
        self.check_cancel()
        if len(self.record["steps"]) >= self.max_actions:
            raise GoalHalt("action_budget_exhausted")
        entry = {"action": action, "before": self.current}
        self.record["steps"].append(entry)
        entry["result"] = await self.execute(action, self.current)
        self.check_cancel()
        if entry["result"].get("status") != "completed":
            raise GoalHalt("action_" + entry["result"].get("status", "unknown"))
        baseline = await self.observe()
        self.check(baseline)
        await self.fresh(baseline["observedAt"])

    async def run(self):
        self.current = await self.observe()
        self.check(self.current)
        self.before = self.current
        self.record["before"] = self.before
        tool_id = "minecraft:" + self.recipe
        self.record["initialToolCount"] = count_tool(self.before["observation"]["player"].get("inventory", []), tool_id)

        for _ in range(self.max_actions):
            if self.is_equipped(self.current["observation"]):
                break
            action = choose_tool_action(self.current["observation"], self.recipe, self.slot)
            if action is None:
                break
            await self.action(action)
            if self.is_equipped(self.current["observation"]):
                break

        if not self.is_equipped(self.current["observation"]):
            if len(self.record["steps"]) >= self.max_actions:
                raise GoalHalt("action_budget_exhausted")
            raise GoalHalt("tool_not_equipped")
        self.record["after"] = self.current
