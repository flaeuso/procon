import requests
import sqlite3
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

# URL da página do DIEESE com a tabela de salário mínimo
SALARIO_URL = "https://www.dieese.org.br/analisecestabasica/salarioMinimo.html"
# Mesmo banco de dados usado pelo process_prices
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "prices.db"  # aponta para data/prices.db no root do projeto


# mapeamento de nomes de meses em português para número
_MONTH_MAP = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

def fetch_salario_minimo():
    """
    Busca na página do DIEESE os valores de Salário Mínimo Nominal
    e Salário Mínimo Necessário por ano.
    Retorna lista de tuplas: (date: datetime.date, nominal: float, necessario: float).
    """
    resp = requests.get(SALARIO_URL, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.content, "html.parser")
    table = soup.find("table")
    if not table:
        raise RuntimeError("Tabela de salário mínimo não encontrada.")

    resultados = []
    current_year = None

    for tr in table.find_all("tr"):
        # detecta linha de subtítulo com o ano
        classes = tr.get("class") or []
        if "subtitulo" in classes:
            ano_link = tr.find("a", attrs={"name": True})
            if ano_link and ano_link["name"].isdigit():
                current_year = int(ano_link["name"])
            continue

        # extrai colunas: mês, nominal, necessário
        tds = tr.find_all("td")
        if len(tds) != 3 or current_year is None:
            continue

        mes_str = tds[0].get_text(strip=True).lower()
        nom_str = tds[1].get_text(strip=True).replace("R$", "").strip()
        nec_str = tds[2].get_text(strip=True).replace("R$", "").strip()

        # converte valores para float
        try:
            nominal = float(nom_str.replace(".", "").replace(",", "."))
            necessario = float(nec_str.replace(".", "").replace(",", "."))
        except ValueError:
            continue

        # mapeia mês para número
        month = _MONTH_MAP.get(mes_str)
        if not month:
            continue

        date = datetime(current_year, month, 1).date()
        resultados.append((date, nominal, necessario))

    return resultados

def save_to_db():
    """
    Cria a tabela minimum_wage se não existir e insere/atualiza
    os valores buscados por ano.
    """
    # garante que o diretório existe
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # cria tabela para salário mínimo
    c.execute("""
    CREATE TABLE IF NOT EXISTS minimum_wage (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      date DATE UNIQUE,
      nominal REAL,
      necessario REAL
    )
    """)

    data = fetch_salario_minimo()

    # imprime no terminal os valores extraídos
    print(f"[SALÁRIO MÍNIMO] Registros extraídos: {len(data)}")
    for dt, nom, nec in data:
        print(f"  - {dt.isoformat()}: nominal R$ {nom:.2f}, necessário R$ {nec:.2f}")

    # insere ou atualiza cada registro
    for date, nom, nec in data:
        c.execute("""
        INSERT INTO minimum_wage(date, nominal, necessario)
        VALUES (?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
          nominal=excluded.nominal,
          necessario=excluded.necessario
        """, (date.isoformat(), nom, nec))

    conn.commit()
    conn.close()
    print(f"[OK] Gravados {len(data)} registros de salário mínimo em {DB_PATH}")

if __name__ == "__main__":
    save_to_db()
