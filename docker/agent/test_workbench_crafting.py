import asyncio
from unittest.mock import AsyncMock
import pytest
from pydantic import ValidationError
import app as module
BASE={'type':'craft_workbench','recipe':'wooden_pickaxe','x':0,'y':64,'z':0}
@pytest.mark.parametrize('change',[{'recipe':'diamond_pickaxe'},{'y':320},{'x':True},{'repeat':2}])
def test_invalid_workbench_requests(change):
    with pytest.raises(ValidationError): module.DirectAction(action={**BASE,**change})

def test_old_client_does_not_get_open_request(monkeypatch):
    state={'connected':True,'observation':{'ready':True,'session':'test','capabilities':['craft']}}
    bridge=AsyncMock(return_value=state)
    monkeypatch.setattr(module,'bridge',bridge)
    with pytest.raises(module.HTTPException): asyncio.run(module.execute_action(module.CraftWorkbench(**BASE),state))
    bridge.assert_awaited_once_with('GET','/v1/observation')

def test_workbench_keeps_server_evidence_after_long_poll(monkeypatch):
    state={'connected':True,'observation':{'ready':True,'session':'test','capabilities':['craft_workbench']}}
    result={'status':'completed','reason':'craft_verified','details':{'inputConsumed':3,'sticksConsumed':2,'outputGained':1,'syncId':4}}
    bridge=AsyncMock(side_effect=[state,{'id':'workbench','status':'queued'}]+[{'status':'running'}]*65+[result])
    monkeypatch.setattr(module,'bridge',bridge)
    monkeypatch.setattr(module.asyncio,'sleep',AsyncMock())
    assert asyncio.run(module.execute_action(module.CraftWorkbench(**BASE),state)) == result
