import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import sidrapy
from datetime import datetime

# ----------------------------------------------------
# CONFIGURAÇÃO DE URLS E DIRETÓRIOS
# ----------------------------------------------------
BASE_URL = "https://goias.gov.br"
NEWS_URL = f"{BASE_URL}/procon/categoria/noticias/"
DEST = "raw/relatorios_procon/"
HTML_EXTRACT = os.path.join(DEST, "html/")
DIEESE_URL = "https://www.dieese.org.br/analisecestabasica/analiseCestaBasicaAnteriores.html"
UEG_PDF = "https://cdn.ueg.edu.br/source/universidade_estadual_de_goias_306/noticias/69505/ConjunturaSocioeconomica_PMCBA_Ano3_Numero12.pdf"
TERMS = ["preço", "preços", "cesta básica"]

# ----------------------------------------------------
# FUNÇÕES AUXILIARES
# ----------------------------------------------------
def normalize_url(href, base):
    """Normaliza um href (relativo ou absoluto) para URL completa."""
    if not href:
        return None
    if href.startswith("//"):
        href = "https:" + href
    if not urlparse(href).netloc:
        href = urljoin(base, href)
    return href

def safe_request(url, **kwargs):
    """Faz GET com timeout, retorna Response ou None em erro."""
    try:
        r = requests.get(url, timeout=30, **kwargs)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"[Erro] requisição {url}: {e}")
        return None

# ----------------------------------------------------
# SCRAPER DO PROCON
# ----------------------------------------------------
def get_filtered_post_urls():
    """Percorre páginas de notícias e filtra URLs que contenham nossos termos."""
    urls = set()
    for p in range(1, 122):
        page_url = NEWS_URL if p == 1 else f"{NEWS_URL}page/{p}/"
        print("Acessando", page_url)
        r = safe_request(page_url)
        if not r:
            continue
        soup = BeautifulSoup(r.content, "html.parser")
        for a in soup.select("a[href]"):
            href = normalize_url(a["href"], BASE_URL)
            title = (a.get_text() or "").lower()
            if href and (any(t in href.lower() for t in TERMS) or any(t in title for t in TERMS)):
                urls.add(href)
    print(f"Total notícias filtradas: {len(urls)}")
    return list(urls)

def extract_from_post(url):
    """Extrai PDFs ou trechos HTML de um post filtrado."""
    r = safe_request(url)
    if not r:
        return None
    soup = BeautifulSoup(r.content, "html.parser")
    info = {"url": url, "pdfs": [], "html": None}
    # coleta links de PDF
    for a in soup.select("a[href$='.pdf']"):
        pdf = normalize_url(a["href"], url)
        if pdf:
            info["pdfs"].append(pdf)
    # se não há PDFs, extrai blocos HTML que têm nossos termos
    if not info["pdfs"]:
        blocks = [
            str(tag) for tag in soup.find_all(["p", "table", "ul"])
            if "preço" in tag.get_text().lower()
        ]
        if blocks:
            os.makedirs(HTML_EXTRACT, exist_ok=True)
            fn = urlparse(url).path.strip("/").replace("/", "_") + ".html"
            path = os.path.join(HTML_EXTRACT, fn)
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(blocks))
            info["html"] = path
    return info

def download_file(url):
    """Baixa um PDF por streaming e salva em DEST."""
    fn = os.path.basename(urlparse(url).path)
    out = os.path.join(DEST, fn)
    os.makedirs(DEST, exist_ok=True)
    if os.path.exists(out):
        print("Já existe:", fn)
        return out
    r = safe_request(url, stream=True)
    if not r:
        return None
    with open(out, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    print("Baixado:", fn)
    return out

def scrape_procon():
    """Orquestra o scrape das notícias do PROCON."""
    results = []
    for url in get_filtered_post_urls():
        print("Processando", url)
        info = extract_from_post(url)
        if not info:
            continue
        info["pdf_files"] = [download_file(u) for u in info["pdfs"]]
        results.append(info)
    return results

# ----------------------------------------------------
# SCRAPER DO DIEESE (incluindo subdiretórios por ano)
# ----------------------------------------------------
def scrape_dieese():
    """
    Coleta TODOS os PDFs de cesta básica do DIEESE, em todas as estruturas:
      1) HTMLs de análise anteriores (analiseCestaBasicaYYYYMM.html)
         -> dentro deles, extrai links *.pdf
      2) Diretórios por ano ("/2011/", "/2012/", ...) que listam PDFs diretamente
      3) PDFs referenciados diretamente na página principal
    
    Retorna lista de caminhos locais dos arquivos baixados.
    """
    r = safe_request(DIEESE_URL)
    if not r:
        return []

    base_soup = BeautifulSoup(r.content, "html.parser")
    page_links = set()
    pdf_urls   = set()

    # 1) Captura páginas de análise anteriores (analiseCestaBasicaYYYYMM.html)
    html_rx = re.compile(r"analiseCestaBasica\d{6}\.html", re.IGNORECASE)
    for a in base_soup.select("a[href]"):
        href = a["href"]
        if html_rx.search(href):
            page_links.add(normalize_url(href, DIEESE_URL))

    # 2) Captura diretórios de ano ("/2011/", "/2012/", ...)
    dir_rx = re.compile(r"^\d{4}/$")
    for a in base_soup.select("a[href]"):
        href = a["href"]
        if dir_rx.match(href):
            page_links.add(normalize_url(href, DIEESE_URL))

    # 3) Captura PDFs diretos na página principal
    for a in base_soup.select("a[href$='.pdf']"):
        pdf_urls.add(normalize_url(a["href"], DIEESE_URL))

    # Agora para cada link de página ou diretório, buscar PDFs
    for link in page_links:
        print("Acessando DIEESE subpágina:", link)
        sub = safe_request(link)
        if not sub:
            continue
        soup = BeautifulSoup(sub.content, "html.parser")
        for a in soup.select("a[href$='.pdf']"):
            pdf_urls.add(normalize_url(a["href"], link))

    print(f"PDFs DIEESE encontrados: {len(pdf_urls)}")

    # Baixa cada PDF
    downloaded = []
    for u in pdf_urls:
        path = download_file(u)
        if path:
            downloaded.append(path)
    return downloaded

# ----------------------------------------------------
# COLETA SIDRA (IPCA)
# ----------------------------------------------------
def fetch_ipca():
    """
    Coleta IPCA de Goiás via SIDRA.
    Ajusta parâmetros para evitar erro de nível territorial.
    """
    try:
        print("Coletando IPCA Goiás via SIDRA...")
        # nível 1 = Brasil, nível 2 = UF, nível 3 = município.
        # se nível 2 falhar, coleta só nacional (nível 1).
        df = sidrapy.get_table(
            table_code="1419",
            territorial_level="2",
            ibge_territorial_code="52",  # código IBGE de Goiás
            period="last 60"
        )
    except Exception:
        print("[Aviso] Level 2 falhou, buscando nível nacional...")
        df = sidrapy.get_table(
            table_code="1419",
            territorial_level="1",
            period="last 60"
        )

    path = os.path.join(DEST, "ipca_goias.csv")
    os.makedirs(DEST, exist_ok=True)
    df.to_csv(path, index=False)
    return path

# ----------------------------------------------------
# ORQUESTRAÇÃO FINAL
# ----------------------------------------------------
def scrape_and_save():
    """
    Executa todos os scrapes e retorna um dict com os resultados:
      - procon: lista de posts+pdfs
      - dieese: lista de PDFs baixados
      - ueg: PDF único da UEG
      - ipca: CSV de IPCA
    """
    return {
        "procon": scrape_procon(),
        "dieese": scrape_dieese(),
        "ueg": download_file(UEG_PDF),
        "ipca": fetch_ipca(),
    }

# permite rodar standalone
if __name__ == "__main__":
    import json
    resultados = scrape_and_save()
    print(json.dumps(resultados, indent=2, ensure_ascii=False))
