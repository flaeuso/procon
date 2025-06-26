#!/usr/bin/env python3
"""
clean_db.py

Script para limpar completamente o banco de dados SQLite de preços de cesta básica.
Ele deleta todos os registros da tabela `basket_prices`. Use com cautela!
"""

import sqlite3
from pathlib import Path

# ----------------------------------------------------
# CONFIGURAÇÃO DO CAMINHO DO BANCO
# ----------------------------------------------------
HERE = Path(__file__).resolve().parent       # pasta onde está o script
PROJECT_ROOT = HERE.parent                   # pasta raiz do projeto
DB_PATH = PROJECT_ROOT / "data" / "prices.db"  # mesmo caminho usado pelo fastapi_app e process_prices

def clean_database(path: Path):
    """
    Conecta no banco em `path` e remove todos os registros da tabela basket_prices.
    Se a tabela não existir, nada acontece.
    """
    if not path.exists():
        print(f"[Aviso] Banco não encontrado em {path}")
        return

    conn = sqlite3.connect(path)
    c = conn.cursor()

    # Verifica se a tabela existe
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='basket_prices'")
    if not c.fetchone():
        print("[Aviso] Tabela 'basket_prices' não existe; nenhum dado foi removido.")
    else:
        # Deleta todos os registros
        c.execute("DELETE FROM basket_prices")
        conn.commit()
        print("[OK] Todos os registros da tabela 'basket_prices' foram removidos.")

    conn.close()

if __name__ == "__main__":
    clean_database(DB_PATH)
