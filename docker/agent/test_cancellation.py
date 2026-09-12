import asyncio
from copy import deepcopy
from uuid import UUID, uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
import app as module
from test_wood_goal import state

@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "executions", {})
    monkeypatch.setattr(module, "step_lock", asyncio.Lock())
    monkeypatch.setattr(module, "DATA", tmp_path)
    monkeypatch.setattr(module, "DRY_RUN", True)
    def forbid_model(*args, **kwargs):
        raise AssertionError("No paid model calls")
    monkeypatch.setattr(module, "ChatOpenAI", forbid_model)

def test_cancel_api_auth_and_uuid_validation():
    with TestClient(module.app) as client:
        url="/v1/executions/"+str(uuid4())+"/cancel"
        assert client.post(url).status_code == 401
        headers={"Authorization":"Bearer "+module.TOKEN}
        assert client.post(url,headers=headers).status_code == 404
        assert client.post("/v1/actions/not-an-id/cancel",headers=headers).status_code == 422
        assert client.get("/v1/execution",headers=headers).json() == {"execution":None}

def test_cancel_bypasses_lock_and_targets_exact_active_action(monkeypatch):
    action_id=str(uuid4())
    result={"id":action_id,"status":"cancelled","cancelConfirmed":True}
    mock=AsyncMock(return_value=result)
    monkeypatch.setattr(module,"cancel_and_wait",mock)
    async def scenario():
        async with module.execution_scope("wood") as control:
            control.action_id=action_id
            assert module.step_lock.locked()
            response=await module.cancel_execution(UUID(control.id))
            assert response["cancelRequested"] and not response["finished"]
            assert response["actionResult"]["cancelConfirmed"]
        assert (await module.execution_status(UUID(control.id)))["finished"]
        mock.assert_awaited_once_with(action_id)
    asyncio.run(scenario())

def test_old_execution_cancel_does_not_cancel_new_execution(monkeypatch):
    mock=AsyncMock()
    monkeypatch.setattr(module,"cancel_and_wait",mock)
    async def scenario():
        async with module.execution_scope("direct") as old: pass
        async with module.execution_scope("wood") as current:
            await module.cancel_execution(UUID(old.id))
            assert not current.cancel_requested
    asyncio.run(scenario())
    mock.assert_not_awaited()

def test_cancellation_during_observation_prevents_dispatch(monkeypatch):
    snapshot=state()
    async def observe():
        module.execution_context.get().cancel_requested=True
        return snapshot
    monkeypatch.setattr(module,"observe",observe)
    mock=AsyncMock()
    monkeypatch.setattr(module,"bridge",mock)
    async def scenario():
        async with module.execution_scope("direct"):
            result=await module.execute_action(module.Stop(type="stop"),snapshot)
            assert result["confirmation"] == "never_dispatched"
    asyncio.run(scenario())
    mock.assert_not_awaited()

def test_cancel_racing_with_post_response_cancels_returned_id(monkeypatch):
    snapshot=state(); action_id=str(uuid4())
    monkeypatch.setattr(module,"observe",AsyncMock(return_value=snapshot))
    async def post(*args):
        control=module.execution_context.get()
        assert control.dispatch_pending and control.action_id is None
        control.cancel_requested=True
        return {"id":action_id,"status":"queued"}
    monkeypatch.setattr(module,"bridge",AsyncMock(side_effect=post))
    cancel=AsyncMock(return_value={"id":action_id,"status":"cancelled","cancelConfirmed":True})
    monkeypatch.setattr(module,"cancel_and_wait",cancel)
    async def scenario():
        async with module.execution_scope("direct") as control:
            result=await module.execute_action(module.Stop(type="stop"),snapshot)
            assert result["cancelConfirmed"] and not control.dispatch_pending
    asyncio.run(scenario())
    cancel.assert_awaited_once_with(action_id)

def test_known_action_poll_failure_requests_targeted_cleanup(monkeypatch):
    snapshot=state(); action_id=str(uuid4())
    monkeypatch.setattr(module,"observe",AsyncMock(return_value=snapshot))
    monkeypatch.setattr(module,"bridge",AsyncMock(side_effect=[
        {"id":action_id,"status":"queued"},module.HTTPException(503,"offline")]))
    cancel=AsyncMock(return_value={"id":action_id,"status":"cancelled","cancelConfirmed":True})
    monkeypatch.setattr(module,"cancel_and_wait",cancel)
    monkeypatch.setattr(module.asyncio,"sleep",AsyncMock())
    async def scenario():
        async with module.execution_scope("direct") as control:
            with pytest.raises(module.HTTPException):
                await module.execute_action(module.Stop(type="stop"),snapshot)
            assert control.action_result["cancelConfirmed"]
    asyncio.run(scenario())
    cancel.assert_awaited_once_with(action_id)

def test_cancelling_is_not_terminal_while_polling(monkeypatch):
    snapshot=state()
    mock=AsyncMock(side_effect=[snapshot,{"id":"a","status":"queued"},
        {"id":"a","status":"cancelling"},{"id":"a","status":"cancelled","cancelConfirmed":True}])
    monkeypatch.setattr(module,"bridge",mock)
    monkeypatch.setattr(module.asyncio,"sleep",AsyncMock())
    assert asyncio.run(module.execute_action(module.Stop(type="stop"),snapshot))["cancelConfirmed"]
    assert mock.await_count == 4

@pytest.mark.parametrize("terminal", ["cancelled","completed","expired"])
def test_cancel_wait_returns_actual_terminal_outcome(monkeypatch, terminal):
    result={"id":"a","status":terminal,"cancelConfirmed":terminal=="cancelled"}
    mock=AsyncMock(side_effect=[{"id":"a","status":"cancelling"},result])
    monkeypatch.setattr(module,"bridge",mock)
    monkeypatch.setattr(module.asyncio,"sleep",AsyncMock())
    assert asyncio.run(module.cancel_and_wait("a")) == result

def test_unavailable_confirmation_is_never_success(monkeypatch):
    monkeypatch.setattr(module,"bridge",AsyncMock(side_effect=module.HTTPException(409,"old client")))
    result=asyncio.run(module.cancel_and_wait("a"))
    assert not result["cancelConfirmed"] and result["httpStatus"] == 409

@pytest.mark.parametrize("registered", [False, True])
def test_goal_cancel_after_approach_does_not_start_mine(monkeypatch, registered):
    snapshot=state()
    monkeypatch.setattr(module,"observe",AsyncMock(return_value=snapshot))
    async def execute(*args):
        module.execution_context.get().cancel_requested=True
        return {"status":"completed"}
    mock=AsyncMock(side_effect=execute)
    monkeypatch.setattr(module,"execute_action",mock)
    result=asyncio.run(module.skill_run("wood", module.SkillRequest(version="1.1.0"))
                       if registered else module.wood(module.WoodRequest()))
    assert result["result"]["status"] == "cancelled"
    assert mock.await_count == 1
    assert module.executions[result["executionId"]].finished

def test_cancel_after_model_response_never_sends_game_action(monkeypatch):
    snapshot=state()
    monkeypatch.setattr(module,"DRY_RUN",False)
    monkeypatch.setenv("OPENAI_API_KEY","offline-placeholder")
    monkeypatch.setattr(module,"observe",AsyncMock(return_value=snapshot))
    class Planner:
        async def ainvoke(self, messages):
            module.execution_context.get().cancel_requested=True
            return module.Plan(reason="fake",action=module.Stop(type="stop"))
    class Model:
        def with_structured_output(self,*args,**kwargs): return Planner()
    monkeypatch.setattr(module,"ChatOpenAI",lambda **kwargs:Model())
    mock=AsyncMock()
    monkeypatch.setattr(module,"bridge",mock)
    result=asyncio.run(module.step(module.Step()))
    assert result["result"]["confirmation"] == "never_dispatched"
    mock.assert_not_awaited()
