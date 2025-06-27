import sqlite3
import pdfplumber
import re
import statistics
from pathlib import Path
from datetime import datetime

# ----------------------------------------------------
# CONFIGURAÇÃO DE CAMINHOS (paths)
# ----------------------------------------------------
HERE = Path(__file__).resolve().parent           # pasta src
PROJECT_ROOT = HERE.parent                        # pasta procon
DB_DIR = PROJECT_ROOT / "data"
DB_PATH = DB_DIR / "prices.db"                   # arquivo de banco SQLite
PROCON_PDF_DIR = PROJECT_ROOT / "raw" / "relatorios_procon"  # PDFs do PROCON
DIEESE_PDF_DIR = PROJECT_ROOT / "raw"                           # PDFs do DIEESE

# ----------------------------------------------------
# FUNÇÃO: inicializa banco de dados e cria tabela
# ----------------------------------------------------
def init_db(path: Path):
    """
    Cria diretório do banco se necessário e inicializa tabela 'basket_prices'.
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
# FUNÇÃO: extrai preços de cesta básica de um PDF com filtragem de outliers
# ----------------------------------------------------
def extract_prices_from_pdf(pdf_path: Path, source: str, state: str):
    """
    Abre o PDF com pdfplumber, extrai texto e busca dois padrões:
    1) Inline: "Cidade (R$ 467,65)"
    2) Em tabela: linhas iniciando com Cidade seguida do valor
    Filtra outliers que estejam fora de ±70% da mediana.
    Retorna lista de tuplas para inserção no banco.
    """
    results = []
    # extrai texto completo do PDF
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    # regex para captura inline: nome da cidade e valor entre parênteses
    inline_rx = re.compile(
        r"([A-Za-zÀ-ÿ ]+?)\s*\(\s*R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\s*\)",
        re.IGNORECASE
    )
    # regex para captura em tabela: linha que começa com cidade seguido de valor
    table_rx = re.compile(
        r"^([A-Za-zÀ-ÿ ]+?)\s+([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\b",
        re.MULTILINE
    )

    # extrai data do nome do arquivo (formato YYYYMM)
    fn = pdf_path.stem
    dt_match = re.search(r"(\d{4})[^\d]?(\d{2})", fn)
    if dt_match:
        year, month = int(dt_match.group(1)), int(dt_match.group(2))
        date = datetime(year, month, 1).date()
    else:
        date = None

    # 1) capturar ocorrências inline
    for city, raw in inline_rx.findall(text):
        price = float(raw.replace('.', '').replace(',', '.'))
        results.append((source, city.strip(), date, 'Cesta Básica', price))

    # 2) capturar ocorrências em tabela
    for city, raw in table_rx.findall(text):
        # evita duplicar casos já capturados inline
        if f"{city}(" not in text:
            price = float(raw.replace('.', '').replace(',', '.'))
            results.append((source, city.strip(), date, 'Cesta Básica', price))

    # Filtragem de outliers via mediana ±70%
    if results:
        prices = [r[4] for r in results]
        med = statistics.median(prices)
        lower, upper = med * 0.3, med * 1.7
        filtered = [r for r in results if lower <= r[4] <= upper]
        return filtered

    return results

# ----------------------------------------------------
# ROTINA PRINCIPAL: processar PDFs e salvar no banco
# ----------------------------------------------------
def main():
    conn = init_db(DB_PATH)
    cursor = conn.cursor()

    # Processa PDFs do PROCON (estado GO)
    for pdf in PROCON_PDF_DIR.glob('*.pdf'):
        print(f"Extraindo PROCON: {pdf.name}")
        rows = extract_prices_from_pdf(pdf, source='procon', state='GO')
        if rows:
            cursor.executemany(
                'INSERT INTO basket_prices(source, state, date, product, price) VALUES(?,?,?,?,?)',
                rows
            )

    # Processa PDFs do DIEESE (cada cidade se torna 'state')
    for pdf in DIEESE_PDF_DIR.glob('*.pdf'):
        if 'dieese' not in pdf.name.lower():
            continue
        print(f"Extraindo DIEESE: {pdf.name}")
        rows = extract_prices_from_pdf(pdf, source='dieese', state=None)
        if rows:
            cursor.executemany(
                'INSERT INTO basket_prices(source, state, date, product, price) VALUES(?,?,?,?,?)',
                rows
            )

    conn.commit()
    conn.close()
    print('Importação concluída.')

if __name__ == '__main__':
    main()