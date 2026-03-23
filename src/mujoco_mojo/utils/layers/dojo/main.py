import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from .routers import monitor, mosaic
from .shared import static


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
dojo_app.mount("/static", static, name="static")


@dojo_app.get("/")
async def root_redirect():
    return RedirectResponse(url="/monitor")


dojo_app.include_router(monitor.router, prefix="/monitor")
dojo_app.include_router(mosaic.router, prefix="/mosaic")
