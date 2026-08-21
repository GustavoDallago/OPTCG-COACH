"""
OPTCG Multi-Mode Banlist Scraper (Meta EN & Meta JP)
Scrapes official Bandai EN & Bandai JP Banned & Restricted Card announcements and updates optcg_data/banlist.json.
"""

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
JP_BANLIST_URL = "https://www.onepiece-cardgame.com/news/restriction.html"

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

DEFAULT_JP = {
    "banned_cards": ["OP03-040", "OP06-047", "OP06-086", "OP06-116", "ST10-001"],
    "restricted_cards": {},
    "banned_pairs": [
        ["OP07-115", "EB04-058"],
        ["OP11-040", "OP11-067"],
        ["OP11-040", "OP08-069"]
    ]
}

def fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            if response.status == 200:
                return response.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[Aviso] Erro ao acessar URL ({url}): {e}")
    return ""

def parse_banlist_html(html_content: str, default_data: dict) -> dict:
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
    print("🏴‍☠️ INICIANDO SCRAPER MULTI-MODO DE BANIMENTOS (EN, JP & LIVRE)")
    print("=" * 60)
    
    en_html = fetch_url(EN_BANLIST_URL)
    en_data = parse_banlist_html(en_html, DEFAULT_EN)
    
    jp_html = fetch_url(JP_BANLIST_URL)
    jp_data = parse_banlist_html(jp_html, DEFAULT_JP)
    
    banlist_structure = {
        "source": "Official Bandai ONE PIECE CARD GAME",
        "last_updated": time.strftime("%Y-%m-%d"),
        "modes": {
            "EN": {
                "name": "Meta Ocidental (EN)",
                "banned_cards": en_data["banned_cards"],
                "restricted_cards": en_data["restricted_cards"],
                "banned_pairs": en_data["banned_pairs"]
            },
            "JP": {
                "name": "Meta Oriental (JP)",
                "banned_cards": jp_data["banned_cards"],
                "restricted_cards": jp_data["restricted_cards"],
                "banned_pairs": jp_data["banned_pairs"]
            },
            "NONE": {
                "name": "Sem Banlist (Livre / Histórico)",
                "banned_cards": [],
                "restricted_cards": {},
                "banned_pairs": []
            }
        },
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
        "banned_sets": existing_sets,
        "banned_starter_decks": existing_starters,
        "whitelisted_cards": existing_whitelist,
        "banned_cards": en_data["banned_cards"],
        "restricted_cards": en_data["restricted_cards"],
        "banned_pairs": en_data["banned_pairs"]
    }

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(banlist_structure, f, indent=4, ensure_ascii=False)
            
        print(f"✅ SUCESSO! Banlist oficial atualizada preservando suas coleções/starters manuais em {filepath}")
        print(f"   Cartas banidas raspadas do site oficial EN: {len(en_data['banned_cards'])}")
        print(f"   Meta EN: {len(en_data['banned_cards'])} banidas")
        print(f"   Meta JP: {len(jp_data['banned_cards'])} banidas")
        print(f"   Livre: 0 banidas (Histórico)")
        return True
    except Exception as e:
        print(f"❌ Erro ao salvar banlist.json: {e}")
        return False

if __name__ == "__main__":
    scrape_banlist()
