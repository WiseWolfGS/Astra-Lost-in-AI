import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
import app as module
from skills import WOOD, check_skill, wood_success
from test_wood_goal import runtime, install, state


def client():
    return TestClient(module.app, headers={"Authorization": "Bearer " + module.TOKEN})


def test_catalog_is_authenticated_and_read_only(runtime, monkeypatch):
    observe = AsyncMock(side_effect=AssertionError("Catalog does not access the world"))
    monkeypatch.setattr(module, "observe", observe)
    assert TestClient(module.app).get("/v1/skills").status_code == 401
    response = client().get("/v1/skills").json()["skills"]
    assert response[0]["id"] == "wood" and response[0]["version"] == "1.1.0"
    assert response[0]["budget"] == {"maxActions": 3, "timeoutSeconds": 60, "modelCalls": 0}
    assert client().get("/v1/skills/wood").json() == response[0]
    assert client().get("/v1/skills/unknown").status_code == 404
    observe.assert_not_awaited()


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
