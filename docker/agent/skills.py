"""Versioned, code-reviewed deterministic skills. No dynamic code loading."""
from dataclasses import dataclass
from types import MappingProxyType

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from wood_goal import WoodGoal, GoalHalt, choose, inventory
from tool_goal import CraftToolGoal, choose_tool_action, count_tool


class WoodInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_actions: int = Field(default=3, ge=1, le=3, strict=True)


class CraftToolInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipe: Literal["wooden_pickaxe", "wooden_axe", "wooden_sword", "wooden_shovel", "wooden_hoe",
                    "stone_pickaxe", "stone_axe", "stone_sword", "stone_shovel", "stone_hoe"] = "wooden_pickaxe"
    slot: int = Field(default=0, ge=0, le=8, strict=True)
    max_actions: int = Field(default=3, ge=1, le=3, strict=True)


def wood_preflight(snapshot):
    WoodGoal(None, None, {}, 3).check(snapshot)
    return choose(snapshot["observation"])


def wood_success(record):
    before, after = record.get("before"), record.get("after")
    return bool(before and after and
                inventory(after["observation"]) - inventory(before["observation"]) >= 1)


def craft_tool_preflight(snapshot):
    CraftToolGoal(None, None, {}, 3).check(snapshot)
    action = choose_tool_action(snapshot["observation"])
    if action is None:
        return {"type": "select_hotbar", "slot": 0, "expectedItem": "minecraft:wooden_pickaxe"}
    return action


def craft_tool_success(record):
    before, after = record.get("before"), record.get("after")
    if not before or not after:
        return False
    inputs = record.get("skill", {}).get("inputs", {})
    recipe = inputs.get("recipe", "wooden_pickaxe")
    slot = inputs.get("slot", 0)
    tool_id = "minecraft:" + recipe
    after_obs = after.get("observation", {})
    player = after_obs.get("player", {})
    main_hand = player.get("mainHand", {})
    selected_slot = player.get("selectedSlot")
    held = (main_hand.get("item") == tool_id) or (selected_slot == slot and any(s.get("slot") == slot and s.get("item") == tool_id for s in player.get("inventory", [])))
    before_count = count_tool(before.get("observation", {}).get("player", {}).get("inventory", []), tool_id)
    after_count = count_tool(player.get("inventory", []), tool_id)
    return bool(held and (after_count >= before_count or after_count >= 1))


@dataclass(frozen=True)
class Skill:
    id: str
    version: str
    description: str
    required_capabilities: tuple[str, ...]
    timeout_seconds: int
    max_actions: int
    inputs: type[BaseModel]
    runner: type
    preflight: object
    verify: object
    success_reason: str
    goal: str
    preconditions: tuple[str, ...]

    def describe(self):
        return {"id": self.id, "version": self.version, "description": self.description,
                "requiredCapabilities": list(self.required_capabilities),
                "inputSchema": self.inputs.model_json_schema(),
                "budget": {"maxActions": self.max_actions, "timeoutSeconds": self.timeout_seconds,
                           "modelCalls": 0},
                "preconditions": list(self.preconditions),
                "successCondition": self.success_reason}


WOOD = Skill("wood", "1.1.0", "Increase the inventory of ordinary logs by at least one.",
             ("approach", "mine", "collect"), 60, 3, WoodInputs, WoodGoal,
             wood_preflight, wood_success, "log_inventory_increased", "increase_log_inventory_by_one",
             ("ready_idle_world", "observation_age_at_most_3000ms",
              "required_capabilities", "local_log_or_settled_drop"))
CRAFT_TOOL = Skill("craft_tool", "1.0.0",
                   "Craft a tool at a nearby workbench, transfer it to the designated hotbar slot, and select it.",
                   ("craft_workbench", "move_hotbar", "select_hotbar"), 60, 3, CraftToolInputs, CraftToolGoal,
                   craft_tool_preflight, craft_tool_success, "tool_crafted_and_equipped", "craft_and_equip_tool",
                   ("ready_idle_world", "observation_age_at_most_3000ms", "required_capabilities",
                    "nearby_workbench_and_materials"))
SKILLS = MappingProxyType({WOOD.id: WOOD, CRAFT_TOOL.id: CRAFT_TOOL})


def check_skill(skill, snapshot):
    try:
        first_action = skill.preflight(snapshot)
        return {"id": skill.id, "version": skill.version, "eligible": True,
                "reason": "preconditions_met", "firstAction": first_action,
                "observedAt": snapshot.get("observedAt")}
    except GoalHalt as exc:
        return {"id": skill.id, "version": skill.version, "eligible": False,
                "reason": str(exc), "observedAt": snapshot.get("observedAt")}
