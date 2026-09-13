import asyncio
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
import app as module


@pytest.mark.parametrize("slot,item", [(-1,"minecraft:air"),(9,"minecraft:air"),
    (True,"minecraft:air"),("1","minecraft:air"),(1,"air"),(1,"minecraft:bad item")])
def test_bad_selection_never_dispatches(monkeypatch,slot,item):
    bridge=AsyncMock()
    monkeypatch.setattr(module,"bridge",bridge)
    with TestClient(module.app) as client:
        response=client.post("/v1/act",json={"action":{"type":"select_hotbar","slot":slot,"expectedItem":item}},
                             headers={"Authorization":"Bearer "+module.TOKEN})
    assert response.status_code == 422
    bridge.assert_not_awaited()


def test_old_client_rejected_before_action_submission(monkeypatch):
    before={"connected":True,"observation":{"ready":True,"session":"test","capabilities":[]}}
    bridge=AsyncMock(return_value=before)
    monkeypatch.setattr(module,"bridge",bridge)
    with pytest.raises(module.HTTPException) as error:
        asyncio.run(module.execute_action(module.SelectHotbar(type="select_hotbar",slot=0,expectedItem="minecraft:air"),before))
    assert error.value.status_code == 409
    bridge.assert_awaited_once_with("GET","/v1/observation")


@pytest.mark.parametrize("status,reason",[("completed","hotbar_selected"),("rejected","slot_item_changed")])
def test_selection_preserves_actual_feedback(monkeypatch,status,reason):
    before={"connected":True,"observation":{"ready":True,"session":"test","capabilities":["select_hotbar"]}}
    result={"status":status,"reason":reason,"details":{"serverConfirmed":False}}
    bridge=AsyncMock(side_effect=[before,{"id":"a","status":"queued"},result])
    monkeypatch.setattr(module,"bridge",bridge)
    monkeypatch.setattr(module.asyncio,"sleep",AsyncMock())
    actual=asyncio.run(module.execute_action(module.SelectHotbar(type="select_hotbar",slot=8,expectedItem="minecraft:air"),before))
    assert actual == result


def test_selection_is_manual_only():
    assert "select_hotbar" not in str(module.Plan.model_json_schema())
