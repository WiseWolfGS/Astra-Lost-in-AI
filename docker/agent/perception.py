"""Decode the bounded Fabric grid; preserve unknown space rather than treating it as air."""
from collections import Counter
from math import floor, isfinite


def summarize(observation):
    environment = observation.get("environment") or {}
    if environment.get("available") is not True:
        return {"available": False, "reason": environment.get("reason", "client_upgrade_required")}
    try:
        if environment.get("schema") != 1:
            raise ValueError("unsupported environment schema")
        terrain = environment["terrain"]
        origin, size = terrain["origin"], terrain["size"]
        if len(origin) != 3 or any(type(n) is not int for n in origin):
            raise ValueError("invalid origin")
        if size != [9, 6, 9] or terrain["order"] != "y,z,x":
            raise ValueError("invalid grid shape")
        palette, cells = terrain["palette"], terrain["cells"]
        if len(palette) > 128 or len(cells) != 486:
            raise ValueError("invalid grid length")
        if any(type(n) is not int or n < -2 or n >= len(palette) for n in cells):
            raise ValueError("invalid palette index")
        for block in palette:
            if (not isinstance(block["id"], str) or
                any(type(block[key]) is not bool for key in ("air", "collision", "potentialHazard")) or
                not isinstance(block["fluid"], str)):
                raise ValueError("invalid block entry")
        position = observation["player"]["position"]
        if len(position) != 3 or not all(isfinite(n) for n in position):
            raise ValueError("invalid player position")
        feet = [floor(n) for n in position]

        def block_at(pos):
            x, y, z = [pos[i] - origin[i] for i in range(3)]
            if not (0 <= x < 9 and 0 <= y < 6 and 0 <= z < 9):
                return {"unknown": True}
            index = cells[(y * 9 + z) * 9 + x]
            if index < 0:
                return {"unknown": True, "reason": "unloaded_or_outside_height" if index == -1 else "palette_limit"}
            return palette[index]

        counts = Counter()
        nearest = {}
        for offset, index in enumerate(cells):
            if index < 0:
                continue
            block = palette[index]
            counts[block["id"]] += 1
            if block["air"]:
                continue
            pos = [origin[0] + offset % 9, origin[1] + offset // 81, origin[2] + offset // 9 % 9]
            distance2 = sum((pos[i] + 0.5 - position[i]) ** 2 for i in range(3))
            if block["id"] not in nearest or distance2 < nearest[block["id"]][0]:
                nearest[block["id"]] = (distance2, {"position": pos, **block})
        columns = {}
        for direction, (dx, dz) in {"here": (0, 0), "north": (0, -1), "south": (0, 1),
                                    "west": (-1, 0), "east": (1, 0)}.items():
            columns[direction] = {
                label: block_at([feet[0] + dx, feet[1] + dy, feet[2] + dz])
                for label, dy in (("below", -1), ("feet", 0), ("head", 1))
            }
        representatives = sorted(nearest.values(), key=lambda item: item[0])
        return {
            "available": True, "source": environment["source"], "sampledAt": environment["sampledAt"],
            "bounds": {"origin": origin, "size": size},
            "unknownCells": cells.count(-1), "omittedCells": cells.count(-2),
            "blockCounts": dict(counts), "nearestBlockTypes": [item[1] for item in representatives[:24]],
            "blockTypesTruncated": len(representatives) > 24, "adjacentColumns": columns,
            "entities": environment.get("entities", []),
            "entitiesTruncated": environment.get("entitiesTruncated", False),
            "target": environment.get("target", {"type": "miss"}),
            "limitations": "Local blocks include occluded blocks. Entity line of sight ignores camera FOV. "
                           "Collision is only a non-empty shape flag. Hazard labels are incomplete. "
                           "Unknown cells and absent hazards do not imply safe ground. No path validation.",
        }
    except (KeyError, TypeError, ValueError, IndexError, OverflowError):
        return {"available": False, "reason": "invalid_environment"}


def planner_observation(snapshot):
    """Keep the full raw grid in episode logs, but send a compact summary to the model."""
    observation = snapshot["observation"]
    return {**snapshot, "observation": {
        **{key: value for key, value in observation.items() if key != "environment"},
        "perception": summarize(observation),
    }}
