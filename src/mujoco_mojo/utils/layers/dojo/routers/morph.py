from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import HTMLResponse

from mujoco_mojo.utils.log import get_logger

from .. import shared

logger = get_logger(__name__)

router = APIRouter()

from starlette.types import Receive, Scope, Send


class WSGIPrefixRestorer:
    """
    Tiny ASGI middleware that restores the prefix stripped by Starlette's mount.
    This ensures the Optuna WSGI app sees the full path it expects.
    """

    def __init__(self, app, prefix):
        self.app = app
        self.prefix = prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            # Restore the prefix (e.g., /api) to the path
            scope["path"] = self.prefix + scope["path"]
        await self.app(scope, receive, send)


@router.get("/", response_class=HTMLResponse)
async def get_optimizer(request: Request):
    """Serves the wrapper frame for the Optuna Dashboard."""
    return shared.templates.TemplateResponse(
        request=request, name="morph.html", context={"request": request}
    )


def mount_optuna_engine(app: FastAPI, storage_url: str):
    """Mounts the Optuna Dashboard as a sub-app at /morph."""
    import warnings

    try:
        import optuna
        import optuna_dashboard
    except ModuleNotFoundError:
        msg = "The `optuna` and `optuna-dashboard` packages are required to view optimization jobs in the Dojo. Install with `uv add mujoco-mojo[optimize]` or `pip install mujoco-mojo[optimize]`"
        logger.exception(msg)
        raise ModuleNotFoundError(msg)

    from fastapi.middleware.wsgi import WSGIMiddleware
    from fastapi.staticfiles import StaticFiles

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    warnings.filterwarnings("ignore", category=optuna.exceptions.ExperimentalWarning)
    warnings.filterwarnings("ignore", category=UserWarning, module="optuna_dashboard")

    app.mount(
        "/static",
        StaticFiles(directory=Path(optuna_dashboard.__file__).parent / "public"),
        name="optuna_static",
    )

    optuna_wsgi = WSGIMiddleware(optuna_dashboard.wsgi(storage=storage_url))
    app.mount("/api", WSGIPrefixRestorer(optuna_wsgi, "/api"))
    app.mount("/dashboard", WSGIPrefixRestorer(optuna_wsgi, "/dashboard"))
