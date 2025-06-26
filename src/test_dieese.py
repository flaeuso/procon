#!/usr/bin/env python3
from scraper.procon_scraper import scrape_dieese
from pprint import pprint

if __name__ == "__main__":
    print("=== Teste de coleta DIEESE ===")
    pdf_paths = scrape_dieese()
    pprint(pdf_paths)
    print(f"Total PDFs DIEESE: {len(pdf_paths)}")
