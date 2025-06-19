import sqlite3
from pathlib import Path

# ----------------------------------------------------
# CONFIGURAÇÃO DE CAMINHOS
# ----------------------------------------------------
HERE = Path(__file__).resolve().parent     # .../procon/src
PROJECT_ROOT = HERE.parent                  # .../procon
DB_PATH = PROJECT_ROOT / "data" / "prices.db"

# ----------------------------------------------------
# ABRE CONEXÃO E EXIBE INFORMAÇÕES
# ----------------------------------------------------
def main():
    # Garante que o arquivo existe
    if not DB_PATH.exists():
        print(f"Arquivo não encontrado: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1) Lista todas as tabelas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print("Tabelas encontradas:", tables)

    # 2) Para cada tabela, mostra esquema e até 5 registros
    for table in tables:
        print(f"\nEsquema da tabela '{table}':")
        cursor.execute(f"PRAGMA table_info('{table}');")
        for cid, name, col_type, notnull, dflt, pk in cursor.fetchall():
            print(f"  - {name} ({col_type}), NOT NULL={bool(notnull)}, PK={bool(pk)}")

        print(f"\nPrimeiros 5 registros de '{table}':")
        cursor.execute(f"SELECT * FROM {table} LIMIT 5;")
        rows = cursor.fetchall()
        if rows:
            # imprime colunas como cabeçalho
            cols = [d[0] for d in cursor.description]
            print(" | ".join(cols))
            for r in rows:
                print(" | ".join(str(x) for x in r))
        else:
            print("  (nenhum registro)")

    conn.close()

if __name__ == "__main__":
    main()
