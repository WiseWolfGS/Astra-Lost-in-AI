import asyncio
from unittest.mock import AsyncMock
import pytest
from pydantic import ValidationError
import app as module

BASE={'type':'place_workbench','x':0,'y':64,'z':0,'expectedSupport':'minecraft:dirt'}
@pytest.mark.parametrize('change',[{'y':319},{'x':True},{'expectedSupport':'minecraft:chest'},{'repeat':2}])
def test_bad_placement_rejected(change):
    with pytest.raises(ValidationError): module.DirectAction(action={**BASE,**change})

def test_placement_requires_capability(monkeypatch):
    state={'connected':True,'observation':{'ready':True,'session':'test','capabilities':[]}}
    bridge=AsyncMock(return_value=state)
    monkeypatch.setattr(module,'bridge',bridge)
    with pytest.raises(module.HTTPException): asyncio.run(module.execute_action(module.PlaceWorkbench(**BASE),state))
    bridge.assert_awaited_once_with('GET','/v1/observation')

def test_placement_feedback_not_promoted_to_server_confirmation(monkeypatch):
    state={'connected':True,'observation':{'ready':True,'session':'test','capabilities':['place_workbench']}}
    result={'status':'completed','reason':'workbench_placed','details':{'serverConfirmed':False,'inventoryConsumed':1}}
    monkeypatch.setattr(module,'bridge',AsyncMock(side_effect=[state,{'id':'place','status':'queued'},result]))
    monkeypatch.setattr(module.asyncio,'sleep',AsyncMock())
    assert asyncio.run(module.execute_action(module.PlaceWorkbench(**BASE),state)) == result
