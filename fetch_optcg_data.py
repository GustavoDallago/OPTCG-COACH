"""
OPTCG Data Pipeline & Spoiler Downloader
Fetches sets, cards, decks, starter sets, and active spoilers from official API and CardKaizoku CDN.
Includes base-card deduplication (filters out AA/Winner/Regional variants, preserves DONs),
dynamic future set spoiler discovery (OP18, EB05, OP19+), atomic file writing, and hybrid image caching.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys
import tempfile
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

import requests

# Configuration
BASE_URL = "https://www.optcgapi.com"
DATA_DIR = "optcg_data"
IMG_DIR = os.path.join(DATA_DIR, "card_images")
CONFIG_PATH = os.path.join(DATA_DIR, "spoiler_config.json")

# Endpoints mapping based on API documentation
ENDPOINTS: Dict[str, str] = {
    "sets": "/api/allSets/",
    "set_cards": "/api/allSetCards/",
    "decks": "/api/allDecks/",
    "starter_cards": "/api/allSTCards/",
    "promo_cards": "/api/allPromoCards/",
    "don_cards": "/api/allDonCards/"
}

# Regex patterns to detect alternate arts, parallel arts, and tournament prize variants
ALT_NAME_PATTERNS = [
    r'\(parallel\)', r'\(alternate\s*art\)', r'\(alt\s*art\)', r'\(sp\)', r'\(special\)',
    r'\(box\s*topper\)', r'\(foil\)', r'\(winner\)', r'\(judge\)',
    r'\(regional\)', r'\(championship\)', r'\(store\)', r'\(cup\)', r'\(event\)',
    r'\(finals?\)', r'\(participant\)', r'\(full\s*art\)', r'\(gold\)', r'\(silver\)',
    r'\(manga\)', r'\(treasure\)', r'\(anniversary\)', r'\(cs\s*\d+\)', r'\(sealed\)',
    r'\(wanted\s*poster\)', r'\(tr\)', r'\[winner\]', r'\[finalist\]', r'\[participant\]', r'\[top\s*\d+\]'
]

ALT_IMG_PATTERNS = [
    r'_[p]\d+', r'_parallel', r'_[a-z0-9]{7}\.jpg'
]

def is_strictly_alt_card(card: Dict[str, Any]) -> bool:
    """Detects if a card is explicitly an alternate art, parallel, tournament prize, or promo variant."""
    name = (card.get("card_name") or "").lower()
    img = (card.get("card_image") or "").lower()
    
    for pat in ALT_NAME_PATTERNS:
        if re.search(pat, name, re.IGNORECASE):
            return True
            
    for pat in ALT_IMG_PATTERNS:
        if re.search(pat, img, re.IGNORECASE):
            return True
            
    return False

def load_spoiler_config() -> Dict[str, Dict[str, str]]:
    """Loads spoiler sets configuration from spoiler_config.json or returns sensible defaults."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Notice: Could not read {CONFIG_PATH}: {e}")
    return {
        "OP18": {
            "name": "Two Legends / The Dominance of God (OP18)",
            "set_id": "OP-18",
            "release_date": "2026-11-20",
            "formatted_date": "20/11/2026"
        },
        "EB05": {
            "name": "Extra Booster: Heroines Edition vol.2 (EB05)",
            "set_id": "EB-05",
            "release_date": "2026-10-30",
            "formatted_date": "30/10/2026"
        }
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
        import io
        from PIL import Image
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

def is_dynamic_spoiler_card(c: Dict[str, Any], config_sets: set) -> bool:
    """Determines whether a card from CardKaizoku belongs to an upcoming spoiler collection."""
    cid = str(c.get("cardNumber", "")).strip().upper()
    cset = str(c.get("cardSet", "")).strip().upper()
    prefix = cid.split("-")[0] if "-" in cid else cset

    if prefix in config_sets or cset in config_sets:
        return True

    # Auto-detect OP collections >= OP18
    m_op = re.match(r'^OP(\d+)$', prefix)
    if m_op and int(m_op.group(1)) >= 18:
        return True

    # Auto-detect Extra Boosters >= EB05
    m_eb = re.match(r'^EB(\d+)$', prefix)
    if m_eb and int(m_eb.group(1)) >= 5:
        return True

    # Auto-detect Starter Decks >= ST37
    m_st = re.match(r'^ST(\d+)$', prefix)
    if m_st and int(m_st.group(1)) >= 37:
        return True

    return False

def fetch_cardkaizoku_spoilers() -> List[Dict[str, Any]]:
    """
    Dynamically discovers and fetches active spoiler cards (OP18, EB05, OP19+) from CardKaizoku CDN.
    Uses manifest target with fallbacks.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.cardkaizoku.com/spoilers'
    }
    spoiler_cfg = load_spoiler_config()
    config_sets = set(spoiler_cfg.keys())

    card_data_url = "https://cdn.cardkaizoku.com/card_data.json"
    try:
        man_resp = requests.get("https://cdn.cardkaizoku.com/manifest.json", headers=headers, timeout=10)
        if man_resp.status_code == 200:
            man = man_resp.json()
            curr = man.get("cardData", {}).get("current")
            if curr:
                card_data_url = f"https://cdn.cardkaizoku.com/{curr}"
    except Exception:
        pass

    try:
        print("Checking CardKaizoku for active spoiler reveals...")
        resp = requests.get(card_data_url, headers=headers, timeout=20)
        if resp.status_code == 200:
            all_cards = resp.json()
            spoiler_cards = [c for c in all_cards if is_dynamic_spoiler_card(c, config_sets)]
            
            detected_sets = sorted(list(set(
                str(c.get("cardNumber", "")).split("-")[0].upper()
                for c in spoiler_cards if "-" in str(c.get("cardNumber", ""))
            )))
            print(f"Found {len(spoiler_cards)} spoiler cards across sets: {detected_sets}")
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

def map_kaizoku_spoiler_card(c: Dict[str, Any], spoiler_cfg: Optional[Dict[str, Dict[str, str]]] = None) -> Dict[str, Any]:
    """Maps CardKaizoku raw card payload to standard schema with dynamic set configuration."""
    if spoiler_cfg is None:
        spoiler_cfg = load_spoiler_config()

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
    
    # Resolve metadata from spoiler_config.json with dynamic fallbacks
    if prefix in spoiler_cfg:
        cfg = spoiler_cfg[prefix]
        set_id = cfg.get("set_id") or (f"OP-{prefix.replace('OP', '')}" if prefix.startswith("OP") else (f"EB-{prefix.replace('EB', '')}" if prefix.startswith("EB") else prefix))
        release_date = cfg.get("release_date")
        set_name = cfg.get("name") or f"{prefix} Spoilers"
    else:
        if prefix.startswith("OP"):
            set_id = f"OP-{prefix.replace('OP', '')}"
        elif prefix.startswith("EB"):
            set_id = f"EB-{prefix.replace('EB', '')}"
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

def evaluate_base_card_score(card: Dict[str, Any]) -> int:
    """
    Evaluates a candidate card entry.
    Higher score indicates the canonical base normal version over AA/winner variants.
    """
    name = (card.get("card_name") or "").strip()
    img = (card.get("card_image") or "").strip()
    cid = str(card.get("card_set_id") or card.get("card_id") or "").strip().upper()

    score = 100

    # Image URL and naming analysis
    if img:
        img_lower = img.lower()
        if re.search(r'_[r]\d+', img_lower):
            score -= 10  # Standard reprints slightly lower priority than original base, but valid
        if re.search(rf'{re.escape(cid.lower())}\.(jpg|webp|png)$', img_lower):
            score += 25
        elif re.search(rf'{re.escape(cid.lower())}_en\.(jpg|webp|png)$', img_lower):
            score += 20

    # Clean name without extra parenthesis is strongly preferred
    clean_name = re.sub(r'\s*\([A-Z0-9\-]+\)', '', name).strip()
    if '(' not in clean_name and '[' not in clean_name:
        score += 15

    if img and img != 'None' and 'placeholder' not in img:
        score += 5

    return score

def clean_card_name(name: str) -> str:
    """Cleans tournament pack, winner, regional, and set ID annotations from card names."""
    if not name:
        return name
    cleaned = re.sub(r'\s*-\s*[A-Z0-9]+-\d+', '', name)
    cleaned = re.sub(r'\s*\([A-Z0-9]+-\d+\)', '', cleaned)
    cleaned = re.sub(r'\s*\((?:Winner|Regional|Finalist|Participant|Judge|Store|Event|Tournament|CS\s*\d+|Pack|Vol\.\s*\d+|Premium|Sealed|Celebration|Release|National).*?\)', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*\[(?:Winner|Finalist|Participant|Judge).*?\]', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or name

def filter_clean_cards(data: List[Dict[str, Any]], filename: str) -> List[Dict[str, Any]]:
    """
    Deduplicates and filters cards to retain strictly Base Normal cards and regular reprints.
    Removes Alternate Arts, Parallel Arts, Winner cards, Regional prize cards, Box Toppers, SPs, and Manga Arts.
    Preserves 100% of DON!! cards in don_cards.json.
    """
    if filename == "don_cards.json" or not isinstance(data, list):
        return data

    if filename == "promo_cards.json":
        # Retain only genuine P-xxx promotional cards in their base format
        p_cards = [
            c for c in data 
            if str(c.get("card_set_id") or c.get("card_id") or "").strip().upper().startswith("P-")
        ]
        grouped = defaultdict(list)
        for c in p_cards:
            cid = str(c.get("card_set_id") or c.get("card_id") or "").strip().upper()
            grouped[cid].append(c)

        result = []
        for cid, variants in grouped.items():
            non_alt = [v for v in variants if not is_strictly_alt_card(v)]
            if non_alt:
                best = dict(sorted(non_alt, key=evaluate_base_card_score, reverse=True)[0])
            else:
                best = dict(sorted(variants, key=evaluate_base_card_score, reverse=True)[0])
            best["card_name"] = clean_card_name(best.get("card_name", ""))
            result.append(best)
        print(f"Cleaned promo cards: {len(data)} -> {len(result)} (retained unique P-xxx base promos)")
        return result

    if filename == "starter_cards.json":
        valid = [c for c in data if not is_strictly_alt_card(c)]
        grouped = defaultdict(list)
        for c in valid:
            cid = str(c.get("card_set_id") or c.get("card_id") or "").strip().upper()
            if cid:
                grouped[cid].append(c)

        result = []
        for cid, variants in grouped.items():
            best = dict(sorted(variants, key=evaluate_base_card_score, reverse=True)[0])
            best["card_name"] = clean_card_name(best.get("card_name", ""))
            result.append(best)
        print(f"Cleaned starter cards: {len(data)} -> {len(result)} (retained unique base cards)")
        return result

    if filename == "set_cards.json":
        # Discard ST- cards (which belong in starter_cards.json) and strict AA/parallel variants
        valid = [
            c for c in data 
            if not str(c.get("card_set_id", "")).strip().upper().startswith("ST") 
            and not is_strictly_alt_card(c)
        ]
        grouped = defaultdict(list)
        for c in valid:
            cid = str(c.get("card_set_id") or c.get("card_id") or "").strip().upper()
            if cid:
                grouped[cid].append(c)

        result = []
        for cid, variants in grouped.items():
            best = dict(sorted(variants, key=evaluate_base_card_score, reverse=True)[0])
            best["card_name"] = clean_card_name(best.get("card_name", ""))
            result.append(best)
        print(f"Cleaned set cards: {len(data)} -> {len(result)} (retained unique base cards)")
        return result

    return data

def save_json(data: Any, filename: str) -> None:
    """Saves data into a JSON file inside optcg_data with atomic writes, spoiler enrichment, and base card filtering."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)

    filepath = os.path.join(DATA_DIR, filename)
    spoiler_cfg = load_spoiler_config()

    # Enrich set_cards.json with OP17 (local) + dynamic active spoilers (OP18, EB05, OP19+)
    if filename == "set_cards.json" and os.path.exists(filepath) and isinstance(data, list):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                existing = json.load(f)

            # 1. Preserve complete OP17 cards from local file if needed
            existing_op17 = [c for c in existing if str(c.get("card_set_id", "")).upper().startswith("OP17-")]
            fetched_op17_ids = set(str(c.get("card_set_id", "")).upper() for c in data if str(c.get("card_set_id", "")).upper().startswith("OP17-"))
            missing_op17 = [c for c in existing_op17 if str(c.get("card_set_id", "")).upper() not in fetched_op17_ids]

            # 2. Check and fetch active reveals dynamically from CardKaizoku
            spoilers_raw = fetch_cardkaizoku_spoilers()
            if spoilers_raw:
                mapped_spoilers = [map_kaizoku_spoiler_card(c, spoiler_cfg) for c in spoilers_raw]
            else:
                config_sets = set(spoiler_cfg.keys())
                mapped_spoilers = [c for c in existing if is_dynamic_spoiler_card({"cardNumber": c.get("card_set_id", ""), "cardSet": c.get("set_id", "")}, config_sets)]

            clean_base = [
                c for c in data
                if not is_dynamic_spoiler_card({"cardNumber": c.get("card_set_id", ""), "cardSet": c.get("set_id", "")}, set(spoiler_cfg.keys()))
                and not str(c.get("card_set_id", "")).upper().startswith("OP17-")
            ]

            assembled = clean_base + missing_op17 + mapped_spoilers
            data = filter_clean_cards(assembled, "set_cards.json")
            print(f"Total cards assembled & cleaned: {len(data)} (including {len(missing_op17)} OP17 cards and {len(mapped_spoilers)} spoiler cards).")
        except Exception as e:
            print(f"Notice: Could not enrich spoiler cards: {e}")
            data = filter_clean_cards(data, "set_cards.json")
    elif filename in ["starter_cards.json", "promo_cards.json"]:
        data = filter_clean_cards(data, filename)

    # Preserve custom and spoiler set metadata in sets.json
    if filename == "sets.json" and isinstance(data, list):
        known_custom_sets = [
            {"set_name": "The World's Strongest Warriors", "set_id": "OP-17"}
        ]
        for set_code, cfg in spoiler_cfg.items():
            s_id = cfg.get("set_id") or (f"OP-{set_code.replace('OP', '')}" if set_code.startswith("OP") else set_code)
            s_name = cfg.get("name") or f"{set_code} Spoilers"
            known_custom_sets.append({"set_name": s_name, "set_id": s_id})

        for ks in known_custom_sets:
            has_set = any(s.get("set_id") in [ks["set_id"], ks["set_id"].replace("-", "")] for s in data)
            if not has_set:
                data.append(ks)

    if atomic_save_json(data, filepath):
        print(f"Successfully saved {len(data) if isinstance(data, list) else 'data'} items to {filepath}")
    else:
        print(f"Failed to save {filepath}")

def main():
    print("Starting OPTCG Base Data Pipeline & Spoiler Downloader...")

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
