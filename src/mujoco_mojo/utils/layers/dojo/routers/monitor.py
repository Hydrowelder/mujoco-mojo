import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.statusing import JobStatus

from ..shared import templates

logger = get_logger(__name__)

router = APIRouter()

CURRENT_JOB: JobStatus | None = None
AUTOREFRESH_PERIOD = 5.0
ACTIVE_CONNECTIONS: set[asyncio.Queue] = set()


async def broadcast_updates():
    """
    This function refreshes the CURRENT_JOB and broadcasts to listeners simultaneously.

    When clients connect, they join the broadcast to recieve updates.
    """
    loop = asyncio.get_running_loop()
    synced_connections: set[asyncio.Queue] = set()

    while True:
        try:
            job = CURRENT_JOB
            if not job or not ACTIVE_CONNECTIONS:
                await asyncio.sleep(AUTOREFRESH_PERIOD)
                continue

            new_listeners = ACTIVE_CONNECTIONS - synced_connections

            # If there is work to do OR new people need a catch-up packet
            if not job.is_done or new_listeners:
                # 1. Start event for the progress bar
                await _emit_to_all({"type": "start", "total": job.n_trial})

                # 2. Only perform the heavy disk scan if the job is actually active
                if not job.is_done:
                    last_reported = [0]

                    def throttled_sync_reporter(pct: float):
                        if pct >= last_reported[0] + 5 or pct >= 100:
                            last_reported[0] = int(pct // 5) * 5
                            asyncio.run_coroutine_threadsafe(
                                _emit_to_all({"type": "progress", "value": pct}), loop
                            )

                    await loop.run_in_executor(
                        None,
                        lambda: job.refresh_from_disk(  # pyright: ignore[reportOptionalMemberAccess]
                            progress_callback=throttled_sync_reporter
                        ),
                    )

                # 3. Always send the "final" state to everyone
                final_data = job.to_monitor_json()
                await _emit_to_all({"type": "progress", "value": 100})
                await _emit_to_all({"type": "final", "status": final_data})

                # Mark everyone as synced
                synced_connections.update(ACTIVE_CONNECTIONS)

            # Cleanup synced set when clients disconnect
            synced_connections &= ACTIVE_CONNECTIONS

        except asyncio.CancelledError:
            break
        await asyncio.sleep(AUTOREFRESH_PERIOD)


async def _emit_to_all(message_dict: dict):
    """Helper to push a message to every queue on the bus."""
    if not ACTIVE_CONNECTIONS:
        return

    payload = json.dumps(message_dict)
    for queue in ACTIVE_CONNECTIONS:
        await queue.put(payload)


@router.get("/", response_class=HTMLResponse)
async def get_monitor(request: Request):
    """Serves the initial monitor frame."""
    return templates.TemplateResponse(
        name="monitor.html", context={"request": request, "job": CURRENT_JOB}
    )


@router.get("/api/status")
async def get_status():
    """The 'Pulse' endpoint for Alpine.js."""
    if not CURRENT_JOB:
        return {"error": "No job loaded"}

    return CURRENT_JOB.to_monitor_json()


@router.get("/api/status/stream")
async def status_stream(request: Request):
    """
    Streams job loading progress to the monitor via SSE.
    """
    client_queue = asyncio.Queue()
    ACTIVE_CONNECTIONS.add(client_queue)

    async def event_generator():
        try:
            while True:
                # check for disconnect
                if await request.is_disconnected():
                    break

                # wait for the next bus update
                data = await client_queue.get()
                if data is None:
                    return
                yield {"data": data}

        finally:
            ACTIVE_CONNECTIONS.remove(client_queue)

    return EventSourceResponse(event_generator())
