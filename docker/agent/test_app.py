import asyncio
import os
import pytest
from unittest.mock import AsyncMock

os.environ.setdefault("BRIDGE_TOKEN", "t" * 32)
os.environ.setdefault("DATA_DIR", "/tmp/astra-tests")
from fastapi.testclient import TestClient
import app as module

@pytest.fixture(autouse=True)
def offline_runtime(monkeypatch):
    # Tests remain offline even when the running container has a paid API configuration.
    monkeypatch.setattr(module, "DRY_RUN", True)
    monkeypatch.setattr(module, "step_lock", asyncio.Lock())
    def forbid_model(*args, **kwargs):
        raise AssertionError("Unit tests must not call the real model")
    monkeypatch.setattr(module, "ChatOpenAI", forbid_model)

def test_auth_and_health():
    with TestClient(module.app) as client:
        assert client.get("/health").json()["dry_run"] is True
        assert client.get("/v1/observation").status_code == 401

def test_dry_run_never_sends_actions(monkeypatch, tmp_path):
    state = {"connected": True, "observation": {"ready": True, "session": "test"}}
    mock = AsyncMock(return_value=state)
    monkeypatch.setattr(module, "bridge", mock)
    monkeypatch.setattr(module, "DATA", tmp_path)
    result = asyncio.run(module.step(module.Step()))
    assert result["result"]["status"] == "skipped"
    mock.assert_awaited_once_with("GET", "/v1/observation")
    assert (tmp_path / "episodes.jsonl").exists()

def test_unready_world_rejected(monkeypatch):
    monkeypatch.setattr(module, "bridge", AsyncMock(return_value={"connected":False}))
    with TestClient(module.app) as client:
        response = client.post("/v1/step",json={},headers={"Authorization":"Bearer "+module.TOKEN})
        assert response.status_code == 409

def test_perception_endpoint_supports_old_client(monkeypatch):
    monkeypatch.setattr(module, "bridge", AsyncMock(return_value={
        "connected": True, "observedAt": 123, "observation": {"ready": True}}))
    with TestClient(module.app) as client:
        assert client.get("/v1/perception").status_code == 401
        result = client.get("/v1/perception", headers={"Authorization":"Bearer "+module.TOKEN}).json()
    assert result["perception"]["reason"] == "client_upgrade_required"

def test_model_path_receives_perception_and_preserves_raw_episode(monkeypatch, tmp_path):
    from test_perception import fixture_observation
    state = {"connected": True, "observation": {
        **fixture_observation(), "ready": True, "session": "test-world"}}
    captured = {}
    class Planner:
        async def ainvoke(self, messages):
            captured["messages"] = messages
            return module.Plan(reason="Test", action=module.Look(type="look", yaw=20, pitch=0))
    class Model:
        def with_structured_output(self, *args, **kwargs):
            return Planner()
    monkeypatch.setattr(module, "DRY_RUN", False)
    monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
    monkeypatch.setattr(module, "ChatOpenAI", lambda **kwargs: Model())
    monkeypatch.setattr(module, "DATA", tmp_path)
    monkeypatch.setattr(module.asyncio, "sleep", AsyncMock())
    mock = AsyncMock(side_effect=[state, state, {"id": "a", "status": "queued"},
        {"id": "a", "status": "completed"}, state])
    monkeypatch.setattr(module, "bridge", mock)
    record = asyncio.run(module.step(module.Step()))
    assert record["result"]["status"] == "completed"
    import json
    prompt = json.loads(captured["messages"][1][1])
    assert prompt["observation"]["observation"]["perception"]["available"]
    assert "environment" not in prompt["observation"]["observation"]
    assert "environment" in record["before"]["observation"]
    assert mock.await_count == 5

def mining_state():
    return {"connected": True, "observation": {"ready": True, "session": "mine-world", "capabilities": ["mine"]}}

def test_direct_mining_executes_without_model_and_keeps_evidence(monkeypatch, tmp_path):
    state = mining_state()
    evidence = {"id":"mine-1", "status":"completed", "details":{"blockChanged":True, "inventoryDelta":{}}}
    mock = AsyncMock(side_effect=[state, state, {"id":"mine-1","status":"queued"}, evidence, state])
    monkeypatch.setattr(module, "bridge", mock)
    monkeypatch.setattr(module.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(module, "DATA", tmp_path)
    request = module.DirectAction(action=module.Mine(type="mine",x=1,y=70,z=2,timeoutTicks=200))
    record = asyncio.run(module.act(request))
    assert record["model_called"] is False
    assert record["dry_run"] is False
    assert record["result"] == evidence
    assert record["result"]["details"]["inventoryDelta"] == {}

def test_mining_waits_past_old_polling_limit(monkeypatch):
    state = mining_state()
    responses = [state, {"id":"mine-1","status":"queued"}]
    responses += [{"id":"mine-1","status":"running"}] * 30
    responses += [{"id":"mine-1","status":"timed_out","reason":"tick_timeout"}]
    monkeypatch.setattr(module, "bridge", AsyncMock(side_effect=responses))
    monkeypatch.setattr(module.asyncio, "sleep", AsyncMock())
    result = asyncio.run(module.execute_action(module.Mine(type="mine",x=1,y=70,z=2,timeoutTicks=200),state))
    assert result["status"] == "timed_out"

@pytest.mark.parametrize("change", [{"capabilities":[]}, {"session":"different-world"}])
def test_incompatible_state_rejects_before_dispatch(monkeypatch, change):
    before = mining_state()
    current = {"connected":True, "observation":{**before["observation"], **change}}
    mock = AsyncMock(return_value=current)
    monkeypatch.setattr(module, "bridge", mock)
    with pytest.raises(module.HTTPException) as error:
        asyncio.run(module.execute_action(module.Mine(type="mine",x=1,y=70,z=2,timeoutTicks=200),before))
    assert error.value.status_code == 409
    mock.assert_awaited_once_with("GET","/v1/observation")

@pytest.mark.parametrize("change", [{"x":1.5},{"x":True},{"y":320},{"timeoutTicks":201},{"timeoutTicks":0}])
def test_bad_mining_actions_never_reach_bridge(monkeypatch, change):
    mock = AsyncMock()
    monkeypatch.setattr(module,"bridge",mock)
    with TestClient(module.app) as client:
        response=client.post("/v1/act", headers={"Authorization":"Bearer "+module.TOKEN},
            json={"action":{"type":"mine","x":1,"y":70,"z":2,"timeoutTicks":200,**change}})
    assert response.status_code == 422
    mock.assert_not_awaited()

def test_direct_action_requires_authentication():
    with TestClient(module.app) as client:
        response=client.post("/v1/act",json={"action":{"type":"stop"}})
    assert response.status_code == 401

@pytest.mark.parametrize("action", [
    {"type":"approach","x":1,"y":70,"z":2,"timeoutTicks":200},
    {"type":"collect","entityId":5,"timeoutTicks":200},
])
def test_navigation_direct_api_preserves_feedback_without_model(monkeypatch,tmp_path,action):
    state={"connected":True,"observation":{"ready":True,"session":"nav","capabilities":["approach","collect"]}}
    outcome={"id":"nav1","status":"completed","details":{"pickupPacketCount":1,"inventoryDelta":1,"verifiedCollectedCount":1}}
    mock=AsyncMock(side_effect=[state,state,{"id":"nav1","status":"queued"},outcome,state])
    monkeypatch.setattr(module,"bridge",mock)
    monkeypatch.setattr(module.asyncio,"sleep",AsyncMock())
    monkeypatch.setattr(module,"DATA",tmp_path)
    with TestClient(module.app) as client:
        response=client.post("/v1/act",headers={"Authorization":"Bearer "+module.TOKEN},json={"action":action})
    assert response.status_code==200
    assert response.json()["model_called"] is False
    assert response.json()["result"]==outcome

@pytest.mark.parametrize("change",[{"entityId":-1},{"entityId":True},{"entityId":1.5},{"timeoutTicks":201}])
def test_invalid_collect_never_dispatches(monkeypatch,change):
    mock=AsyncMock()
    monkeypatch.setattr(module,"bridge",mock)
    with TestClient(module.app) as client:
        response=client.post("/v1/act",headers={"Authorization":"Bearer "+module.TOKEN},
            json={"action":{"type":"collect","entityId":5,"timeoutTicks":200,**change}})
    assert response.status_code==422
    mock.assert_not_awaited()

def test_collect_needs_its_own_capability(monkeypatch):
    state=mining_state()
    mock=AsyncMock(return_value=state)
    monkeypatch.setattr(module,"bridge",mock)
    with pytest.raises(module.HTTPException) as error:
        asyncio.run(module.execute_action(module.Collect(type="collect",entityId=5,timeoutTicks=200),state))
    assert error.value.status_code==409
    assert mock.await_count==1
