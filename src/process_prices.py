import sqlite3
import pdfplumber
import re
from pathlib import Path
from datetime import datetime

# ----------------------------------------------------
# CONFIGURAÇÃO DE CAMINHOS (paths)
# ----------------------------------------------------
HERE = Path(__file__).resolve().parent           # pasta src
PROJECT_ROOT = HERE.parent                        # pasta procon
db_dir = PROJECT_ROOT / "data"
DB_PATH = db_dir / "prices.db"                   # arquivo de banco SQLite
PROCON_PDF_DIR = PROJECT_ROOT / "raw" / "relatorios_procon"  # PDFs do PROCON
DIEESE_PDF_DIR = PROJECT_ROOT / "raw"                           # PDFs do DIEESE

# ----------------------------------------------------
# FUNÇÃO: inicializa banco de dados e tabela
# ----------------------------------------------------
def init_db(path: Path):
    """
    Garante criação do diretório e inicializa o banco SQLite.
    Cria tabela 'basket_prices' se não existir.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS basket_prices (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      source TEXT,
      state TEXT,
      date DATE,
      product TEXT,
      price REAL
    )""")
    conn.commit()
    return conn

# ----------------------------------------------------
# FUNÇÃO: extrai preços de cesta básica de um PDF
# ----------------------------------------------------
def extract_prices_from_pdf(pdf_path: Path, source: str, state: str):
    """
    Abre o PDF com pdfplumber, extrai texto e busca dois padrões:
    1) Inline: \"Cidade (R$ 467,65)\"
    2) Em tabela: linhas iniciando com Cidade seguida de valor
    Retorna lista de registros para inserção.
    """
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    # Padrão inline: captura nome e valor em parênteses
    inline_rx = re.compile(
        r"([A-Za-zÀ-ÿ ]+?)\s*\(\s*R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\s*\)",
        re.IGNORECASE
    )
    # Padrão tabular: linha começa com Cidade e valor
    table_rx = re.compile(
        r"^([A-Za-zÀ-ÿ ]+?)\s+([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\b",
        re.MULTILINE
    )

    # Data extraída do nome do arquivo (YYYYMM)
    fn = pdf_path.stem
    dt_match = re.search(r"(\d{4})[^\d]?(\d{2})", fn)
    if dt_match:
        year, month = int(dt_match.group(1)), int(dt_match.group(2))
        date = datetime(year, month, 1).date()
    else:
        date = None

    # 1) procura ocorrências inline
    for city, raw in inline_rx.findall(text):
        price = float(raw.replace(".", "").replace(",", "."))
        results.append((source, city.strip(), date, "Cesta Básica", price))

    # 2) procura ocorrências em tabela
    for city, raw in table_rx.findall(text):
        # evita duplicar casos já capturados inline
        # se não houver parênteses na linha correspondente
        if f"{city} (" not in raw and city.strip():
            price = float(raw.replace(".", "").replace(",", "."))
            results.append((source, city.strip(), date, "Cesta Básica", price))

    return results

# ----------------------------------------------------
# ROTINA PRINCIPAL: processar e salvar
# ----------------------------------------------------
def main():
    conn = init_db(DB_PATH)
    cursor = conn.cursor()

    # PROCON (estado GO fixo)
    for pdf in PROCON_PDF_DIR.glob("*.pdf"):
        print(f"Extraindo PROCON: {pdf.name}")
        rows = extract_prices_from_pdf(pdf, source="procon", state="GO")
        if rows:
            cursor.executemany(
                "INSERT INTO basket_prices(source, state, date, product, price) VALUES(?,?,?,?,?)",
                rows
            )

    # DIEESE (cada cidade vira 'state')
    for pdf in DIEESE_PDF_DIR.glob("*.pdf"):
        if "dieese" not in pdf.name.lower():
            continue
        print(f"Extraindo DIEESE: {pdf.name}")
        rows = extract_prices_from_pdf(pdf, source="dieese", state=None)
        if rows:
            cursor.executemany(
                "INSERT INTO basket_prices(source, state, date, product, price) VALUES(?,?,?,?,?)",
                rows
            )

    conn.commit()
    conn.close()
    print("Importação concluída.")

if __name__ == "__main__":
    main()
