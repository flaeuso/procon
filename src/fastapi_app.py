import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime
import io

# força matplotlib a usar backend sem interface gráfica
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# — Ajuste de path para imports locais —
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
for p in (BASE_DIR, PARENT_DIR):
    if p not in sys.path:
        sys.path.append(p)

# Imports dos módulos de scraping e processamento
from scraper.procon_scraper import scrape_and_save
from process_prices import main as process_prices_main
from scraper.salario_minimo import save_to_db as save_minimum_wage  # assume retorna contagem

# Caminho do banco SQLite
DB_PATH = Path(PARENT_DIR) / "data" / "prices.db"

app = FastAPI(title="API Procon & Cesta Básica")

# Monta pasta estática
app.mount("/static", StaticFiles(directory=str(Path(BASE_DIR) / "static")), name="static")

# Templates Jinja2
templates = Jinja2Templates(directory=str(Path(BASE_DIR) / "templates"))

# --- Modelos Pydantic ---
class BasketPrice(BaseModel):
    id: int
    source: str
    state: str | None
    date: str | None
    product: str
    price: float

class MinimumWage(BaseModel):
    id: int
    date: str
    nominal: float
    necessario: float

# --- Função utilitária de conexão ao DB ---
def get_db_connection():
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Banco não encontrado: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# -----------------------------
# Endpoints de scraping & utils
# -----------------------------

@app.get("/scrape/procon")
def scrape_procon():
    files = scrape_and_save()
    return {"status": "ok", "arquivos_baixados": files, "quantidade": len(files)}

@app.get("/scrape/minimum-wage")
def scrape_minimum_wage():
    """
    Executa a coleta de salário mínimo no DIEESE e salva no banco.
    """
    count = save_minimum_wage()
    return {"status": "ok", "records": count}

@app.get("/clean_db")
def clean_db():
    conn = get_db_connection()
    conn.execute("DELETE FROM basket_prices")
    conn.commit()
    conn.close()
    return {"status": "ok", "deleted_all": True}

@app.get("/process_prices")
def process_prices():
    process_prices_main()
    return {"status": "ok", "processed": True}

# -----------------------------
# Endpoints JSON de preços
# -----------------------------

@app.get("/api/prices/", response_model=list[BasketPrice])
def api_read_all_prices():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM basket_prices ORDER BY date DESC").fetchall()
    conn.close()
    return [BasketPrice(**dict(r)) for r in rows]

@app.get("/api/prices/cheapest/", response_model=list[BasketPrice])
def api_read_cheapest(n: int = 3):
    all_prices = api_read_all_prices()
    cheapest = sorted(all_prices, key=lambda x: x.price)[:n]
    return cheapest

@app.get("/api/cities/", response_model=list[str])
def api_list_cities():
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT DISTINCT state
        FROM basket_prices
        WHERE state IS NOT NULL AND trim(state) != ''
        ORDER BY state
    """).fetchall()
    conn.close()
    return [r["state"] for r in rows]

@app.get("/api/cities/{city}/prices", response_model=list[BasketPrice])
def api_prices_by_city(city: str):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM basket_prices WHERE state = ? ORDER BY date", (city,)
    ).fetchall()
    conn.close()
    return [BasketPrice(**dict(r)) for r in rows]

@app.get("/api/cities/{city}/graph.png")
def api_city_graph(city: str):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT date, price FROM basket_prices WHERE state = ? ORDER BY date", (city,)
    ).fetchall()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail=f"Sem dados para {city}")
    dates = [datetime.fromisoformat(r["date"]) for r in rows if r["date"]]
    prices = [r["price"] for r in rows if r["date"]]
    plt.figure(figsize=(8, 4))
    plt.plot(dates, prices, marker="o")
    plt.title(f"Cesta Básica em {city}")
    plt.xlabel("Data")
    plt.ylabel("Preço (R$)")
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

@app.get("/api/minimum-wage/", response_model=list[MinimumWage])
def api_read_minimum_wage():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM minimum_wage ORDER BY date").fetchall()
    conn.close()
    return [MinimumWage(**dict(r)) for r in rows]

# -----------------------------
# Endpoints HTML / UI
# -----------------------------

@app.get("/", response_class=HTMLResponse)
def ui_home(request: Request):
    return templates.TemplateResponse("base.html", {
        "request": request,
        "now": datetime.now()
    })

@app.get("/prices/", response_class=HTMLResponse)
def ui_all_prices(request: Request):
    items = api_read_all_prices()
    return templates.TemplateResponse("prices.html", {
        "request": request,
        "items": items,
        "now": datetime.now(),
        "title": "Todos os Preços"
    })

@app.get("/prices/cheapest/", response_class=HTMLResponse)
def ui_cheapest(request: Request, n: int = 3):
    items = api_read_cheapest(n)
    return templates.TemplateResponse("prices.html", {
        "request": request,
        "items": items,
        "now": datetime.now(),
        "title": f"Top {n} Mais Baratas"
    })

@app.get("/cities/", response_class=HTMLResponse)
def ui_cities(request: Request):
    cities = api_list_cities()
    return templates.TemplateResponse("cities.html", {
        "request": request,
        "cities": cities,
        "now": datetime.now()
    })

@app.get("/cities/{city}/graph", response_class=HTMLResponse)
def ui_city_graph(request: Request, city: str):
    # o gráfico é servido por /api/cities/{city}/graph.png
    return templates.TemplateResponse("city_graph.html", {
        "request": request,
        "city": city,
        "now": datetime.now()
    })

@app.get("/salario-minimo", response_class=HTMLResponse)
def ui_salario_minimo(request: Request):
    records = api_read_minimum_wage()
    return templates.TemplateResponse("salary.html", {
        "request": request,
        "records": records,
        "now": datetime.now()
    })
