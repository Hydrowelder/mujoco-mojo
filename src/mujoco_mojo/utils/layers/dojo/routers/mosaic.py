from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from mujoco_mojo.utils.log import get_logger

from ..shared import templates

logger = get_logger(__name__)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def get_mosaic(request: Request):
    """Serves the initial mosiac frame."""
    return templates.TemplateResponse(name="mosaic.html", context={"request": request})
