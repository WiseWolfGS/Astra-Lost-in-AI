import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
import app as module
from skills import WOOD, CRAFT_TOOL, check_skill, wood_success, craft_tool_success
from test_wood_goal import runtime, install, state
from test_tool_goal import tool_state


def client():
    return TestClient(module.app, headers={"Authorization": "Bearer " + module.TOKEN})


def test_catalog_is_authenticated_and_read_only(runtime, monkeypatch):
    observe = AsyncMock(side_effect=AssertionError("Catalog does not access the world"))
    monkeypatch.setattr(module, "observe", observe)
    assert TestClient(module.app).get("/v1/skills").status_code == 401
    response = client().get("/v1/skills").json()["skills"]
    assert len(response) == 2
    assert response[0]["id"] == "wood" and response[0]["version"] == "1.1.0"
    assert response[0]["budget"] == {"maxActions": 3, "timeoutSeconds": 60, "modelCalls": 0}
    assert response[1]["id"] == "craft_tool" and response[1]["version"] == "1.0.0"
    assert response[1]["budget"] == {"maxActions": 3, "timeoutSeconds": 60, "modelCalls": 0}
    assert client().get("/v1/skills/wood").json() == response[0]
    assert client().get("/v1/skills/craft_tool").json() == response[1]
    assert client().get("/v1/skills/unknown").status_code == 404
    observe.assert_not_awaited()


def test_craft_tool_inputs_validation(runtime, monkeypatch):
    assert client().post("/v1/skills/craft_tool/run",
                         json={"version": "1.0.0", "inputs": {"slot": 9}}).status_code == 422
    assert client().post("/v1/skills/craft_tool/run",
                         json={"version": "1.0.0", "inputs": {"recipe": "diamond_pickaxe"}}).status_code == 422
    assert client().post("/v1/skills/craft_tool/run",
                         json={"version": "1.0.0", "inputs": {"max_actions": 4}}).status_code == 422


def test_craft_tool_run_and_evidence(runtime, monkeypatch, tmp_path):
    s0 = tool_state(recipe="wooden_pickaxe", tool_slot=None, planks=3, sticks=2, selected_slot=1)
    s1 = tool_state(recipe="wooden_pickaxe", tool_slot=9, planks=0, sticks=0, selected_slot=1)
    s2 = tool_state(recipe="wooden_pickaxe", tool_slot=0, planks=0, sticks=0, selected_slot=1)
    s3 = tool_state(recipe="wooden_pickaxe", tool_slot=0, planks=0, sticks=0, selected_slot=0)

    execute = install(monkeypatch, [s0, s1, s2, s3])
    result = client().post("/v1/skills/craft_tool/run", json={
        "version": "1.0.0",
        "inputs": {"recipe": "wooden_pickaxe", "slot": 0, "max_actions": 3}
    }).json()

    assert result["result"]["status"] == "completed"
    assert result["result"]["reason"] == "tool_crafted_and_equipped"
    assert execute.await_count == 3
    assert result["skill"]["id"] == "craft_tool"
    assert result["skill"]["version"] == "1.0.0"

    persisted = json.loads((tmp_path / "episodes.jsonl").read_text().splitlines()[0])
    assert persisted["skill"] == result["skill"]


def test_craft_tool_success_requires_equipped_evidence():
    s_before = tool_state(recipe="wooden_pickaxe", tool_slot=None, planks=3, sticks=2)
    s_after_not_held = tool_state(recipe="wooden_pickaxe", tool_slot=9, planks=0, sticks=0, selected_slot=1)
    s_after_held = tool_state(recipe="wooden_pickaxe", tool_slot=0, planks=0, sticks=0, selected_slot=0)

    rec = {"skill": {"inputs": {"recipe": "wooden_pickaxe", "slot": 0}},
           "before": s_before, "after": s_after_not_held}
    assert not craft_tool_success(rec)

    rec["after"] = s_after_held
    assert craft_tool_success(rec)


@pytest.mark.parametrize("inputs", [{"max_actions": 4}, {"max_actions": True},
                                       {"max_actions": "2"}, {"code": "anything"}])
def test_invalid_inputs_cannot_dispatch(runtime, monkeypatch, inputs):
    execute = install(monkeypatch, [state()])
    assert client().post("/v1/skills/wood/run", json={"version": "1.1.0", "inputs": inputs}).status_code == 422
    execute.assert_not_awaited()


def test_version_and_unknown_skill_fail_before_observation(runtime, monkeypatch):
    observe = AsyncMock(side_effect=AssertionError("No world access"))
    monkeypatch.setattr(module, "observe", observe)
    assert client().post("/v1/skills/wood/run", json={"version": "2.0.0"}).status_code == 409
    assert client().post("/v1/skills/missing/run", json={"version": "1.1.0"}).status_code == 404
    assert client().post("/v1/skills/wood/run", json={}).status_code == 422
    observe.assert_not_awaited()


def test_preflight_reports_conditions_without_action(runtime, monkeypatch):
    execute = install(monkeypatch, [state(drop=True)])
    check = client().get("/v1/skills/wood/check").json()
    assert check["eligible"] and check["firstAction"]["type"] == "collect"
    execute.assert_not_awaited()
    missing = state()
    missing["observation"]["capabilities"] = []
    assert check_skill(WOOD, missing)["reason"] == "missing_capabilities"
    assert check_skill(WOOD, state(log=False))["reason"] == "no_local_log_or_drop"
    stale = state()
    stale["observedAt"] -= 4000
    assert check_skill(WOOD, stale)["reason"] == "stale_observation"


def test_versioned_run_persists_evidence_and_legacy_matches(runtime, monkeypatch, tmp_path):
    execute = install(monkeypatch, [state(drop=True), state(count=6)])
    result = client().post("/v1/skills/wood/run", json={"version": "1.1.0", "inputs": {"max_actions": 1}}).json()
    assert result["result"]["status"] == "completed"
    assert execute.await_count == 1
    assert result["skill"] == {"id": "wood", "version": "1.1.0", "inputs": {"max_actions": 1}}
    assert result["observationSchemaVersion"] == 1
    persisted = json.loads((tmp_path / "episodes.jsonl").read_text().splitlines()[0])
    assert persisted["skill"] == result["skill"] and persisted["inventoryDelta"] == 1
    install(monkeypatch, [state(drop=True), state(count=6)])
    legacy = asyncio.run(module.wood(module.WoodRequest(max_actions=1)))
    assert legacy["skill"] == result["skill"] and legacy["result"] == result["result"]


def test_success_requires_inventory_evidence():
    assert not wood_success({"inventoryDelta": 1})
    assert not wood_success({"before": state(), "after": state(), "inventoryDelta": 1})
    assert wood_success({"before": state(), "after": state(count=6)})


def test_run_rechecks_after_preflight_and_preserves_lock(runtime, monkeypatch):
    install(monkeypatch, [state(drop=True)])
    assert client().get("/v1/skills/wood/check").json()["eligible"]
    execute = install(monkeypatch, [state(log=False)])
    result = client().post("/v1/skills/wood/run", json={"version": "1.1.0"}).json()
    assert result["result"]["reason"] == "no_local_log_or_drop"
    execute.assert_not_awaited()
    asyncio.run(module.step_lock.acquire())
    try:
        assert client().post("/v1/skills/wood/run", json={"version": "1.1.0"}).status_code == 409
    finally:
        module.step_lock.release()
