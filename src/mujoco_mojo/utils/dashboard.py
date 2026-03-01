from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from mujoco_mojo.utils.statusing import JobStatus

app = FastAPI(title="MuJoCo Mojo Dashboard")
HERE = Path(__file__).parent
templates = Jinja2Templates(directory=HERE / "templates")

# Chime sound comes from https://mixkit.co/free-sound-effects/win/
app.mount("/static", StaticFiles(directory=HERE / "templates"), name="static")

CURRENT_JOB: JobStatus | None = None


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
