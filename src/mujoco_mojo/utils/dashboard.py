from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from mujoco_mojo.utils.statusing import JobStatus

app = FastAPI(title="MuJoCo Mojo Dashboard")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

CURRENT_JOB: JobStatus | None = None


def set_active_job(job: JobStatus):
    global CURRENT_JOB
    CURRENT_JOB = job
    print(f"DEBUG: Active job set to {CURRENT_JOB.started_by}")


@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Serves the initial dashboard frame."""
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "job": CURRENT_JOB}
    )


@app.get("/api/status")
async def get_status():
    """The 'Pulse' endpoint for Alpine.js."""
    if not CURRENT_JOB:
        return {"error": "No job loaded"}

    return CURRENT_JOB.to_dashboard_json()
