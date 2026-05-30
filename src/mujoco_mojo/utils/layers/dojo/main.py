import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import mujoco_mojo.utils.layers.dojo.shared as shared

from .routers import monitor, morph, mosaic

# try:
#     from .routers import sensai as _sensai_router
# except ImportError:
_sensai_router = None

security = HTTPBasic(auto_error=False)


def validate_dojo_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Checks the provided credentials against the CLI-provided password. Username is ignored (or set to 'mojo'), we just care about the password.
    """
    if not shared.AUTH_PASSWORD:
        return None

    if not credentials or credentials.password != shared.AUTH_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect Mojo Password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def _cleanup_webm_cache(max_age_seconds: float = 86_400) -> None:
    """
    Removes stale GIF→WebM artefacts on startup.

    Cleans two locations: the temp-dir cache (files older than `max_age_seconds`, default 24 h) and any legacy `.mojo_webm.webm` files left in trial directories from before the temp-dir migration.
    """
    import tempfile
    import time
    from pathlib import Path

    # remove stale temp-dir cache entries
    cache_dir = Path(tempfile.gettempdir()) / "mujoco_mojo_webm"
    if cache_dir.is_dir():
        now = time.time()
        for f in cache_dir.iterdir():
            try:
                if now - f.stat().st_mtime > max_age_seconds:
                    f.unlink(missing_ok=True)
            except OSError:
                pass

    # remove legacy in-tree cache files left by older versions of the code
    job = shared.CURRENT_JOB
    if job and (trials_root := job.workdir / "trials").is_dir():
        for legacy in trials_root.rglob("*.mojo_webm.webm"):
            try:
                legacy.unlink(missing_ok=True)
            except OSError:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # prune stale GIF→WebM cache files from previous sessions
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _cleanup_webm_cache)

    # start the monitor background broadcast task
    broadcast_task = asyncio.create_task(monitor.broadcast_updates())
    yield

    # cleanup on shutdown
    broadcast_task.cancel()

    try:
        await broadcast_task
    except asyncio.CancelledError:
        pass


dojo_app = FastAPI(title="MuJoCo Mojo Dojo", lifespan=lifespan)
dojo_app.mount("/mojo-static", shared.static, name="mojo_static")


@dojo_app.get("/")
async def root_redirect():
    return RedirectResponse(url="/monitor")


@dojo_app.exception_handler(status.HTTP_401_UNAUTHORIZED)
async def auth_exception_handler(request: Request, exc: HTTPException):
    """
    Catch 401 errors and render our custom HTML page.
    Crucial: We MUST include the 'WWW-Authenticate' header so the browser
    knows it should still try to show the login popup first.
    """
    return shared.templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "request": request,
            "status_code": 401,
            "title": "Access Denied",
            "message": "The Mojo Dojo is currently locked. Correct credentials are required to enter.",
            "button_text": "Try Again",
        },
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Basic"},
    )


@dojo_app.exception_handler(status.HTTP_404_NOT_FOUND)
async def not_found_exception_handler(request: Request, exc: HTTPException):
    return shared.templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "request": request,
            "status_code": 404,
            "title": "Lost in the Void",
            "message": "The page you are looking for was not able to be found.",
        },
        status_code=status.HTTP_404_NOT_FOUND,
    )


dependencies = [Depends(validate_dojo_auth)]
dojo_app.include_router(monitor.router, prefix="/monitor", dependencies=dependencies)
dojo_app.include_router(mosaic.router, prefix="/mosaic", dependencies=dependencies)
dojo_app.include_router(morph.router, prefix="/morph", dependencies=dependencies)
if _sensai_router is not None:
    dojo_app.include_router(
        _sensai_router.router, prefix="/sensai", dependencies=dependencies
    )
