import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# --- Ajustes de path para import local ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
for p in (BASE_DIR, PARENT_DIR):
    if p not in sys.path:
        sys.path.append(p)

# Import do scraper
from scraper.procon_scraper import scrape_and_save

# Caminho do banco SQLite
PROJECT_ROOT = PARENT_DIR
DB_PATH = Path(PROJECT_ROOT) / "data" / "prices.db"

app = FastAPI(title="API Procon & Cesta Básica")

# Monta pasta estática (CSS)
app.mount("/static", StaticFiles(directory=str(Path(BASE_DIR) / "static")), name="static")

# Templates Jinja2
templates = Jinja2Templates(directory=str(Path(BASE_DIR) / "templates"))

# Modelo Pydantic para JSON
class BasketPrice(BaseModel):
    id: int
    source: str
    state: str | None
    date: str | None
    product: str
    price: float

def get_db_connection():
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Banco não encontrado: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# -------------------
# Scraper endpoint
# -------------------
@app.get("/scrape/procon")
def scrape_procon():
    files = scrape_and_save()
    return {"status": "ok", "arquivos_baixados": files, "quantidade": len(files)}

# -------------------
# API JSON endpoints
# -------------------
@app.get("/api/prices/", response_model=list[BasketPrice])
def api_read_all_prices(limit: int = 100):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM basket_prices ORDER BY date DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [BasketPrice(**dict(r)) for r in rows]

@app.get("/api/prices/cheapest/", response_model=list[BasketPrice])
def api_read_cheapest(n: int = 3):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM basket_prices ORDER BY price ASC LIMIT ?", (n,))
    rows = cur.fetchall()
    conn.close()
    return [BasketPrice(**dict(r)) for r in rows]

# -------------------
# HTML/UI endpoints
# -------------------
@app.get("/", response_class=HTMLResponse)
def ui_home(request: Request):
    return templates.TemplateResponse("base.html", {"request": request, "now": datetime.now})

@app.get("/prices/", response_class=HTMLResponse)
def ui_all_prices(request: Request, limit: int = 100):
    items = api_read_all_prices(limit)
    return templates.TemplateResponse(
        "prices.html",
        {"request": request, "items": items, "now": datetime.now, "title": "Todos os Preços"}
    )

@app.get("/prices/cheapest/", response_class=HTMLResponse)
def ui_cheapest(request: Request, n: int = 3):
    items = api_read_cheapest(n)
    return templates.TemplateResponse(
        "prices.html",
        {"request": request, "items": items, "now": datetime.now, "title": f"Top {n} Mais Baratas"}
    )
