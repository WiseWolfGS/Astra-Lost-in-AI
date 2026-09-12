"""Synthetic client -> Node -> Python smoke test. Run only with Minecraft disconnected."""
import os
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import time
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
        # Exercise the real agent execution lock, separate cancellation lane and
        # terminal acknowledgement using a synthetic Fabric client.
        state.pop("result", None)
        state["capabilities"] = ["mine", "cancel"]
        client.post(bridge + "/v1/tick", json=state).raise_for_status()
        def request(path, body):
            with httpx.Client(headers=headers, timeout=25) as worker:
                response=worker.post("http://127.0.0.1:8000"+path,json=body)
                response.raise_for_status()
                return response.json()
        with ThreadPoolExecutor(max_workers=2) as pool:
            execution_future=pool.submit(request,"/v1/act",{"action":{
                "type":"mine","x":1,"y":70,"z":2,"timeoutTicks":200}})
            deadline=time.monotonic()+10
            command=None
            while time.monotonic()<deadline and command is None:
                command=client.post(bridge+"/v1/tick",json=state).json().get("command")
                time.sleep(.05)
            assert command is not None, "agent did not dispatch"
            state["busy"]=True
            state["activeAction"]={"id":command["id"],"type":"mine"}
            client.post(bridge+"/v1/tick",json=state).raise_for_status()
            execution=client.get("http://127.0.0.1:8000/v1/execution").json()["execution"]
            assert execution["actionId"]==command["id"]
            cancel_future=pool.submit(request,"/v1/executions/"+execution["id"]+"/cancel",{})
            cancellation=None
            deadline=time.monotonic()+5
            while time.monotonic()<deadline and cancellation is None:
                cancellation=client.post(bridge+"/v1/tick",json=state).json().get("cancel")
                time.sleep(.05)
            assert cancellation=={"id":command["id"],"session":state["session"]}
            # Receipt alone must never be reported as confirmed.
            pending=client.get(bridge+"/v1/actions/"+command["id"]).json()
            assert pending["status"]=="cancelling" and not pending["cancelConfirmed"]
            state["busy"]=False
            state.pop("activeAction")
            state["result"]={"id":command["id"],"status":"cancelled",
                             "reason":"cancel_requested","details":{"inputsReleased":True}}
            client.post(bridge+"/v1/tick",json=state).raise_for_status()
            cancelled=cancel_future.result(timeout=10)
            outcome=execution_future.result(timeout=10)
            assert cancelled["actionResult"]["cancelConfirmed"]
            assert outcome["result"]["status"]=="cancelled" and outcome["result"]["cancelConfirmed"]
            status=client.get("http://127.0.0.1:8000/v1/executions/"+execution["id"]).json()
            assert status["finished"] and status["cancelRequested"]
            print("PASS: running execution cancellation bypasses lock, matches session/action and confirms input release.")
    finally:
        state["ready"] = False
        client.post(bridge + "/v1/tick", json=state).raise_for_status()
