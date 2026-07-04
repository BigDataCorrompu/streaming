#!/usr/bin/env python3
"""
Version FRIENDLY - un seul lien mediafire pour un film.

Usage:
    ./scrapper_mediafire.py "LIEN_MEDIAFIRE" "Nom du Film" [mot_de_passe]
"""

import sys

sys.path.insert(0, ".")
from torbox_b2_core_unified import process_movie


def main():
    if len(sys.argv) not in (3, 4):
        print("Usage: ./scrapper_mediafire.py <lien_mediafire> <nom_film> [mot_de_passe]")
        sys.exit(1)

    link = sys.argv[1]
    movie_name = sys.argv[2]
    password = sys.argv[3] if len(sys.argv) == 4 else None

    success = process_movie(link, movie_name, password=password)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
