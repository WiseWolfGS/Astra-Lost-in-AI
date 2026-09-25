import asyncio
from copy import deepcopy
import time
from unittest.mock import AsyncMock

import pytest
import app as module
from test_perception import fixture_observation
from tool_goal import CraftToolGoal, choose_tool_action, GoalHalt, count_materials, count_tool


def tool_state(recipe="wooden_pickaxe", tool_slot=None, selected_slot=0,
               planks=3, sticks=2, cobblestone=0, target_wb=True, wb_in_terrain=True):
    obs = fixture_observation()
    obs.update(ready=True, busy=False, session="tool_test",
               capabilities=["craft_workbench", "move_hotbar", "select_hotbar", "stone_tools"])
    inv = []
    if planks > 0:
        inv.append({"slot": 10, "item": "minecraft:oak_planks", "count": planks})
    if sticks > 0:
        inv.append({"slot": 11, "item": "minecraft:stick", "count": sticks})
    if cobblestone > 0:
        inv.append({"slot": 12, "item": "minecraft:cobblestone", "count": cobblestone})
    if tool_slot is not None:
        inv.append({"slot": tool_slot, "item": "minecraft:" + recipe, "count": 1})

    main_hand = {"item": "minecraft:air", "count": 0}
    if tool_slot == selected_slot:
        main_hand = {"item": "minecraft:" + recipe, "count": 1}

    obs["player"].update(health=20, dimension="minecraft:overworld",
                         selectedSlot=selected_slot, mainHand=main_hand, inventory=inv)

    terrain = obs["environment"]["terrain"]
    terrain["cells"] = [0] * 486
    terrain["palette"].append({"id": "minecraft:crafting_table"})
    wb_palette_idx = len(terrain["palette"]) - 1
    if wb_in_terrain:
        terrain["cells"][205] = wb_palette_idx

    if target_wb:
        obs["environment"]["target"] = {
            "type": "block", "position": [2, 70, -1],
            "block": {"id": "minecraft:crafting_table"}, "inReach": True, "canHarvest": True, "hardness": 2.5
        }
    else:
        obs["environment"]["target"] = {"type": "air"}

    return {"connected": True, "observedAt": time.time() * 1000, "observation": obs}


def test_choose_tool_action_craft_when_not_in_inventory():
    st = tool_state(recipe="wooden_pickaxe", tool_slot=None, planks=3, sticks=2)
    action = choose_tool_action(st["observation"], recipe="wooden_pickaxe", slot=0)
    assert action == {"type": "craft_workbench", "recipe": "wooden_pickaxe", "x": 2, "y": 70, "z": -1}


def test_choose_tool_action_move_when_in_main_inventory():
    st = tool_state(recipe="wooden_pickaxe", tool_slot=15, selected_slot=0)
    action = choose_tool_action(st["observation"], recipe="wooden_pickaxe", slot=0)
    assert action["type"] == "move_hotbar"
    assert action["sourceSlot"] == 15
    assert action["hotbarSlot"] == 0
    assert action["expectedSource"] == "minecraft:wooden_pickaxe"


def test_choose_tool_action_select_when_in_hotbar_not_selected():
    st = tool_state(recipe="wooden_pickaxe", tool_slot=0, selected_slot=1)
    action = choose_tool_action(st["observation"], recipe="wooden_pickaxe", slot=0)
    assert action == {"type": "select_hotbar", "slot": 0, "expectedItem": "minecraft:wooden_pickaxe"}


def test_choose_tool_action_none_when_already_equipped():
    st = tool_state(recipe="wooden_pickaxe", tool_slot=0, selected_slot=0)
    action = choose_tool_action(st["observation"], recipe="wooden_pickaxe", slot=0)
    assert action is None


def test_preflight_rejects_insufficient_materials():
    st = tool_state(recipe="wooden_pickaxe", planks=2, sticks=2)
    with pytest.raises(GoalHalt, match="insufficient_materials"):
        choose_tool_action(st["observation"], recipe="wooden_pickaxe", slot=0)


def test_preflight_rejects_missing_workbench():
    st = tool_state(recipe="wooden_pickaxe", planks=3, sticks=2, target_wb=False, wb_in_terrain=False)
    with pytest.raises(GoalHalt, match="aim_at_workbench"):
        choose_tool_action(st["observation"], recipe="wooden_pickaxe", slot=0)


def test_stone_tool_requires_stone_materials():
    st = tool_state(recipe="stone_pickaxe", cobblestone=2, sticks=2)
    with pytest.raises(GoalHalt, match="insufficient_materials"):
        choose_tool_action(st["observation"], recipe="stone_pickaxe", slot=0)

    st2 = tool_state(recipe="stone_pickaxe", cobblestone=3, sticks=2)
    action = choose_tool_action(st2["observation"], recipe="stone_pickaxe", slot=0)
    assert action["type"] == "craft_workbench"
    assert action["recipe"] == "stone_pickaxe"


def test_full_craft_move_select_sequence():
    async def run_test():
        s0 = tool_state(recipe="wooden_pickaxe", tool_slot=None, planks=3, sticks=2, selected_slot=1)
        s1 = tool_state(recipe="wooden_pickaxe", tool_slot=9, planks=0, sticks=0, selected_slot=1)
        s2 = tool_state(recipe="wooden_pickaxe", tool_slot=0, planks=0, sticks=0, selected_slot=1)
        s3 = tool_state(recipe="wooden_pickaxe", tool_slot=0, planks=0, sticks=0, selected_slot=0)

        states = [s0, s1, s2, s3]
        stage = 0
        clock = time.time() * 1000

        async def mock_observe():
            nonlocal clock
            clock += 1
            snap = deepcopy(states[min(stage, len(states) - 1)])
            snap["observedAt"] = clock
            return snap

        dispatched = []

        async def mock_execute(act, before):
            nonlocal stage
            stage += 1
            dispatched.append(act)
            return {"status": "completed", "reason": "action_ok"}

        record = {"steps": []}
        goal = CraftToolGoal(mock_observe, mock_execute, record, max_actions=3,
                             recipe="wooden_pickaxe", slot=0)
        await goal.run()

        assert len(dispatched) == 3
        assert dispatched[0]["type"] == "craft_workbench"
        assert dispatched[1]["type"] == "move_hotbar"
        assert dispatched[2]["type"] == "select_hotbar"
        assert goal.is_equipped(goal.current["observation"])

    asyncio.run(run_test())
