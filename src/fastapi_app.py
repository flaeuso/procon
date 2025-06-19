import os
import sys
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# ----------------------------------------------------
# Configuração de paths e imports
# ----------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))    # pasta src
PARENT_DIR = os.path.dirname(BASE_DIR)
for p in (BASE_DIR, PARENT_DIR):
    if p not in sys.path:
        sys.path.append(p)

# Import do scraper existente
from scraper.procon_scraper import scrape_and_save

# Banco de dados
PROJECT_ROOT = PARENT_DIR
DB_PATH = Path(PROJECT_ROOT) / "data" / "prices.db"

# Templates e estáticos
templates = Jinja2Templates(directory=str(Path(BASE_DIR) / "templates"))
static_dir = Path(BASE_DIR) / "static"

# ----------------------------------------------------
# Inicializa FastAPI
# ----------------------------------------------------
app = FastAPI(title="Procon & Cesta Básica")

# monta arquivos estáticos em /static
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ----------------------------------------------------
# Modelos
# ----------------------------------------------------
class BasketPrice(BaseModel):
    id: int
    source: str
    state: str | None
    date: str | None
    product: str
    price: float

# ----------------------------------------------------
# Utilitário para conexão ao DB
# ----------------------------------------------------
def get_db_connection():
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Banco não encontrado: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ----------------------------------------------------
# Endpoints de scraping
# ----------------------------------------------------
@app.get("/scrape/procon")
def scrape_procon():
    """
    Dispara o scraper do PROCON, retorna arquivos baixados.
    """
    files = scrape_and_save()
    return {
        "status": "ok",
        "arquivos_baixados": files,
        "quantidade": len(files)
    }

# ----------------------------------------------------
# Endpoints de API JSON
# ----------------------------------------------------
@app.get("/prices/", response_model=list[BasketPrice])
def read_all_prices(limit: int = 100):
    """
    Retorna até `limit` registros ordenados por data decrescente.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM basket_prices ORDER BY date DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [BasketPrice(**dict(r)) for r in rows]

@app.get("/prices/cheapest/", response_model=list[BasketPrice])
def read_cheapest(n: int = 3):
    """
    Retorna as `n` ofertas mais baratas.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM basket_prices ORDER BY price ASC LIMIT ?", (n,))
    rows = cur.fetchall()
    conn.close()
    return [BasketPrice(**dict(r)) for r in rows]

@app.get("/prices/{item_id}", response_model=BasketPrice)
def read_price(item_id: int):
    """
    Retorna um registro específico por ID.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM basket_prices WHERE id = ?", (item_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return BasketPrice(**dict(row))

# ----------------------------------------------------
# Endpoint HTML principal
# ----------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request, n: int = 3):
    """
    Página HTML que exibe as `n` cestas mais baratas.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM basket_prices ORDER BY price ASC LIMIT ?", (n,))
    rows = cur.fetchall()
    conn.close()

    ofertas = [BasketPrice(**dict(r)) for r in rows]
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "ofertas": ofertas,
            "n": n
        }
    )
