"""Synthetic client -> Node -> Python smoke test. Run only with Minecraft disconnected."""
import os
from uuid import uuid4
import httpx

headers = {"Authorization": "Bearer " + os.environ["BRIDGE_TOKEN"]}
bridge = os.environ.get("BRIDGE_URL", "http://bridge:8765")
with httpx.Client(headers=headers, timeout=10) as client:
    initial = client.get(bridge + "/v1/observation").json()
    if initial["connected"]:
        raise SystemExit("Disconnect Minecraft before running the synthetic smoke test.")
    if not client.get("http://127.0.0.1:8000/health").json()["dry_run"]:
        raise SystemExit("Smoke test requires DRY_RUN=true.")
    state = {"protocol": 1, "session": "smoke-" + str(uuid4()), "ready": True, "busy": False}
    try:
        client.post(bridge + "/v1/tick", json=state).raise_for_status()
        response = client.post("http://127.0.0.1:8000/v1/step", json={"goal": "Synthetic transport smoke test"})
        response.raise_for_status()
        assert response.json()["result"]["status"] == "skipped"
        queued = client.post(bridge + "/v1/actions", json={"type": "look", "yaw": 20, "pitch": 0})
        queued.raise_for_status()
        action_id = queued.json()["id"]
        dispatch = client.post(bridge + "/v1/tick", json=state).json()
        assert dispatch["command"]["id"] == action_id
        state["result"] = {"id": action_id, "status": "completed"}
        client.post(bridge + "/v1/tick", json=state).raise_for_status()
        assert client.get(bridge + "/v1/actions/" + action_id).json()["status"] == "completed"
        print("PASS: synthetic observation, dry-run episode, action dispatch and acknowledgement; no OpenAI call.")
    finally:
        state["ready"] = False
        client.post(bridge + "/v1/tick", json=state).raise_for_status()
