#!/usr/bin/env python3
"""
Test sur UN SEUL episode - cinecalidad.am - SERIES
Usage:
    python3 scraper_cinecalidad_single.py "URL_EPISODE" "Nom Dossier" "TAG" "SAISON" "EPISODE"
"""

import sys
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, ".")
from torbox_b2_core_unified import process_series_episode

HEADERS_WEB = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def get_magnet(url):
    r = requests.get(url, headers=HEADERS_WEB, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("magnet:"):
            return a["href"]
    return None


def main():
    if len(sys.argv) != 6:
        print("Usage: python3 scraper_cinecalidad_single.py <url_episode> <nom_dossier> <tag> <saison> <episode>")
        sys.exit(1)

    url = sys.argv[1]
    folder_name = sys.argv[2]
    tag = sys.argv[3]
    season = int(sys.argv[4])
    ep = int(sys.argv[5])

    print(f"[SCRAPE] {url}")
    magnet = get_magnet(url)

    if not magnet:
        print("ECHEC: aucun lien magnet trouve sur cette page")
        sys.exit(1)

    print(f"[MAGNET] {magnet[:80]}...")
    process_series_episode(magnet, folder_name, tag, season, ep)


if __name__ == "__main__":
    main()
