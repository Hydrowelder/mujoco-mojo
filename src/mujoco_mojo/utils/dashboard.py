import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from mujoco_mojo.utils.statusing import JobStatus

dashboard_app = FastAPI(title="MuJoCo Mojo Dashboard")
HERE = Path(__file__).parent
templates = Jinja2Templates(directory=HERE / "templates")

# Chime sound comes from https://mixkit.co/free-sound-effects/win/
dashboard_app.mount("/static", StaticFiles(directory=HERE / "templates"), name="static")

CURRENT_JOB: JobStatus | None = None


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

    async def event_generator():
        if not CURRENT_JOB:
            yield {"data": json.dumps({"type": "error", "message": "No job loaded"})}
            return

        # 1. Initial Start Event
        yield {"data": json.dumps({"type": "start", "total": CURRENT_JOB.n_trial})}

        # 2. Trigger a custom refresh that reports progress
        # We process in chunks so we don't spam the network too hard
        chunk_size = max(1, CURRENT_JOB.n_trial // 20)

        # We manually drive the refresh here to yield progress
        total = CURRENT_JOB.n_trial
        for i in range(0, total, chunk_size):
            # Check if client disconnected
            if await request.is_disconnected():
                break

            # 1. Run the refresh
        CURRENT_JOB.refresh_from_disk()

        # 2. Yield artificial "smoothing" increments
        # This keeps the laser moving while Python is finishing the dump_to_path
        for p in range(0, 96, 5):
            yield {"data": json.dumps({"type": "progress", "value": p})}
            await asyncio.sleep(0.02)

        # 3. Final data generation (The heavy part)
        final_data = CURRENT_JOB.to_dashboard_json()

        # 4. Only NOW hit 100% and send the data
        yield {"data": json.dumps({"type": "progress", "value": 100})}
        yield {"data": json.dumps({"type": "final", "status": final_data})}

    return EventSourceResponse(event_generator())
