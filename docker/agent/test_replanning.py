import asyncio
from copy import deepcopy
import pytest
import app as module
from test_wood_goal import runtime, install, state


def drops():
    snapshot=state(drop=True)
    second=deepcopy(snapshot["observation"]["environment"]["entities"][0])
    second.update(id=43, position=[2.5,70,-.5])
    snapshot["observation"]["environment"]["entities"].append(second)
    return snapshot


def run(budget=3):
    return asyncio.run(module.wood(module.WoodRequest(max_actions=budget)))


def test_rejected_drop_uses_distinct_candidate_with_shared_budget(runtime, monkeypatch):
    execute=install(monkeypatch,[drops(),drops(),state(count=6)],
                    {1:{"status":"rejected","reason":"no_flat_path"}})
    result=run(2)
    assert result["result"]["status"] == "completed"
    assert [call.args[0].entityId for call in execute.await_args_list] == [42,43]
    assert len(result["steps"]) == 2 and len(result["replans"]) == 1


def test_no_alternative_does_not_repeat_or_mine(runtime, monkeypatch):
    execute=install(monkeypatch,[state(drop=True)],
                    {1:{"status":"rejected","reason":"no_flat_path"}})
    assert run()["result"]["reason"] == "no_alternative_candidate"
    assert execute.await_count == 1


def test_exhausted_budget_never_replans(runtime, monkeypatch):
    execute=install(monkeypatch,[drops()],{1:{"status":"rejected","reason":"no_flat_path"}})
    result=run(1)
    assert result["result"]["reason"] == "action_rejected"
    assert execute.await_count == 1 and not result.get("replans")


@pytest.mark.parametrize("status,reason",[("cancelled","path_blocked"),
    ("timed_out","navigation_timeout"),("rejected","unsafe_start")])
def test_unsafe_or_cancelled_failures_never_retry(runtime, monkeypatch,status,reason):
    execute=install(monkeypatch,[drops()],{1:{"status":status,"reason":reason}})
    run()
    assert execute.await_count == 1


def test_second_rejection_does_not_retry_again(runtime,monkeypatch):
    execute=install(monkeypatch,[drops()],{i:{"status":"rejected","reason":"no_flat_path"} for i in (1,2)})
    assert run()["result"]["reason"] == "action_rejected"
    assert execute.await_count == 2


def test_health_loss_after_rejection_blocks_retry(runtime,monkeypatch):
    hurt=drops(); hurt["observation"]["player"]["health"]=19
    execute=install(monkeypatch,[drops(),hurt],{1:{"status":"rejected","reason":"no_flat_path"}})
    assert run()["result"]["reason"] == "health_decreased"
    assert execute.await_count == 1
