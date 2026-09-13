import asyncio
from unittest.mock import AsyncMock
import pytest
import app as module
from pydantic import ValidationError

@pytest.mark.parametrize('recipe',['oak_planks','stick','crafting_table'])
def test_allowlisted_recipe(recipe):
    assert module.DirectAction(action={'type':'craft','recipe':recipe}).action.recipe == recipe

@pytest.mark.parametrize('action',[{'type':'craft','recipe':'diamond_sword'},
    {'type':'craft','recipe':'oak_planks','count':64},{'type':'craft','recipe':'minecraft:oak_planks'}])
def test_unbounded_or_unknown_recipe_rejected(action):
    with pytest.raises(ValidationError): module.DirectAction(action=action)

def test_legacy_client_cannot_receive_craft(monkeypatch):
    state={'connected':True,'observation':{'session':'test','ready':True,'capabilities':[]}}
    bridge=AsyncMock(return_value=state)
    monkeypatch.setattr(module,'bridge',bridge)
    with pytest.raises(module.HTTPException):
        asyncio.run(module.execute_action(module.Craft(type='craft',recipe='stick'),state))
    bridge.assert_awaited_once_with('GET','/v1/observation')

def test_craft_waits_past_eight_seconds_and_keeps_evidence(monkeypatch):
    state={'connected':True,'observation':{'session':'test','ready':True,'capabilities':['craft']}}
    result={'status':'completed','reason':'craft_verified','details':{'inputConsumed':2,'outputGained':4}}
    bridge=AsyncMock(side_effect=[state,{'id':'craft','status':'queued'}]+[{'status':'running'}]*36+[result])
    monkeypatch.setattr(module,'bridge',bridge)
    monkeypatch.setattr(module.asyncio,'sleep',AsyncMock())
    assert asyncio.run(module.execute_action(module.Craft(type='craft',recipe='stick'),state)) == result

def test_craft_remains_manual():
    assert 'crafting_table' not in str(module.Plan.model_json_schema())
