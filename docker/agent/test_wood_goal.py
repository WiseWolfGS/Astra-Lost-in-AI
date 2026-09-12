import asyncio
from copy import deepcopy
import time
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
import app as module
from test_perception import fixture_observation
from wood_goal import choose, GoalHalt


def state(count=5, drop=False, log=True):
    obs = fixture_observation()
    obs.update(ready=True, busy=False, session="wood", capabilities=["approach", "mine", "collect"])
    obs["player"].update(health=20, dimension="minecraft:overworld",
                         inventory=[{"item": "minecraft:oak_log", "count": count}])
    terrain = obs["environment"]["terrain"]
    terrain["cells"] = [0] * 486
    terrain["palette"].append(dict(terrain["palette"][1], id="minecraft:oak_log"))
    if log:
        terrain["cells"][205] = 3  # (2,70,-1), 3 blocks horizontally
    obs["environment"]["target"] = {"type": "block", "position": [2,70,-1],
        "block": {"id": "minecraft:oak_log"}, "inReach": True, "canHarvest": True, "hardness": 2}
    if drop:
        obs["environment"]["entities"] = [{"id": 42, "type": "minecraft:item", "item": "minecraft:oak_log",
            "position": [1.5,70,-.5], "onGround": True, "lineOfSight": True}]
    return {"connected": True, "observedAt": time.time()*1000, "observation": obs}


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "DATA", tmp_path)
    monkeypatch.setattr(module, "step_lock", asyncio.Lock())
    def forbidden(*args, **kwargs):
        raise AssertionError("No paid model calls in wood skill")
    monkeypatch.setattr(module, "ChatOpenAI", forbidden)
    monkeypatch.setattr(module, "DRY_RUN", False)


def install(monkeypatch, states, outcomes=None):
    stage = 0
    clock = time.time()*1000
    async def observe():
        nonlocal clock
        clock += 1
        snapshot = deepcopy(states[min(stage, len(states)-1)])
        snapshot["observedAt"] = clock
        return snapshot
    async def execute(action, before):
        nonlocal stage
        stage += 1
        return (outcomes or {}).get(stage, {"status": "completed"})
    mock = AsyncMock(side_effect=execute)
    monkeypatch.setattr(module, "observe", observe)
    monkeypatch.setattr(module, "execute_action", mock)
    return mock


def run(max_actions=3):
    return asyncio.run(module.wood(module.WoodRequest(max_actions=max_actions)))


def test_full_chain_and_persistent_evidence(runtime, monkeypatch, tmp_path):
    mock = install(monkeypatch, [state(), state(), state(drop=True, log=False), state(count=6, log=False)])
    result = run()
    assert result["result"]["reason"] == "log_inventory_increased"
    assert [call.args[0].type for call in mock.await_args_list] == ["approach", "mine", "collect"]
    assert result["initialLogCount"] == 5 and result["inventoryDelta"] == 1
    assert result["model_called"] is False
    assert (tmp_path / "episodes.jsonl").exists()


def test_drop_first_and_dry_run_still_direct(runtime, monkeypatch):
    monkeypatch.setattr(module, "DRY_RUN", True)
    mock = install(monkeypatch, [state(drop=True), state(count=6)])
    result = run()
    assert result["result"]["status"] == "completed"
    assert mock.await_count == 1 and mock.await_args.args[0].type == "collect"
    assert result["dry_run"] is False


def test_auto_pickup_after_mine_skips_collect(runtime, monkeypatch):
    mock = install(monkeypatch, [state(), state(), state(count=6)])
    assert run()["result"]["status"] == "completed"
    assert mock.await_count == 2


def test_completed_action_without_gain_is_not_goal_success(runtime, monkeypatch):
    install(monkeypatch, [state(drop=True), state(log=False)])
    result = run()
    assert result["result"]["reason"] == "inventory_gain_not_observed"
    assert result["inventoryDelta"] == 0


@pytest.mark.parametrize("status", ["rejected", "cancelled", "timed_out"])
def test_failed_action_never_chains(runtime, monkeypatch, status):
    mock = install(monkeypatch, [state()], {1: {"status": status, "reason": "unsafe_start"}})
    result = run()
    assert result["result"]["reason"] == "action_" + status
    assert result["result"]["actionReason"] == "unsafe_start"
    assert mock.await_count == 1


def test_budget_stops_before_second_action(runtime, monkeypatch):
    mock = install(monkeypatch, [state()])
    assert run(1)["result"]["reason"] == "action_budget_exhausted"
    assert mock.await_count == 1


@pytest.mark.parametrize("change,reason", [
    ("session", "world_changed"), ("dimension", "world_changed"),
    ("health", "health_decreased"), ("ready", "world_not_ready"),
    ("target", "mining_target_not_verified")])
def test_changed_world_or_target_stops_before_mining(runtime, monkeypatch, change, reason):
    altered = state()
    obs = altered["observation"]
    if change == "session": obs["session"] = "new"
    elif change == "dimension": obs["player"]["dimension"] = "minecraft:the_nether"
    elif change == "health": obs["player"]["health"] = 19
    elif change == "ready": obs["ready"] = False
    else: obs["environment"]["target"]["position"] = [1,70,-1]
    mock = install(monkeypatch, [state(), altered])
    assert run()["result"]["reason"] == reason
    assert mock.await_count == 1


def test_no_local_target_does_not_count_existing_logs(runtime, monkeypatch):
    mock = install(monkeypatch, [state(log=False)])
    assert run()["result"]["reason"] == "no_local_log_or_drop"
    mock.assert_not_awaited()


def test_supporting_log_is_not_mined():
    snapshot = state(log=False)
    snapshot["observation"]["environment"]["terrain"]["cells"][121] = 3
    with pytest.raises(GoalHalt, match="no_local_log_or_drop"):
        choose(snapshot["observation"])


def test_stale_observation_never_dispatches(runtime, monkeypatch):
    snapshot = state()
    snapshot["observedAt"] -= 10000
    monkeypatch.setattr(module, "observe", AsyncMock(return_value=snapshot))
    mock = AsyncMock()
    monkeypatch.setattr(module, "execute_action", mock)
    assert run()["result"]["reason"] == "stale_observation"
    mock.assert_not_awaited()


def test_remaining_log_two_blocks_above_feet_is_selected():
    snapshot = state(log=False)
    snapshot["observation"]["environment"]["terrain"]["cells"][367] = 3
    assert choose(snapshot["observation"])["y"] == 72


def test_canopy_above_navigation_height_is_not_selected():
    snapshot = state(log=False)
    snapshot["observation"]["environment"]["terrain"]["cells"][448] = 3
    with pytest.raises(GoalHalt, match="no_local_log_or_drop"):
        choose(snapshot["observation"])


def test_uncertain_action_requests_stop(runtime, monkeypatch):
    install(monkeypatch, [state()], {1: {"status": "running"}})
    mock = AsyncMock(return_value={"status": "queued"})
    monkeypatch.setattr(module, "bridge", mock)
    result = run()
    mock.assert_awaited_once_with("POST", "/v1/actions", {"type": "stop"})
    assert result["result"]["status"] == "stopped"


def test_auth_validation_and_shared_lock(runtime):
    with TestClient(module.app) as client:
        headers = {"Authorization": "Bearer " + module.TOKEN}
        assert client.post("/v1/goals/wood", json={}).status_code == 401
        for value in [0, 4, True, 1.5]:
            assert client.post("/v1/goals/wood", json={"max_actions": value}, headers=headers).status_code == 422
        asyncio.run(module.step_lock.acquire())
        assert client.post("/v1/goals/wood", json={}, headers=headers).status_code == 409
        module.step_lock.release()


def test_nonadvancing_observation_blocks_next_action(runtime, monkeypatch):
    snapshot = state()
    monkeypatch.setattr(module, "observe", AsyncMock(return_value=snapshot))
    mock = AsyncMock(return_value={"status": "completed"})
    monkeypatch.setattr(module, "execute_action", mock)
    monkeypatch.setattr(module.asyncio, "sleep", AsyncMock())
    assert run()["result"]["reason"] == "observation_not_advancing"
    assert mock.await_count == 1


def test_missing_drop_does_not_start_second_mine(runtime, monkeypatch):
    mock = install(monkeypatch, [state(), state(), state(log=False)])
    monkeypatch.setattr(module.asyncio, "sleep", AsyncMock())
    assert run()["result"]["reason"] == "no_settled_log_drop"
    assert mock.await_count == 2


@pytest.mark.parametrize("failure,reason", [
    (TimeoutError(), "goal_timeout"),
    (module.HTTPException(503, "offline"), "bridge_or_state_error")])
def test_interrupted_dispatch_is_recorded_and_stop_requested(runtime, monkeypatch, failure, reason):
    install(monkeypatch, [state()])
    monkeypatch.setattr(module, "execute_action", AsyncMock(side_effect=failure))
    mock = AsyncMock(return_value={"status": "queued"})
    monkeypatch.setattr(module, "bridge", mock)
    result = run()
    assert result["result"]["reason"] == reason
    assert result["stopRequest"]["status"] == "queued"
    mock.assert_awaited_once()
    assert not module.step_lock.locked()


def test_dimension_change_at_dispatch_never_queues(runtime, monkeypatch):
    before = state()
    after = deepcopy(before)
    after["observation"]["player"]["dimension"] = "minecraft:the_nether"
    mock = AsyncMock(return_value=after)
    monkeypatch.setattr(module, "bridge", mock)
    with pytest.raises(module.HTTPException):
        asyncio.run(module.execute_action(module.Approach(type="approach", x=2,y=70,z=-1,timeoutTicks=200), before))
    mock.assert_awaited_once_with("GET", "/v1/observation")
