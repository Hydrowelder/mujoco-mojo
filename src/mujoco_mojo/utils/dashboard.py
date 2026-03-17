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

HERE = Path(__file__).parent
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

    while True:
        job = CURRENT_JOB

        # only broadcast if there is a job and there are listeners and the job is not done
        if job and active_connections and not job.is_done:
            # start event
            await _emit_to_all({"type": "start", "total": job.n_trial})

            def sync_reporter(pct: float):
                asyncio.run_coroutine_threadsafe(
                    _emit_to_all({"type": "progress", "value": pct}),
                    loop,
                )

            # perform the refresh for everyone on a separate thread
            await loop.run_in_executor(
                None,
                lambda: job.refresh_from_disk(progress_callback=sync_reporter),  # pyright: ignore[reportOptionalMemberAccess]
            )

            # package the update and send it
            final_data = job.to_dashboard_json()
            await _emit_to_all({"type": "progress", "value": 100})
            await _emit_to_all({"type": "final", "status": final_data})

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
    try:
        await broadcast_task
    except asyncio.CancelledError:
        logger.info("Broadcast task shut down successfully")


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
                yield {"data": data}

        finally:
            active_connections.remove(client_queue)

    return EventSourceResponse(event_generator())
