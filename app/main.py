from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR
from app.db import init_db
from app.routes.api import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="MiniMax 用量看板", lifespan=lifespan)
app.include_router(api_router)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@app.get("/")
def index():
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return TEMPLATES.TemplateResponse(request, "dashboard.html", {})


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return TEMPLATES.TemplateResponse(request, "settings.html", {})

