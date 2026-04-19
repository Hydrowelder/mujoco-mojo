import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import mujoco_mojo.utils.layers.dojo.shared as shared

from .routers import monitor, mosaic

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


@asynccontextmanager
async def lifespan(app: FastAPI):
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


dependencies = [Depends(validate_dojo_auth)]


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


def mount_optimizer(app: FastAPI, storage_url: str):
    """Mounts the Optuna Dashboard as a sub-app at /optimizer."""
    import optuna_dashboard
    from fastapi.middleware.wsgi import WSGIMiddleware
    from fastapi.staticfiles import StaticFiles

    dojo_app.mount(
        "/static",
        StaticFiles(directory=Path(optuna_dashboard.__file__).parent / "public"),
        name="static",
    )

    optuna_app = optuna_dashboard.wsgi(storage=storage_url)
    app.mount("/", WSGIMiddleware(optuna_app))


@dojo_app.get("/optimizer")
async def optimizer_view(request: Request):
    return shared.templates.TemplateResponse(
        request=request, name="optimizer.html", context={"request": request}
    )


dojo_app.include_router(monitor.router, prefix="/monitor", dependencies=dependencies)
dojo_app.include_router(mosaic.router, prefix="/mosaic", dependencies=dependencies)
