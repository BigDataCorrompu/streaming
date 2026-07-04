#!/usr/bin/env python3
"""
Scraper specifique pour cinecalidad.am - SERIES
Usage:
    python3 scraper_cinecalidad.py "URL_SERIE" "Nom Dossier" "TAG"

Exemple:
    python3 scraper_cinecalidad.py "https://www.cinecalidad.am/ver-serie/house-of-the-dragon/" "House of the Dragon" "HOTD"
"""

import sys
import re
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, ".")
from torbox_b2_core_unified import process_series_episode

HEADERS_WEB = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def get_episode_links(series_url):
    print(f"[SCAN] {series_url}")
    r = requests.get(series_url, headers=HEADERS_WEB, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")

    episodes = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.search(r'(\d+)x(\d+)', href) or re.search(r'[Ss](\d+)[Ee](\d+)', href)
        if m and "ver-el-episodio" in href:
            season, ep = int(m.group(1)), int(m.group(2))
            episodes[(season, ep)] = href

    print(f"       {len(episodes)} episodes trouves")
    return episodes


def get_magnet(url):
    r = requests.get(url, headers=HEADERS_WEB, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("magnet:"):
            return a["href"]
    return None


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 scraper_cinecalidad.py <url_serie> <nom_dossier> <tag>")
        sys.exit(1)

    series_url, folder_name, tag = sys.argv[1], sys.argv[2], sys.argv[3]

    episodes = get_episode_links(series_url)
    if not episodes:
        print("Aucun episode trouve, verifie l'URL")
        sys.exit(1)

    success, fail = 0, 0
    for (season, ep), url in sorted(episodes.items()):
        try:
            magnet = get_magnet(url)
            if process_series_episode(magnet, folder_name, tag, season, ep):
                success += 1
            else:
                fail += 1
        except Exception as e:
            print(f"      ERREUR S{season:02d}E{ep:02d}: {e}")
            fail += 1

    print(f"\n=== TERMINE: {success} succes, {fail} echecs ===")


if __name__ == "__main__":
    main()
