# procon
Trabalho Final Extração Automatizada de dados - Comparação cesta basica procom

# Cesta Básica – Extração Automatizada e API

Este projeto implementa um pipeline completo para **extração, transformação e exposição** de preços da cesta básica em diversas fontes (PROCON, DIEESE, SIDRA) e disponibiliza uma API REST e interface web para consulta.

├── LICENSE
├── README.md
├── requirements.txt
├── notebooks/ # ETL e análises em Jupyter (exemplos)
│ └── etl_cesta_basica.ipynb
├── raw/ # Dados brutos
│ ├── relatorios_procon/ # PDFs PROCON
│ └── dieese/ # PDFs DIEESE
├── data/ # Dados tratados
│ ├── ipca_goias.csv
│ ├── precos_amadeus.json
│ ├── precos_travelpayouts.json
│ └── prices.db # SQLite com tabela basket_prices
├── scraper/
│ └── procon_scraper.py # Coleta HTML/PDF/API SIDRA
├── src/
│ ├── process_prices.py # Extrai preços e popula SQLite
│ └── fastapi_app.py # FastAPI + Jinja2 UI
└── .gitignore

yaml
Copiar
Editar

---

## 🚀 Como Começar

### 1. Pré-requisitos

- Python **3.10+**
- `git`
- (Opcional) [poetry](https://python-poetry.org/) ou `pipenv`

### 2. Clonar e criar ambiente

```bash
git clone https://github.com/SEU_USUARIO/projeto-cesta-basica.git
cd projeto-cesta-basica
python -m venv .venv
source .venv/bin/activate     # Linux/macOS
.venv\Scripts\activate        # Windows
3. Instalar dependências
bash
Copiar
Editar
pip install --upgrade pip
pip install -r requirements.txt
🧱 Pipeline Resumido
bash
Copiar
Editar
[Scraper PROCON/API SIDRA/DIEESE]
           │
           ▼
[raw/relatorios_procon/*.pdf] ──► scrape_procon.py ──► data/raw/*.json, CSV
           │
           ▼
 process_prices.py
  • pdfplumber + regex
  • sqlite3 → data/prices.db
           │
           ▼
[FastAPI + Jinja2]
  • /scrape/procon   dispara coleta
  • /prices/         lista todos os preços
  • /prices/cheapest lista 3 mais baratas
  • /              UI HTML
📄 Scripts Principais
scraper/procon_scraper.py
Coleta HTML (BeautifulSoup) das notícias do PROCON filtrando por “cesta básica” ou “preço”.

Extrai PDFs vinculados e bloco de texto relevante.

Baixa todos os arquivos em raw/….

src/process_prices.py
Abre cada PDF com pdfplumber.

Localiza padrões Cesta Básica… R$ valor e tabelas.

Converte moeda (1.234,56 → 1234.56).

Insere em SQLite (tabela basket_prices).

src/fastapi_app.py
FastAPI + Jinja2Templates para UI.

Endpoints:

GET /scrape/procon → dispara scraper

GET /prices/ → lista até N preços

GET /prices/cheapest/ → top 3 mais baratos

GET /prices/{id} → detalhe por ID

🗃️ Banco de Dados (basket_prices)
Coluna	Tipo	Descrição
id	INTEGER	PK auto-incremental
source	TEXT	Origem (procon, dieese, sidra)
state	TEXT	Estado ou cidade
date	DATE	Data de referência (yyyy-mm-dd)
product	TEXT	Nome do produto (“Cesta Básica…”)
price	REAL	Valor em BRL

📊 Notebooks ETL
No diretório notebooks/ há um Jupyter Notebook (etl_cesta_basica.ipynb) que:

Carrega raw PDFs e JSONs.

Mostra transformação passo-a-passo.

Gera gráficos exploratórios.

📜 Licença & Fontes
Licença: MIT

Fontes:

PROCON Goiás – https://goias.gov.br/procon

DIEESE Cesta Básica – https://www.dieese.org.br

IBGE SIDRA – via sidrapy (tabela 1419)

APIs Amadeus, TravelPayouts, Skyscanner (quando aplicável)

📄 Como Executar
Baixar e processar dados

bash
Copiar
Editar
python scraper/procon_scraper.py
python src/process_prices.py
Executar API + UI

bash
Copiar
Editar
uvicorn src.fastapi_app:app --reload --port 8000
Acessar no navegador

UI HTML: http://127.0.0.1:8000/

JSON all: http://127.0.0.1:8000/prices/?limit=50

JSON cheapest: http://127.0.0.1:8000/prices/cheapest/?n=3

Disparar coleta: http://127.0.0.1:8000/scrape/procon

🎯 Próximos Passos
Automatizar via CI/CD (GitHub Actions).

Suporte a múltiplos estados/fonte extra.

Dashboard interativo (Plotly/Dash, Grafana).

markdown
Copiar
Editar
# Licença

MIT License © 2025
Aluno : Flávio Eustáquio de Oliveira
Aluno : Filipe Maruyama Cardinli
Aluno : Reginaldo Santos
Aluno : Wemerson G. de Souza
