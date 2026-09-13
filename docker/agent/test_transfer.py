import asyncio
from unittest.mock import AsyncMock
import pytest
from pydantic import ValidationError
import app as module
BASE={'type':'move_hotbar','sourceSlot':9,'hotbarSlot':0,'expectedSource':'minecraft:wooden_pickaxe',
      'expectedTarget':'minecraft:air','sourceCount':1,'targetCount':0}
@pytest.mark.parametrize('change',[{'sourceSlot':8},{'sourceSlot':36},{'hotbarSlot':9},{'sourceCount':0},
    {'targetCount':True},{'expectedSource':'bad'},{'repeat':2}])
def test_invalid_transfer(change):
    with pytest.raises(ValidationError):module.DirectAction(action={**BASE,**change})

def test_old_client_never_receives_transfer(monkeypatch):
    state={'connected':True,'observation':{'ready':True,'session':'test','capabilities':['select_hotbar']}}
    bridge=AsyncMock(return_value=state);monkeypatch.setattr(module,'bridge',bridge)
    with pytest.raises(module.HTTPException):asyncio.run(module.execute_action(module.MoveHotbar(**BASE),state))
    bridge.assert_awaited_once_with('GET','/v1/observation')

@pytest.mark.parametrize('status,reason',[('completed','hotbar_transfer_verified'),('rejected','inventory_changed')])
def test_transfer_keeps_feedback(monkeypatch,status,reason):
    state={'connected':True,'observation':{'ready':True,'session':'test','capabilities':['move_hotbar']}}
    result={'status':status,'reason':reason}
    monkeypatch.setattr(module,'bridge',AsyncMock(side_effect=[state,{'id':'swap','status':'queued'},result]))
    monkeypatch.setattr(module.asyncio,'sleep',AsyncMock())
    assert asyncio.run(module.execute_action(module.MoveHotbar(**BASE),state)) == result
