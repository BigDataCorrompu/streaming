#!/usr/bin/env python3
"""
Core UNIFIE: gere series (magnet/torrents) ET films (liens directs/webdl).
Remplace torbox_b2_core.py et torbox_b2_core_movies.py.

Concept: un "item" a telecharger a toujours:
  - une source (magnet OU lien direct)
  - un chemin de destination sur B2
  - un nom final (sans extension)
  - un type: "torrent" ou "webdl" (determine automatiquement le bon endpoint TorBox)
"""

import time
import subprocess
import requests
import os
from dotenv import load_dotenv

# Charge les variables du fichier .env
load_dotenv()

# Recupere la valeur de la variable
torbox_api_key = os.getenv("TORBOX_API_KEY")

TORBOX_API_KEY = torbox_api_key
TORBOX_BASE = "https://api.torbox.app/v1/api"
B2_BUCKET = "ProjectLatamStreaming"
POLL_INTERVAL = 15

HEADERS_TORBOX = {"Authorization": f"Bearer {TORBOX_API_KEY}"}


# ============================================================
# TORBOX - couche commune (torrent OU webdl selon le type)
# ============================================================

def _endpoint_for(kind):
    return "torrents" if kind == "torrent" else "webdl"


def _remote_for(kind):
    return "torbox"  # TorBox expose torrents ET webdl sur le meme WebDAV/remote rclone


def add_download(source, kind, password=None):
    """
    source: magnet (si kind='torrent') ou lien direct (si kind='webdl')
    Retourne (id, hash)
    """
    endpoint = _endpoint_for(kind)
    field = "magnet" if kind == "torrent" else "link"
    data = {field: source}
    if password:
        data["password"] = password

    r = requests.post(
        f"{TORBOX_BASE}/{endpoint}/create{('torrent' if kind=='torrent' else 'webdownload')}",
        headers=HEADERS_TORBOX,
        data=data,
    )
    r.raise_for_status()
    resp = r.json()["data"]
    item_id = resp.get("torrent_id") or resp.get("webdownload_id") or resp.get("id")
    item_hash = resp.get("hash")
    return item_id, item_hash


def find_item_info(item_id, item_hash, kind, max_retries=5):
    endpoint = _endpoint_for(kind)
    for attempt in range(max_retries):
        try:
            r = requests.get(f"{TORBOX_BASE}/{endpoint}/mylist", headers=HEADERS_TORBOX, timeout=30)
            if r.status_code >= 500:
                print(f"       (erreur serveur {r.status_code} sur mylist, retry {attempt+1}/{max_retries}...)")
                time.sleep(10)
                continue
            r.raise_for_status()
            all_items = r.json()["data"]
            if isinstance(all_items, dict):
                all_items = [all_items]

            for item in all_items:
                if item_id and item.get("id") == item_id:
                    return item
                if item_hash and item.get("hash") == item_hash:
                    return item
            return None
        except requests.exceptions.RequestException as e:
            print(f"       (erreur reseau sur mylist: {e}, retry {attempt+1}/{max_retries}...)")
            time.sleep(10)

    raise Exception(f"Impossible de contacter TorBox mylist apres {max_retries} tentatives")


def wait_for_completion(item_id, item_hash, kind, label):
    while True:
        try:
            info = find_item_info(item_id, item_hash, kind)
        except Exception as e:
            print(f"       [{label}] {e}, nouvelle tentative dans 30s...")
            time.sleep(30)
            continue

        if info is None:
            print(f"       [{label}] introuvable dans mylist, retry...")
            time.sleep(POLL_INTERVAL)
            continue

        progress = info.get("progress", 0) * 100
        state = info.get("download_state", "?")
        print(f"       [{label}] {state} - {progress:.1f}%", end="\r")

        if info.get("download_finished") or info.get("cached"):
            print(f"\n       [{label}] Termine")
            return info

        time.sleep(POLL_INTERVAL)


def get_source_folder(item_id, item_hash, kind, label, max_retries=10):
    """Trouve le dossier (ou None si fichier a plat) sur le remote rclone correspondant."""
    info = find_item_info(item_id, item_hash, kind)
    if not info or not info.get("files"):
        raise Exception(f"Impossible de retrouver les fichiers de {label}")

    first_file_name = info["files"][0]["name"]
    parts = first_file_name.split("/")
    expected_folder = parts[0] if len(parts) > 1 else None
    remote = _remote_for(kind)

    for attempt in range(max_retries):
        result = subprocess.run(
            ["rclone", "lsf", f"{remote}:", "--dirs-only"],
            capture_output=True, text=True
        )
        folders = [f.rstrip("/") for f in result.stdout.strip().split("\n") if f]

        if expected_folder is None:
            # fichier attendu a la racine
            result_files = subprocess.run(
                ["rclone", "lsf", f"{remote}:"],
                capture_output=True, text=True
            )
            all_items = [f for f in result_files.stdout.strip().split("\n") if f]
            if parts[-1] in all_items:
                return None
        elif expected_folder in folders:
            return expected_folder

        time.sleep(3)

    raise Exception(f"Source introuvable sur {remote}: apres {max_retries} tentatives")


def cleanup_source(item_id, item_hash, kind, source_folder):
    remote = _remote_for(kind)
    if kind == "torrent":
        if source_folder:
            subprocess.run(["rclone", "purge", f"{remote}:{source_folder}/"], check=False)
    else:
        # webdl: nettoyage via API (pas de notion de dossier fiable a purge)
        info = find_item_info(item_id, item_hash, kind)
        if info:
            requests.post(
                f"{TORBOX_BASE}/webdl/controlwebdownload",
                headers=HEADERS_TORBOX,
                json={"webdownload_id": info["id"], "operation": "delete"},
            )


# ============================================================
# B2 - couche commune
# ============================================================

def item_exists_on_b2(dest_path, new_name):
    """Verifie si un fichier video pour ce nom existe deja sur B2."""
    result = subprocess.run(
        ["rclone", "lsf", f"b2:{B2_BUCKET}/{dest_path}/"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return False

    existing_files = result.stdout.strip().split("\n")
    for f in existing_files:
        if f.startswith(new_name + ".") and f.split(".")[-1].lower() in ("mkv", "mp4"):
            return True
    return False


def sync_and_rename(item_id, item_hash, kind, dest_path, new_name, label, max_retries=5):
    """
    dest_path: ex "Series/House of the Dragon/Season 01" ou "Films"
    new_name: ex "HOTD S01E01" ou "El Retorno del Rey"
    """
    source_folder = get_source_folder(item_id, item_hash, kind, label)
    remote = _remote_for(kind)
    tmp_folder = f"_tmp_{new_name.replace(' ', '_')}"

    source_path = f"{remote}:{source_folder}/" if source_folder else f"{remote}:"

    subprocess.run(
        ["rclone", "copy", source_path, f"b2:{B2_BUCKET}/{dest_path}/{tmp_folder}/",
         "--include", "*.mkv", "--include", "*.mp4", "--include", "*.srt", "--progress"],
        check=False
    )

    files = []
    for attempt in range(max_retries):
        result = subprocess.run(
            ["rclone", "lsf", f"b2:{B2_BUCKET}/{dest_path}/{tmp_folder}/"],
            capture_output=True, text=True
        )
        files = [f for f in result.stdout.strip().split("\n") if f]
        has_video = any(f.split(".")[-1].lower() in ("mkv", "mp4") for f in files)
        if has_video:
            break
        print(f"       [{label}] video pas encore visible sur B2, retry...")
        time.sleep(5)

    for f in files:
        ext = f.split(".")[-1]
        old = f"b2:{B2_BUCKET}/{dest_path}/{tmp_folder}/{f}"
        new = f"b2:{B2_BUCKET}/{dest_path}/{new_name}.{ext}"
        subprocess.run(["rclone", "moveto", old, new])

    subprocess.run(["rclone", "rmdir", f"b2:{B2_BUCKET}/{dest_path}/{tmp_folder}/"], check=False)
    cleanup_source(item_id, item_hash, kind, source_folder)


# ============================================================
# API PUBLIQUE - utilisee par les scrapers
# ============================================================

def process_series_episode(magnet, folder_name, tag, season, ep):
    """Series: identifie par saison/episode, source = magnet (torrent)."""
    label = f"S{season:02d}E{ep:02d}"
    print(f"\n=== {folder_name} {label} (tag: {tag}) ===")

    dest_path = f"Series/{folder_name}/Season {season:02d}"
    new_name = f"{tag} {label}"

    if item_exists_on_b2(dest_path, new_name):
        print(f"      SKIP: {new_name} existe deja sur B2")
        return True

    if not magnet:
        print(f"      SKIP: pas de magnet pour {label}")
        return False

    item_id, item_hash = add_download(magnet, kind="torrent")
    wait_for_completion(item_id, item_hash, "torrent", label)
    sync_and_rename(item_id, item_hash, "torrent", dest_path, new_name, label)

    if not item_exists_on_b2(dest_path, new_name):
        print(f"      ECHEC: {new_name} - video absente apres transfert")
        return False

    print(f"      OK: {new_name}")
    return True


def process_movie(link, movie_name, password=None, dest_path="Films"):
    """Films: source = lien direct (webdl)."""
    label = movie_name
    print(f"\n=== FILM: {movie_name} ===")

    if item_exists_on_b2(dest_path, movie_name):
        print(f"      SKIP: {movie_name} existe deja sur B2")
        return True

    if not link:
        print(f"      SKIP: pas de lien pour {movie_name}")
        return False

    item_id, item_hash = add_download(link, kind="webdl", password=password)
    wait_for_completion(item_id, item_hash, "webdl", label)
    sync_and_rename(item_id, item_hash, "webdl", dest_path, movie_name, label)

    if not item_exists_on_b2(dest_path, movie_name):
        print(f"      ECHEC: {movie_name} - video absente apres transfert")
        return False

    print(f"      OK: {movie_name}")
    return True