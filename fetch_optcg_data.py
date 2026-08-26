"""
OPTCG Data Pipeline & Spoiler Downloader
Fetches sets, cards, decks, starter sets, and active spoilers from official API and CardKaizoku CDN.
Includes atomic file writing, automatic fallback endpoints, and hybrid image management.
"""
from __future__ import annotations

import os
import sys
import json
import time
import tempfile
import datetime
import requests
from typing import Dict, Any, List, Optional

# Configuration
BASE_URL = "https://www.optcgapi.com"
DATA_DIR = "optcg_data"
IMG_DIR = os.path.join(DATA_DIR, "card_images")

# Endpoints mapping based on API documentation
ENDPOINTS: Dict[str, str] = {
    "sets": "/api/allSets/",
    "set_cards": "/api/allSetCards/",
    "decks": "/api/allDecks/",
    "starter_cards": "/api/allSTCards/",
    "promo_cards": "/api/allPromoCards/",
    "don_cards": "/api/allDonCards/"
}

def atomic_save_json(data: Any, filepath: str, indent: Optional[int] = None) -> bool:
    """
    Saves JSON data atomically using a temporary file and atomic replace.
    Prevents corrupt or empty JSON files if process terminates unexpectedly.
    Uses compact formatting by default to save storage and network bandwidth.
    """
    dirname = os.path.dirname(filepath)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)

    tmp_file = f"{filepath}.tmp_{os.getpid()}_{int(time.time()*1000)}"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            if indent is not None:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            else:
                json.dump(data, f, separators=(',', ':'), ensure_ascii=False)
        os.replace(tmp_file, filepath)
        return True
    except Exception as e:
        print(f"Error during atomic save to {filepath}: {e}")
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass
        return False

def compress_and_save_image(img_bytes: bytes, target_webp_path: str) -> bool:
    """
    Compresses raw image bytes into an optimized WebP image (max height 800px, 82% quality).
    Reduces file size by ~90-95% compared to uncompressed PNG.
    """
    try:
        from PIL import Image
        import io
        with Image.open(io.BytesIO(img_bytes)) as img:
            img = img.convert("RGB")
            if img.height > 800:
                ratio = 800.0 / img.height
                new_size = (int(img.width * ratio), 800)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            img.save(target_webp_path, "WEBP", quality=82, method=6)
            return True
    except Exception as e:
        print(f"Notice: Pillow WebP compression fallback: {e}")
        return False

def fetch_data(endpoint: str, retries: int = 3) -> Any:
    """
    Fetches JSON data from a specific API endpoint with fallback and exponential backoff retry.
    """
    url = f"{BASE_URL}{endpoint}"
    print(f"Fetching from {url}...")

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404 and endpoint == "/api/allPromoCards/":
                fallback_url = f"{BASE_URL}/api/allPromos/"
                print(f"Failed with 404. Trying fallback: {fallback_url}...")
                fallback_resp = requests.get(fallback_url, timeout=30)
                if fallback_resp.status_code == 200:
                    return fallback_resp.json()

            print(f"Warning: Attempt {attempt}/{retries} received status code {response.status_code} from {url}")
        except requests.exceptions.RequestException as e:
            print(f"Network error on attempt {attempt}/{retries} for {url}: {e}")
        except json.JSONDecodeError:
            print(f"JSON decode error on attempt {attempt}/{retries} for {url}")

        if attempt < retries:
            backoff = 2 ** (attempt - 1)
            print(f"Retrying in {backoff} seconds...")
            time.sleep(backoff)

    print(f"Error: All {retries} attempts failed for {url}")
    return None

def fetch_cardkaizoku_spoilers() -> List[Dict[str, Any]]:
    """
    Fetches active spoiler cards (OP18, EB05) from CardKaizoku CDN.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.cardkaizoku.com/spoilers'
    }
    url = "https://cdn.cardkaizoku.com/card_data.json"
    try:
        print("Checking CardKaizoku for new OP18/EB05 spoiler reveals...")
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            all_cards = resp.json()
            spoiler_cards = [
                c for c in all_cards
                if str(c.get("cardNumber", "")).upper().startswith(("OP18-", "EB05-"))
                or str(c.get("cardSet", "")).upper() in ["OP18", "EB05"]
            ]
            print(f"Found {len(spoiler_cards)} OP18/EB05 spoiler cards in CardKaizoku.")
            return spoiler_cards
    except Exception as e:
        print(f"Warning: Could not fetch spoilers from CardKaizoku: {e}")
    return []

def format_card_type(raw_type: str) -> str:
    """Normalizes raw card type strings into standard title format."""
    if not raw_type:
        return "Character"
    t = raw_type.strip().lower()
    if t == "character":
        return "Character"
    elif t == "leader":
        return "Leader"
    elif t == "event":
        return "Event"
    elif t == "stage":
        return "Stage"
    return raw_type.capitalize()

def get_or_download_spoiler_image(cid: str, prefix: str) -> str:
    """
    Hybrid Image Lifecycle Strategy:
    1. Checks if Limitless CDN already has the official image on the web.
       - If yes (HTTP 200), use CDN URL and remove local file if present (auto-cleanup).
    2. If not on CDN yet, downloads preview image and converts to optimized WebP in optcg_data/card_images/.
    """
    cdn_url = f"https://limitlesstcg.nyc3.digitaloceanspaces.com/one-piece/{prefix}/{cid}_EN.webp"
    local_webp = os.path.join(IMG_DIR, f"{cid}.webp")
    local_png = os.path.join(IMG_DIR, f"{cid}.png")

    try:
        r_cdn = requests.head(cdn_url, timeout=4)
        if r_cdn.status_code == 200:
            for old_f in [local_webp, local_png]:
                if os.path.exists(old_f):
                    try:
                        os.remove(old_f)
                        print(f"Cleaned up local file {old_f} (now available on Limitless CDN).")
                    except Exception:
                        pass
            return cdn_url
    except Exception:
        pass

    if not os.path.exists(IMG_DIR):
        os.makedirs(IMG_DIR, exist_ok=True)

    if os.path.exists(local_webp):
        return f"./optcg_data/card_images/{cid}.webp"

    kaizoku_url = f"https://cdn.cardkaizoku.com/cards_en/{prefix}/{cid}.png"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.cardkaizoku.com/'
    }
    try:
        r = requests.get(kaizoku_url, headers=headers, timeout=15)
        if r.status_code == 200:
            if compress_and_save_image(r.content, local_webp):
                print(f"Saved optimized local spoiler image (WebP): {local_webp}")
                if os.path.exists(local_png):
                    try:
                        os.remove(local_png)
                    except Exception:
                        pass
            else:
                with open(local_png, "wb") as fp:
                    fp.write(r.content)
                print(f"Downloaded local spoiler image (PNG fallback): {local_png}")
    except Exception as e:
        print(f"Notice: Could not download spoiler image for {cid}: {e}")

    if os.path.exists(local_webp):
        return f"./optcg_data/card_images/{cid}.webp"
    if os.path.exists(local_png):
        return f"./optcg_data/card_images/{cid}.png"

    return cdn_url

def map_kaizoku_spoiler_card(c: Dict[str, Any]) -> Dict[str, Any]:
    """Maps CardKaizoku raw card payload to standard schema."""
    cid = str(c.get("cardNumber", "")).strip().upper()
    c_type = format_card_type(c.get("cardType", ""))

    raw_text = (c.get("text") or "").strip().replace("<br/>", "\n").replace("<br>", "\n")
    raw_trigger = (c.get("trigger") or "").strip().replace("<br/>", "\n").replace("<br>", "\n")
    if raw_trigger and raw_trigger not in ["—", "-", "None"]:
        if not raw_trigger.startswith("[Trigger]"):
            raw_trigger = f"[Trigger] {raw_trigger}"
        if raw_text:
            card_text = f"{raw_text}\n{raw_trigger}"
        else:
            card_text = raw_trigger
    else:
        card_text = raw_text

    raw_cost = c.get("cost")
    color = c.get("color", "Red")
    is_multi_color = "/" in color or " " in color

    if c_type == "Leader":
        card_cost = None
        life = "4" if is_multi_color else "5"
    else:
        card_cost = str(raw_cost) if raw_cost is not None and str(raw_cost) != "" else "0"
        life = None

    raw_power = c.get("power")
    if c_type in ["Event", "Stage"]:
        card_power = None
    else:
        card_power = str(raw_power) if raw_power is not None and str(raw_power) != "" else None

    raw_counter = c.get("counter")
    if raw_counter is not None and str(raw_counter).isdigit() and int(raw_counter) > 0:
        counter_amount: Optional[int] = int(raw_counter)
    else:
        counter_amount = None

    raw_attr = (c.get("attribute") or "").strip()
    attribute = raw_attr if raw_attr and raw_attr != "?" else None

    rarity = (c.get("rarity") or "").strip() or None
    sub_types = (c.get("feature") or "").strip() or None

    prefix = cid.split("-")[0] if "-" in cid else "OP18"
    if prefix == "OP18":
        set_id = "OP-18"
        release_date = "2026-11-20"
        set_name = "Two Legends: OP18 Spoilers"
    elif prefix == "EB05":
        set_id = "EB-05"
        release_date = "2026-10-30"
        set_name = "Extra Booster: EB05 Spoilers"
    else:
        set_id = prefix
        release_date = None
        set_name = f"{prefix} Spoilers"

    card_image = get_or_download_spoiler_image(cid, prefix)

    return {
        "inventory_price": None,
        "market_price": None,
        "card_name": c.get("cardName", cid),
        "set_name": set_name,
        "card_text": card_text,
        "set_id": set_id,
        "rarity": rarity,
        "card_set_id": cid,
        "card_color": color,
        "card_type": c_type,
        "life": life,
        "card_cost": card_cost,
        "card_power": card_power,
        "sub_types": sub_types,
        "counter_amount": counter_amount,
        "attribute": attribute,
        "date_scraped": datetime.date.today().isoformat(),
        "release_date": release_date,
        "card_image_id": cid,
        "card_image": card_image
    }

def save_json(data: Any, filename: str) -> None:
    """Saves data into a JSON file inside optcg_data with atomic writes and spoiler enrichment."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)

    filepath = os.path.join(DATA_DIR, filename)

    # Enrich set_cards.json with OP17 (local) + active OP18/EB05 spoilers
    if filename == "set_cards.json" and os.path.exists(filepath) and isinstance(data, list):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                existing = json.load(f)

            # 1. Preserve complete OP17 cards from local file
            existing_op17 = [c for c in existing if str(c.get("card_set_id", "")).upper().startswith("OP17-")]
            fetched_op17_ids = set(str(c.get("card_set_id", "")).upper() for c in data if str(c.get("card_set_id", "")).upper().startswith("OP17-"))
            missing_op17 = [c for c in existing_op17 if str(c.get("card_set_id", "")).upper() not in fetched_op17_ids]

            # 2. Check and fetch latest OP18/EB05 reveals from CardKaizoku
            spoilers_raw = fetch_cardkaizoku_spoilers()
            if spoilers_raw:
                mapped_spoilers = [map_kaizoku_spoiler_card(c) for c in spoilers_raw]
            else:
                mapped_spoilers = [c for c in existing if str(c.get("card_set_id", "")).upper().startswith(("OP18-", "EB05-"))]

            clean_base = [
                c for c in data
                if not str(c.get("card_set_id", "")).upper().startswith(("OP17-", "OP18-", "EB05-"))
            ]

            data = clean_base + missing_op17 + mapped_spoilers
            print(f"Total cards assembled: {len(data)} (including {len(missing_op17)} OP17 cards and {len(mapped_spoilers)} OP18/EB05 spoilers).")
        except Exception as e:
            print(f"Notice: Could not enrich spoiler cards: {e}")

    # Preserve custom set metadata in sets.json
    if filename == "sets.json" and isinstance(data, list):
        known_custom_sets = [
            {"set_name": "The World's Strongest Warriors", "set_id": "OP-17"},
            {"set_name": "Extra Booster: EB-05 Spoilers", "set_id": "EB-05"},
            {"set_name": "Two Legends: OP-18 Spoilers", "set_id": "OP-18"}
        ]
        for ks in known_custom_sets:
            has_set = any(s.get("set_id") in [ks["set_id"], ks["set_id"].replace("-", "")] for s in data)
            if not has_set:
                data.append(ks)

    if atomic_save_json(data, filepath):
        print(f"Successfully saved {len(data) if isinstance(data, list) else 'data'} items to {filepath}")
    else:
        print(f"Failed to save {filepath}")

def main():
    print("Starting OPTCG API Data Downloader...")

    for name, endpoint in ENDPOINTS.items():
        data = fetch_data(endpoint)
        if data:
            save_json(data, f"{name}.json")
        else:
            print(f"Could not retrieve data for {name}.")

        time.sleep(1)

    print("\nDownload process completed.")
    print(f"All downloaded data has been saved in the '{DATA_DIR}' folder.")

if __name__ == "__main__":
    main()
