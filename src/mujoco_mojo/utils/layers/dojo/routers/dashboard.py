import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.statusing import JobStatus

logger = get_logger(__name__)

HERE = Path(__file__).parent.parent
CURRENT_JOB: JobStatus | None = None
AUTOREFRESH_PERIOD = 5.0


# all current clients in queue
active_connections: set[asyncio.Queue] = set()


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
            if not job or not active_connections:
                await asyncio.sleep(AUTOREFRESH_PERIOD)
                continue

            new_listeners = active_connections - synced_connections

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
                final_data = job.to_dashboard_json()
                await _emit_to_all({"type": "progress", "value": 100})
                await _emit_to_all({"type": "final", "status": final_data})

                # Mark everyone as synced
                synced_connections.update(active_connections)

            # Cleanup synced set when clients disconnect
            synced_connections &= active_connections

        except asyncio.CancelledError:
            break
        await asyncio.sleep(AUTOREFRESH_PERIOD)


async def _emit_to_all(message_dict: dict):
    """Helper to push a message to every queue on the bus."""
    if not active_connections:
        return

    payload = json.dumps(message_dict)
    for queue in active_connections:
        await queue.put(payload)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup logic
    broadcast_task = asyncio.create_task(broadcast_updates())
    yield

    # shutdown logic
    broadcast_task.cancel()
    for queue in list(active_connections):
        await queue.put(None)  # Sentinel value to break the while loop

    await broadcast_task


dashboard_app = FastAPI(title="MuJoCo Mojo Dashboard", lifespan=lifespan)
templates = Jinja2Templates(directory=HERE / "templates")

# Chime sound comes from https://mixkit.co/free-sound-effects/win/
dashboard_app.mount("/static", StaticFiles(directory=HERE / "templates"), name="static")


@dashboard_app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Serves the initial dashboard frame."""
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "job": CURRENT_JOB}
    )


@dashboard_app.get("/api/status")
async def get_status():
    """The 'Pulse' endpoint for Alpine.js."""
    if not CURRENT_JOB:
        return {"error": "No job loaded"}

    return CURRENT_JOB.to_dashboard_json()


@dashboard_app.get("/api/status/stream")
async def status_stream(request: Request):
    """
    Streams job loading progress to the dashboard via SSE.
    """
    client_queue = asyncio.Queue()
    active_connections.add(client_queue)

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
            active_connections.remove(client_queue)

    return EventSourceResponse(event_generator())
