from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


router = APIRouter()
templates = Jinja2Templates(directory="web/templates")


@router.get("/", response_class=HTMLResponse)
async def debug_map(request: Request):
    host = request.headers.get("host", "localhost:8000")
    return templates.TemplateResponse(request, "debug_map.html", {"host": host})


@router.get("/garage", response_class=HTMLResponse)
async def debug_garage(request: Request):
    host = request.headers.get("host", "localhost:8000")
    return templates.TemplateResponse(request, "debug_garage.html", {"host": host})
