"""
OPTCG Banlist Scraper (Western Meta EN)
Scrapes official Bandai EN Banned & Restricted Card announcements and updates optcg_data/banlist.json.
"""
from __future__ import annotations

import os
import re
import sys
import json
import time
import urllib.request
from typing import Dict, Any, List

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DATA_DIR = "optcg_data"
EN_BANLIST_URL = "https://en.onepiece-cardgame.com/news/restriction.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

DEFAULT_EN = {
    "banned_cards": ["OP03-040", "OP06-047", "OP06-086", "OP06-116", "ST10-001"],
    "restricted_cards": {},
    "banned_pairs": [
        ["OP07-115", "EB04-058"],
        ["OP11-040", "OP11-067"],
        ["OP11-040", "OP08-069"]
    ]
}

def atomic_save_json(data: Any, filepath: str, indent: int = 4) -> bool:
    """Saves JSON data atomically using a temporary file and atomic replace."""
    dirname = os.path.dirname(filepath)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)
    tmp_file = f"{filepath}.tmp_{os.getpid()}_{int(time.time()*1000)}"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
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

def fetch_url(url: str) -> str:
    """Performs an HTTP GET request with custom headers."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            if response.status == 200:
                return response.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[Warning] Error reaching URL ({url}): {e}")
    return ""

def parse_banlist_html(html_content: str, default_data: dict) -> dict:
    """Parses banlist HTML for banned card IDs and restricted pairs."""
    mode_data = {
        "banned_cards": list(default_data["banned_cards"]),
        "restricted_cards": dict(default_data["restricted_cards"]),
        "banned_pairs": list(default_data["banned_pairs"])
    }

    if not html_content:
        return mode_data

    # Scrape Banned Cards IDs
    banned_section = re.search(r'(?:<h4>Banned Cards</h4>|<h4>禁止カード</h4>).*?(?=<h4>|<h3>|</div>\s*</div>\s*</div>)', html_content, re.DOTALL | re.IGNORECASE)
    if banned_section:
        found_ids = re.findall(r'freewords=([A-Z0-9\-]+)', banned_section.group(0))
        if found_ids:
            mode_data["banned_cards"] = sorted(list(set(cid.upper().strip() for cid in found_ids)))

    # Scrape Banned Pairs
    pair_matches = re.findall(r'freewords=([A-Z0-9\-]+)[\s\S]*?freewords=([A-Z0-9\-]+)', html_content)
    if pair_matches:
        pairs = []
        for p1, p2 in pair_matches:
            c1, c2 = p1.upper().strip(), p2.upper().strip()
            if c1 != c2 and [c1, c2] not in pairs and [c2, c1] not in pairs:
                pairs.append([c1, c2])
        if pairs:
            mode_data["banned_pairs"] = pairs

    return mode_data

def scrape_banlist() -> bool:
    print("=" * 60)
    print("🏴‍☠️ STARTING BANLIST SCRAPER (WESTERN META EN)")
    print("=" * 60)

    en_html = fetch_url(EN_BANLIST_URL)
    en_data = parse_banlist_html(en_html, DEFAULT_EN)

    filepath = os.path.join(DATA_DIR, "banlist.json")

    existing_sets = []
    existing_starters = []
    existing_whitelist = []

    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                existing_sets = old_data.get("banned_sets", [])
                existing_starters = old_data.get("banned_starter_decks", [])
                existing_whitelist = old_data.get("whitelisted_cards", [])
        except Exception:
            pass

    banlist_structure = {
        "source": "Official Bandai ONE PIECE CARD GAME (EN)",
        "last_updated": time.strftime("%Y-%m-%d"),
        "banned_sets": existing_sets,
        "banned_starter_decks": existing_starters,
        "whitelisted_cards": existing_whitelist,
        "banned_cards": en_data["banned_cards"],
        "restricted_cards": en_data["restricted_cards"],
        "banned_pairs": en_data["banned_pairs"]
    }

    if atomic_save_json(banlist_structure, filepath):
        print(f"✅ SUCCESS! Official EN banlist updated at {filepath}")
        print(f"   Banned cards scraped: {len(en_data['banned_cards'])}")
        print(f"   Banned pairs scraped: {len(en_data['banned_pairs'])}")
        return True
    return False

if __name__ == "__main__":
    scrape_banlist()
