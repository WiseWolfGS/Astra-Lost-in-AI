from copy import deepcopy
import pytest
from perception import summarize, planner_observation


def fixture_observation():
    air = {"id": "minecraft:air", "air": True, "collision": False, "fluid": "empty", "potentialHazard": False}
    stone = {"id": "minecraft:stone", "air": False, "collision": True, "fluid": "empty", "potentialHazard": False}
    lava = {"id": "minecraft:lava", "air": False, "collision": False, "fluid": "minecraft:lava", "potentialHazard": True}
    cells = [0] * 486
    # origin (-5, 68, -5); feet at (-1,70,-1). Fixed indices exercise x/z/y ordering.
    cells[121] = 1  # (-1,69,-1), directly below
    cells[193] = 2  # (-1,70,-2), north feet
    cells[201] = -1  # (-2,70,-1), west feet: not loaded
    cells[203] = -2  # (0,70,-1), east feet: omitted
    return {
        "player": {"position": [-0.5, 70.0, -0.5]},
        "environment": {"schema": 1, "available": True, "source": "local_loaded_world", "sampledAt": 123,
            "terrain": {"origin": [-5,68,-5], "size": [9,6,9], "order": "y,z,x",
                        "palette": [air,stone,lava], "cells": cells},
            "target": {"type": "miss"}, "entities": []}
    }


def test_grid_coordinates_and_negative_player_position():
    result = summarize(fixture_observation())
    assert result["available"]
    assert result["adjacentColumns"]["here"]["below"]["id"] == "minecraft:stone"
    assert result["adjacentColumns"]["north"]["feet"]["potentialHazard"] is True
    assert result["adjacentColumns"]["west"]["feet"]["unknown"] is True
    assert result["adjacentColumns"]["east"]["feet"]["reason"] == "palette_limit"
    assert result["unknownCells"] == 1 and result["omittedCells"] == 1
    nearest = {entry["id"]: entry["position"] for entry in result["nearestBlockTypes"]}
    assert nearest["minecraft:stone"] == [-1,69,-1]
    assert nearest["minecraft:lava"] == [-1,70,-2]


@pytest.mark.parametrize("index", [128, -3, True, 0.5])
def test_invalid_palette_indices_fail_closed(index):
    observation = fixture_observation()
    observation["environment"]["terrain"]["cells"][0] = index
    assert summarize(observation) == {"available": False, "reason": "invalid_environment"}


def test_old_client_and_payload_limit():
    assert summarize({})["reason"] == "client_upgrade_required"
    assert summarize({"environment": {"available": False, "reason": "payload_limit"}})["reason"] == "payload_limit"


def test_prompt_is_compact_and_does_not_mutate_raw_episode():
    snapshot = {"connected": True, "observation": fixture_observation()}
    original = deepcopy(snapshot)
    prompt = planner_observation(snapshot)
    assert "environment" not in prompt["observation"]
    assert prompt["observation"]["perception"]["available"]
    assert snapshot == original


def test_truncated_grid_rejected():
    observation = fixture_observation()
    observation["environment"]["terrain"]["cells"].pop()
    assert summarize(observation)["available"] is False

def test_item_identity_and_settled_state_reach_model_summary():
    observation=fixture_observation()
    item={"id":5,"type":"minecraft:item","item":"minecraft:oak_log","count":1,"onGround":True,"distance":2.0}
    observation["environment"]["entities"]=[item]
    assert summarize(observation)["entities"]==[item]
