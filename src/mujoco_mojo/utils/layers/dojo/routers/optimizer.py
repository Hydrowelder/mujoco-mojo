from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import HTMLResponse

from .. import shared

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
        request=request, name="optimizer.html", context={"request": request}
    )


def mount_optuna_engine(app: FastAPI, storage_url: str):
    """Mounts the Optuna Dashboard as a sub-app at /optimizer."""
    import optuna_dashboard
    from fastapi.middleware.wsgi import WSGIMiddleware
    from fastapi.staticfiles import StaticFiles

    app.mount(
        "/static",
        StaticFiles(directory=Path(optuna_dashboard.__file__).parent / "public"),
        name="optuna_static",
    )

    optuna_wsgi = WSGIMiddleware(optuna_dashboard.wsgi(storage=storage_url))
    app.mount("/api", WSGIPrefixRestorer(optuna_wsgi, "/api"))
    app.mount("/dashboard", WSGIPrefixRestorer(optuna_wsgi, "/dashboard"))
