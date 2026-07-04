#!/usr/bin/env python3
"""
Version BATCH - plusieurs liens mediafire (plusieurs films) d'un coup.

Usage (ligne de commande):
    ./scrapper_mediafire_batch.py "lien1|nom1" "lien2|nom2|motdepasse2" ...

Usage (fichier - format auto-detecte par extension):
    ./scrapper_mediafire_batch.py --file films.txt
    ./scrapper_mediafire_batch.py --file films.csv
    ./scrapper_mediafire_batch.py --file films.json
"""

import sys
import csv
import json

sys.path.insert(0, ".")
from torbox_b2_core_unified import process_movie


def parse_txt_line(entry):
    parts = entry.split("|")
    if len(parts) < 2:
        print(f"IGNORE (format invalide, attendu lien|nom[|password]): {entry}")
        return None
    link = parts[0].strip()
    name = parts[1].strip()
    password = parts[2].strip() if len(parts) >= 3 and parts[2].strip() else None
    return link, name, password


def load_from_txt(path):
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                parsed = parse_txt_line(line)
                if parsed:
                    entries.append(parsed)
    return entries


def load_from_csv(path):
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        sample = f.read(1024)
        f.seek(0)
        has_header = csv.Sniffer().has_header(sample) if sample.strip() else False
        reader = csv.reader(f)
        rows = list(reader)

    start = 1 if has_header else 0
    for row in rows[start:]:
        if len(row) < 2:
            continue
        link, name = row[0].strip(), row[1].strip()
        password = row[2].strip() if len(row) >= 3 and row[2].strip() else None
        if link and name:
            entries.append((link, name, password))
    return entries


def load_from_json(path):
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        for name, link in data.items():
            entries.append((link, name, None))
    elif isinstance(data, list):
        for item in data:
            link = item.get("link") or item.get("url")
            name = item.get("name") or item.get("nom")
            password = item.get("password") or item.get("mot_de_passe")
            if link and name:
                entries.append((link, name, password))
    return entries


def load_entries_from_file(path):
    if path.endswith(".csv"):
        return load_from_csv(path)
    elif path.endswith(".json"):
        return load_from_json(path)
    else:
        return load_from_txt(path)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    entries = []

    if sys.argv[1] == "--file":
        if len(sys.argv) != 3:
            print("Usage: ./scrapper_mediafire_batch.py --file films.<txt|csv|json>")
            sys.exit(1)
        entries = load_entries_from_file(sys.argv[2])
    else:
        for entry in sys.argv[1:]:
            parsed = parse_txt_line(entry)
            if parsed:
                entries.append(parsed)

    if not entries:
        print("Aucune entree valide trouvee.")
        sys.exit(1)

    success, fail = 0, 0
    for link, movie_name, password in entries:
        try:
            if process_movie(link, movie_name, password=password):
                success += 1
            else:
                fail += 1
        except Exception as e:
            print(f"      ERREUR sur {movie_name}: {e}")
            fail += 1

    print(f"\n=== TERMINE: {success} succes, {fail} echecs ===")


if __name__ == "__main__":
    main()
