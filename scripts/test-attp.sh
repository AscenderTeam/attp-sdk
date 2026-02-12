#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export ATTP_SHARED_SECRET="${ATTP_SHARED_SECRET:-change-me}"
export ATTP_REMOTE_URI="${ATTP_REMOTE_URI:-attp://127.0.0.1:6564}"
export ATTP_NAMESPACE="${ATTP_NAMESPACE:-default}"
export ATTP_NODE_ID="${ATTP_NODE_ID:-main}"
export ATTP_MAX_PAYLOAD_SIZE="${ATTP_MAX_PAYLOAD_SIZE:-1048576}"

export PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:$PYTHONPATH}"

RUNNER="python"
if command -v poetry >/dev/null 2>&1; then
  RUNNER="poetry run python"
fi

$RUNNER - <<'PY'
import asyncio
import os

import msgpack

from attp.client.authenticator import HmacConnectionAuthenticator
from attp.client.session_driver import ClientSessionDriver
from attp.shared.limits import AttpLimits
from attp.types.frames.accepted import IAcceptedDTO
from attp_core.rs_api import AttpClientSession, AttpCommand, init_logging


async def main():
    init_logging(filter=os.getenv("ATTP_LOG_LEVEL", "debug"))
    remote = os.environ["ATTP_REMOTE_URI"]
    namespace = os.environ["ATTP_NAMESPACE"]
    node_id = os.environ["ATTP_NODE_ID"]
    max_payload = int(os.environ["ATTP_MAX_PAYLOAD_SIZE"])

    limits = AttpLimits(max_payload_size=max_payload).to_model()
    print("Connecting to", remote)
    client = AttpClientSession(remote, limits=limits)
    client = await client.connect(max_retries=3)
    if not client.session:
        raise RuntimeError("Failed to connect to remote ATTP server.")
    print("Connected, session established")

    driver = ClientSessionDriver(client.session)
    authenticator = HmacConnectionAuthenticator(
        remote,
        namespace,
        secret={"env": "ATTP_SHARED_SECRET"},
        node_id=node_id,
    )

    print("Sending AUTH...")
    await driver.start(authenticator)
    print("AUTH accepted")

    ready = None
    while True:
        msg = await asyncio.wait_for(driver.incoming_listener.get(), timeout=10)
        if msg is None:
            raise RuntimeError("Connection closed before READY.")
        if msg.route_id == 0 and msg.command_type == AttpCommand.READY:
            if not msg.payload:
                raise RuntimeError("READY payload missing.")
            ready = IAcceptedDTO.mps(msg.payload)
            break

    echo_route_id = None
    notify_route_id = None
    for route in ready.routes:
        if route.pattern == "echo" and route.route_type == "message":
            echo_route_id = route.route_id
        if route.pattern == "notify" and route.route_type == "event":
            notify_route_id = route.route_id

    if echo_route_id is None:
        raise RuntimeError("echo route not found in READY routes.")

    corr = await driver.send_call(echo_route_id, {"message": "hello"})
    while True:
        msg = await asyncio.wait_for(driver.incoming_listener.get(), timeout=10)
        if msg is None:
            raise RuntimeError("Connection closed before ACK.")
        if msg.command_type == AttpCommand.ACK and msg.correlation_id == corr:
            payload = msgpack.unpackb(msg.payload, raw=False) if msg.payload else None
            print("ACK:", payload)
            break
        if msg.command_type == AttpCommand.ERR:
            print("ERR:", msg.payload)
            break

    if notify_route_id is not None:
        await driver.send_event(notify_route_id, {"event": "ping"})

    await driver.close()


asyncio.run(main())
PY
