# src/compute_variation.py

import sqlite3
from pathlib import Path

import pandas as pd

def main():
    # caminhos
    HERE = Path(__file__).resolve().parent
    PROJECT_ROOT = HERE.parent
    DB_PATH = PROJECT_ROOT / "data" / "prices.db"
    OUT_XLSX = PROJECT_ROOT / "variation_index.xlsx"
    OUT_CSV  = PROJECT_ROOT / "variation_index.csv"

    # conecta
    conn = sqlite3.connect(DB_PATH)

    # 1) Média anual da cesta por estado
    basket_df = pd.read_sql(
        "SELECT state, date, price FROM basket_prices WHERE state IS NOT NULL",
        conn, parse_dates=["date"]
    )
    basket_df["year"] = basket_df["date"].dt.year
    basket_mean = (
        basket_df
        .groupby(["state", "year"])["price"]
        .mean()
        .reset_index()
        .sort_values(["state", "year"])
    )
    basket_mean["basket_pct"] = (
        basket_mean
        .groupby("state")["price"]
        .pct_change() * 100
    )

    # 2) Salário mínimo nominal anual
    wage_df = pd.read_sql(
        "SELECT date, nominal FROM minimum_wage",
        conn, parse_dates=["date"]
    )
    wage_df["year"] = wage_df["date"].dt.year
    wage_mean = (
        wage_df
        .groupby("year")["nominal"]
        .first()
        .reset_index()
        .sort_values("year")
    )
    wage_mean["wage_pct"] = wage_mean["nominal"].pct_change() * 100

    conn.close()

    # 3) Índice comparativo
    df = (
        basket_mean
        .merge(wage_mean[["year", "wage_pct"]], on="year", how="left")
        .assign(index_pct=lambda d: d["wage_pct"] - d["basket_pct"])
    )

    # 4) Gravação: tenta Excel, senão CSV
    try:
        df.to_excel(OUT_XLSX, index=False, sheet_name="Comparativo")
        print(f"[OK] Planilha Excel salva em {OUT_XLSX}")
    except ModuleNotFoundError as e:
        print(f"[AVISO] excel engine não disponível ({e}); salvando CSV em lugar disso.")
        df.to_csv(OUT_CSV, index=False)
        print(f"[OK] CSV salvo em {OUT_CSV}")

if __name__ == "__main__":
    main()
