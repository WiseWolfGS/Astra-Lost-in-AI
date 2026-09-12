"""Versioned, code-reviewed deterministic skills. No dynamic code loading."""
from dataclasses import dataclass
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field
from wood_goal import WoodGoal, GoalHalt, choose, inventory


class WoodInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_actions: int = Field(default=3, ge=1, le=3, strict=True)


def wood_preflight(snapshot):
    WoodGoal(None, None, {}, 3).check(snapshot)
    return choose(snapshot["observation"])


def wood_success(record):
    before, after = record.get("before"), record.get("after")
    return bool(before and after and
                inventory(after["observation"]) - inventory(before["observation"]) >= 1)


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
SKILLS = MappingProxyType({WOOD.id: WOOD})


def check_skill(skill, snapshot):
    try:
        first_action = skill.preflight(snapshot)
        return {"id": skill.id, "version": skill.version, "eligible": True,
                "reason": "preconditions_met", "firstAction": first_action,
                "observedAt": snapshot.get("observedAt")}
    except GoalHalt as exc:
        return {"id": skill.id, "version": skill.version, "eligible": False,
                "reason": str(exc), "observedAt": snapshot.get("observedAt")}
