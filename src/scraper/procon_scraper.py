import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import sidrapy

# URL base do site do Governo de Goiás
BASE_URL = "https://goias.gov.br"
# URL específica para acessar notícias do PROCON
NEWS_URL = f"{BASE_URL}/procon/categoria/noticias/"
# Diretório de destino para salvar relatórios e downloads
DEST = "raw/relatorios_procon/"
# Subdiretório para extrair trechos HTML
HTML_EXTRACT = os.path.join(DEST, "html/")
# URLs adicionais para coleta de dados
DIEESE_URL = "https://www.dieese.org.br/analisecestabasica/analiseCestaBasicaAnteriores.html"
UEG_PDF = "https://cdn.ueg.edu.br/source/universidade_estadual_de_goias_306/noticias/69505/ConjunturaSocioeconomica_PMCBA_Ano3_Numero12.pdf"
# Termos-chave para filtrar notícias relevantes
TERMS = ["preço", "preços", "cesta básica"]


def normalize_url(href, base):
    """
    Normaliza URLs: trata caminhos relativos e URLs começando com '//'.
    Retorna URL absoluta ou None se inválida.
    """
    if not href:
        return None
    # Converte URLs como '//exemplo.com' em 'https://exemplo.com'
    if href.startswith("//"):
        href = "https:" + href
    # Junta URLs relativas à base
    if not urlparse(href).netloc:
        href = urljoin(base, href)
    return href


def safe_request(url, **kwargs):
    """
    Faz requisição HTTP GET com timeout e tratamento de erros.
    Retorna o objeto Response ou None em caso de falha.
    """
    try:
        r = requests.get(url, timeout=30, **kwargs)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"[Erro] requisição {url}: {e}")
        return None


def get_filtered_post_urls():
    """
    Percorre as páginas de notícias do PROCON e filtra URLs que contenham
    termos relacionados a preços ou cesta básica.
    Retorna lista única de URLs filtradas.
    """
    urls = set()
    # Assume 121 páginas de notícias
    for p in range(1, 122):
        page = NEWS_URL if p == 1 else f"{NEWS_URL}page/{p}/"
        print("Acessando", page)
        r = safe_request(page)
        if not r:
            continue
        soup = BeautifulSoup(r.content, "html.parser")
        # Seleciona todos os links na página
        for a in soup.select("a[href]"):
            href = normalize_url(a["href"], BASE_URL)
            title = (a.get_text() or "").lower()
            # Filtra por termos no href ou no texto do link
            if href and (any(t in href.lower() for t in TERMS) or any(t in title for t in TERMS)):
                urls.add(href)
    print(f"Total notícias filtradas: {len(urls)}")
    return list(urls)


def extract_from_post(url):
    """
    Extrai PDFs e blocos de HTML com termos de preço de um post.
    Se encontrar PDFs, adiciona às 'pdfs'.
    Caso contrário, salva trechos HTML em arquivo.
    """
    r = safe_request(url)
    if not r:
        return None
    soup = BeautifulSoup(r.content, "html.parser")
    results = {"url": url, "pdfs": [], "html": None}
    # Coleta links de PDF no post
    for a in soup.select("a[href$='.pdf']"):
        pdf = normalize_url(a["href"], url)
        if pdf:
            results["pdfs"].append(pdf)
    # Se não houver PDFs, procura blocos HTML relevantes
    if not results["pdfs"]:
        blocks = [str(tag) for tag in soup.find_all(["p", "table", "ul"])
                  if "preço" in tag.get_text().lower()]
        if blocks:
            # Cria diretório de saída se não existir
            os.makedirs(HTML_EXTRACT, exist_ok=True)
            # Gera nome de arquivo a partir da URL
            fn = urlparse(url).path.strip("/").replace("/", "_") + ".html"
            path = os.path.join(HTML_EXTRACT, fn)
            # Escreve trechos encontrados no arquivo
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(blocks))
            results["html"] = path
    return results


def download_file(url):
    """
    Baixa um arquivo (PDF) via streaming e salva em DEST.
    Retorna caminho do arquivo salvo ou None.
    """
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
    """
    Orquestra o scraping das notícias filtradas:
    - Filtra URLs
    - Extrai PDFs ou HTML
    - Baixa PDFs
    Retorna lista de dicionários com resultados.
    """
    out = []
    for url in get_filtered_post_urls():
        print("Processando", url)
        info = extract_from_post(url)
        if not info:
            continue
        # Baixa cada PDF encontrado
        info["pdf_files"] = [download_file(u) for u in info["pdfs"]]
        out.append(info)
    return out


def scrape_dieese():
    """
    Coleta PDFs de análises de cesta básica no site do DIEESE.
    Retorna lista de caminhos dos PDFs baixados.
    """
    r = safe_request(DIEESE_URL)
    if not r:
        return []
    soup = BeautifulSoup(r.content, "html.parser")
    # Encontra todos os links que terminam com .pdf
    urls = [normalize_url(a["href"], DIEESE_URL)
            for a in soup.select("a[href$='.pdf']")]
    print("PDFs DIEESE encontrados:", len(urls))
    return [download_file(u) for u in urls if u]


def fetch_ipca():
    """
    Coleta série histórica do IPCA para Goiás usando a API do Sidra.
    Salva em CSV e retorna caminho.
    """
    print("Coletando IPCA Goiás via SIDRA...")
    df = sidrapy.get_table(
        table_code="1419",
        territorial_level="2",
        ibge_territorial_code="52",
        period="last 60"
    )
    os.makedirs(DEST, exist_ok=True)
    path = os.path.join(DEST, "ipca_goias.csv")
    df.to_csv(path, index=False)
    return path


def scrape_and_save():
    """
    Função principal que executa todos os scrapes:
    - PROCON
    - DIEESE
    - UEG
    - IPCA (SIDRA)
    Retorna um dicionário com os resultados de cada fonte.
    """
    results = {
        "procon": scrape_procon(),
        "dieese": [f for f in scrape_dieese() if f],
        "ueg": download_file(UEG_PDF),
        "ipca": fetch_ipca()
    }
    return results
