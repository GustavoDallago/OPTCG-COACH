import os
import re
import sys
import json
import time
import argparse
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, List, Optional

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

DATA_DIR = "optcg_data"
BASE_URL = "https://play.limitlesstcg.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def parse_args():
    parser = argparse.ArgumentParser(description="Limitless TCG Metagame Scraper (Past 7 Days)")
    parser.add_argument("--set", type=str, default="OP17", help="Set code to scrape (e.g., OP17, OP16, OP09)")
    parser.add_argument("--min-players", type=int, default=8, help="Minimum player count in tournament (default: 8)")
    parser.add_argument("--days", type=int, default=7, help="Days of history to analyze (default: 7)")
    return parser.parse_args()

def atomic_save_json(data: Any, filepath: str, indent: Optional[int] = None) -> bool:
    """Saves JSON data atomically using a temporary file and atomic replace in compact format."""
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

def fetch_url(url: str, retries: int = 3, delay: float = 0.5) -> Optional[str]:
    """Faz requisições HTTP seguras com headers e tratamento de erros, incluindo rate limit (429)."""
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                if response.status == 200:
                    time.sleep(delay)
                    return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = min(30 * attempt, 120)
                print(f"  [Rate Limit 429] Bloqueio temporário em {url}. Aguardando {wait}s antes de tentar novamente (Tentativa {attempt}/{retries})...")
                time.sleep(wait)
            else:
                print(f"  [Aviso] HTTP {e.code} ao acessar {url} (Tentativa {attempt}/{retries}): {e}")
                if attempt < retries:
                    time.sleep(attempt * 1.5)
        except Exception as e:
            print(f"  [Aviso] Falha ao acessar {url} (Tentativa {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(attempt * 1.5)
    return None

_card_details_cache = {}
import html

def fetch_card_details(card_id: str, card_db: dict = None) -> dict:
    """Fetches real card attributes (cost, power, type, attribute) from local DB first,
    falling back to the Limitless card page only if not found locally."""
    global _card_details_cache
    if card_id in _card_details_cache:
        return _card_details_cache[card_id]

    # --- Priority 1: Check local card database (zero network cost) ---
    if card_db:
        local = card_db.get(card_id.upper(), {})
        if local:
            details = {}
            if local.get('card_cost') is not None:
                details['cost'] = str(local['card_cost'])
            raw_power = local.get('card_power')
            if raw_power is not None:
                details['power'] = str(raw_power).replace(',', '')
            if local.get('card_type'):
                details['card_type'] = local['card_type']
            if local.get('attribute'):
                details['attribute'] = local['attribute']
            raw_counter = local.get('counter_amount')
            if raw_counter is not None and str(raw_counter) not in ('0', '', 'None'):
                try:
                    val = int(str(raw_counter).replace(',', '').replace('+', ''))
                    if val > 0:
                        details['counter'] = f"+{val}"
                except (ValueError, TypeError):
                    pass
            if details:
                _card_details_cache[card_id] = details
                return details

    # --- Priority 2: Fallback to Limitless web page (for unknown/promo cards) ---
    url = f"{BASE_URL}/cards/{card_id}"
    html_content = fetch_url(url, retries=2, delay=0.3)
    if not html_content:
        _card_details_cache[card_id] = {}
        return {}
    
    details = {}
    
    # Extract cost
    cost_m = re.search(r'Cost[^<]*</[^>]+>\s*<[^>]+>\s*(\d+)', html_content)
    if cost_m:
        details['cost'] = cost_m.group(1)
    
    # Extract power
    power_m = re.search(r'Power[^<]*</[^>]+>\s*<[^>]+>\s*([0-9,]+)', html_content)
    if power_m:
        details['power'] = power_m.group(1).replace(',', '')
    
    # Extract card type
    type_m = re.search(r'(?:Type|Category)[^<]*</[^>]+>\s*<[^>]+>\s*(Leader|Character|Event|Stage)', html_content, re.IGNORECASE)
    if type_m:
        details['card_type'] = type_m.group(1)
    
    # Extract attribute
    attr_m = re.search(r'Attribute[^<]*</[^>]+>\s*<[^>]+>\s*(Slash|Strike|Ranged|Special|Wisdom)', html_content, re.IGNORECASE)
    if attr_m:
        details['attribute'] = attr_m.group(1)
    
    # Extract counter
    counter_m = re.search(r'Counter[^<]*</[^>]+>\s*<[^>]+>\s*([+][0-9,]+)', html_content)
    if counter_m:
        details['counter'] = counter_m.group(1)
    
    _card_details_cache[card_id] = details
    return details

def is_base_version(card: Dict[str, Any]) -> bool:
    name = (card.get("card_name") or "").lower()
    img = (card.get("card_image") or "").lower()
    
    # Strictly reject Japanese versions if English is available
    if "japanese" in name or "_jp" in img:
        return False
        
    alt_keywords = [
        "(parallel", "(alternate", "(special", "(extra grand", 
        "(store", "(premium", "(winner", "(judge", "(manga", "(championship", 
        "(treasure", "(event", "(prb", "_p1", "_p2", "_p3", "_p4", "_parallel", "_img.jpg"
    ]
    for kw in alt_keywords:
        if kw in name or kw in img:
            return False
    return True

def clean_card_name(name: str) -> str:
    cleaned = re.sub(r'\s*-\s*[A-Z0-9]+-\d+', '', name)
    cleaned = re.sub(r'\s*\([A-Z0-9]+-\d+\)', '', cleaned)
    cleaned = re.sub(r'\s*\((?:Parallel|Alternate Art|Japanese Version|Special|Extra Grand Battle|Store|Premium|Winner Pack|Judge|Manga|Championship|Treasure|Event).*?\)', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or name

def load_card_database() -> Dict[str, Dict[str, Any]]:
    """Carrega o banco de cartas local priorizando SEMPRE as versões base das cartas."""
    cards_map = {}
    for filename in ["promo_cards.json", "don_cards.json", "starter_cards.json", "set_cards.json"]:
        filepath = os.path.join(DATA_DIR, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    cards = json.load(f)
                    for c in cards:
                        cid = (c.get("card_set_id") or c.get("card_id") or "").upper()
                        if not cid:
                            continue
                        
                        is_base = is_base_version(c)
                        if cid not in cards_map:
                            cards_map[cid] = c
                        else:
                            existing_is_base = is_base_version(cards_map[cid])
                            if is_base and not existing_is_base:
                                cards_map[cid] = c
            except Exception:
                pass
    return cards_map

def get_top_cut(num_players: int) -> tuple:
    """Calcula o top cut dinâmico para coleta de decklists e sample builds.
    
    Retorna (top_cut_decklists, top_cut_sample_builds):
    - top_cut_decklists: máximo de colocação para raspar decklists completas
    - top_cut_sample_builds: máximo de colocação para exibir como exemplo de build
    
    Exemplos:
      8 jogadores  -> top 8 decklists, top 4 builds
      16 jogadores -> top 16 decklists, top 8 builds
      32 jogadores -> top 32 decklists, top 8 builds
      64 jogadores -> top 48 decklists, top 8 builds
      128+         -> top 64 decklists, top 8 builds
    """
    if num_players < 16:
        return num_players, min(4, num_players)
    elif num_players < 32:
        return 16, 8
    elif num_players < 64:
        return 32, 8
    elif num_players < 128:
        return 48, 8
    else:
        return 64, 8


def find_tournaments(set_code: str, min_players: int = 8) -> List[Dict[str, Any]]:
    """Busca a lista de torneios da seção 'Past 7 days' que correspondam ao Set e ao mínimo de jogadores."""
    url = f"{BASE_URL}/tournaments/?game=OP"
    print(f"--> Buscando torneios recentes em: {url}")
    html = fetch_url(url)
    if not html:
        print("❌ Erro: Não foi possível carregar a lista de torneios do Limitless.")
        return []

    tournaments = []
    row_pattern = re.compile(r'<tr\s+([^>]*?)>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
    
    table_match = re.search(r'<table[^>]*class="[^"]*completed-tournaments[^"]*"[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE)
    table_content = table_match.group(1) if table_match else html

    set_upper = set_code.upper()
    
    for row_match in row_pattern.finditer(table_content):
        attrs = row_match.group(1)
        content = row_match.group(2)
        
        data_name = re.search(r'data-name="([^"]+)"', attrs)
        data_players = re.search(r'data-players="(\d+)"', attrs)
        data_date = re.search(r'data-date="([^"]+)"', attrs)
        data_winner = re.search(r'data-winner="([^"]+)"', attrs)
        
        link_match = re.search(r'href="\/tournament\/([a-f0-9]+)\/standings"', content)
        if not link_match:
            continue
            
        t_id = link_match.group(1)
        name = data_name.group(1) if data_name else ""
        players = int(data_players.group(1)) if data_players else 0
        date_str = data_date.group(1) if data_date else ""
        winner = data_winner.group(1) if data_winner else ""

        name_clean = name.upper()
        is_matching_set = (set_upper in name_clean) or (set_upper.replace("OP", "OP-") in name_clean)
        
        if is_matching_set and players >= min_players:
            tournaments.append({
                "id": t_id,
                "name": name,
                "players": players,
                "date": date_str,
                "winner": winner
            })
            print(f"  [+] Torneio Elegível Encontrado: {name} | Jogadores: {players} | ID: {t_id}")

    return tournaments

def parse_standings(t_id: str) -> List[Dict[str, Any]]:
    """Raspa os Standings de um torneio específico."""
    url = f"{BASE_URL}/tournament/{t_id}/standings"
    html = fetch_url(url)
    if not html:
        return []

    players_list = []
    row_pattern = re.compile(r'<tr\s+([^>]*?)>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
    
    for row in row_pattern.finditer(html):
        attrs = row.group(1)
        content = row.group(2)
        
        data_placing = re.search(r'data-placing="(\d+)"', attrs)
        data_name = re.search(r'data-name="([^"]+)"', attrs)
        data_country = re.search(r'data-country="([^"]+)"', attrs)
        
        player_id_match = re.search(r'href="\/tournament\/[a-f0-9]+\/player\/([a-z0-9_\-]+)"', content, re.IGNORECASE)
        leader_id_match = re.search(r'href="\/tournament\/[a-f0-9]+\/metagame\/([A-Z0-9\-]+)"', content)
        decklist_link_match = re.search(r'href="(\/tournament\/[a-f0-9]+\/player\/[a-z0-9_\-]+\/decklist)"', content, re.IGNORECASE)
        
        if not player_id_match or not leader_id_match:
            continue
            
        p_id = player_id_match.group(1).lower()
        placing = int(data_placing.group(1)) if data_placing else len(players_list) + 1
        name = data_name.group(1) if data_name else p_id
        country = data_country.group(1) if data_country else ""
        leader_id = leader_id_match.group(1).upper()
        
        deck_name_match = re.search(rf'href="\/tournament\/[a-f0-9]+\/metagame\/{re.escape(leader_id)}">([^<]+)<', content)
        deck_name = deck_name_match.group(1).strip() if deck_name_match else leader_id
        
        players_list.append({
            "player_id": p_id,
            "player_name": name,
            "placing": placing,
            "country": country,
            "leader_id": leader_id,
            "deck_name": deck_name,
            "has_decklist": bool(decklist_link_match),
            "decklist_url": f"{BASE_URL}{decklist_link_match.group(1)}" if decklist_link_match else None
        })

    return players_list

def parse_decklist(decklist_url: str) -> List[Dict[str, Any]]:
    """Raspa a lista exata de 50 cartas do jogador."""
    html = fetch_url(decklist_url, delay=0.05)
    if not html:
        return []

    cards_found = []
    
    js_match = re.search(r'const\s+decklist\s*=\s*`([^`]+)`', html)
    raw_lines = []
    if js_match:
        raw_lines = js_match.group(1).strip().splitlines()
    else:
        input_match = re.search(r'<input[^>]*name="input"[^>]*value="([^"]+)"', html)
        if input_match:
            raw_lines = input_match.group(1).strip().splitlines()

    for line in raw_lines:
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
            
        match = re.search(r'^\s*(\d+)\s+(.*?)\s*\(([A-Za-z0-9\-]+)\)\s*$', line)
        if match:
            qty = int(match.group(1))
            c_name = match.group(2).strip()
            c_id = match.group(3).strip().upper()
            cards_found.append({
                "card_id": c_id,
                "card_name": c_name,
                "quantity": qty
            })
        else:
            simple_match = re.search(r'^\s*(\d+)\s*x?\s*([A-Za-z0-9\-]+)', line)
            if simple_match:
                qty = int(simple_match.group(1))
                c_id = simple_match.group(2).strip().upper()
                cards_found.append({
                    "card_id": c_id,
                    "card_name": c_id,
                    "quantity": qty
                })

    return cards_found

def parse_pairings(t_id: str) -> List[Dict[str, Any]]:
    """Raspa todas as rodadas de partidas (Pairings) do torneio para descobrir quem enfrentou quem."""
    initial_url = f"{BASE_URL}/tournament/{t_id}/pairings"
    html = fetch_url(initial_url)
    if not html:
        return []

    rounds = [1]
    round_matches = re.findall(r'href="\/tournament\/[a-f0-9]+\/pairings\?round=(\d+)"', html)
    if round_matches:
        rounds = sorted(list(set(int(r) for r in round_matches)))

    all_matches = []
    
    for r in rounds:
        round_url = f"{BASE_URL}/tournament/{t_id}/pairings?round={r}"
        r_html = html if (r == rounds[-1] and "data-round" in html) else fetch_url(round_url, delay=0.2)
        if not r_html:
            continue
            
        row_pattern = re.compile(r'<tr\s+([^>]*?)>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
        for row in row_pattern.finditer(r_html):
            attrs = row.group(1)
            content = row.group(2)
            
            data_winner = re.search(r'data-winner="([^"]+)"', attrs)
            winner_id = data_winner.group(1).lower() if data_winner else ""
            
            players = re.findall(r'class="player[^"]*"\s+data-id="([a-z0-9_\-]+)"', content, re.IGNORECASE)
            if len(players) >= 2:
                p1_id = players[0].lower()
                p2_id = players[1].lower()
                
                all_matches.append({
                    "round": r,
                    "p1": p1_id,
                    "p2": p2_id,
                    "winner": winner_id
                })

    return all_matches

def fetch_fallback_meta_cards(leader_id: str, card_db: dict, current_set_code: str) -> list:
    """
    Se o deck nunca ganhou no meta (0 vitórias) e não possui cartas salvas,
    busca as cartas que o líder mais usa nos arquivos JSON de metas anteriores ou no banco de cartas.
    """
    import glob
    meta_files = sorted(glob.glob(os.path.join(DATA_DIR, "meta_*.json")), reverse=True)
    for filepath in meta_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
            for leader in prev_data.get("leaders", []):
                l_id = leader.get("leader_card_id") or ""
                if l_id.upper() == leader_id.upper():
                    cards = leader.get("cards", [])
                    if cards and len(cards) > 0:
                        return cards
        except Exception:
            pass

    leader_info = card_db.get(leader_id, {})
    leader_color = leader_info.get("card_color") or ""
    if not leader_color:
        return []

    leader_colors = [c.strip().lower() for c in re.split(r'[\s/]+', leader_color) if c.strip()]
    fallback_cards = []

    for cid, cinfo in card_db.items():
        if cid == leader_id or cinfo.get("card_type") == "Leader":
            continue
        ccolor_raw = (cinfo.get("card_color") or "").lower()
        ccolors = [c.strip() for c in re.split(r'[\s/]+', ccolor_raw) if c.strip()]
        if any(lc in ccolors for lc in leader_colors):
            c_set = cid.split("-")[0] if "-" in cid else current_set_code
            c_img = cinfo.get("card_image") or f"https://limitlesstcg.nyc3.digitaloceanspaces.com/one-piece/{c_set}/{cid}_EN.webp"
            fallback_cards.append({
                "card_name": clean_card_name(cinfo.get("card_name") or cid),
                "card_id": cid,
                "inclusion_percentage": 50.0,
                "copies_recommendation": "usually 4x",
                "avg_copies": 4.0,
                "category": "suggested",
                "decks_count_text": "Carta Sugerida por Cor",
                "image": c_img
            })
            if len(fallback_cards) >= 30:
                break

    return fallback_cards

def scrape_limitless(set_code: str = "OP17", min_players: int = 16, days: int = 7):
    print("=" * 60)
    print(f"🏴‍☠️ INICIANDO SCRAPER LIMITLESS TCG: META {set_code.upper()} (ÚLTIMOS {days} DIAS)")
    print(f"   Filtro Mínimo de Jogadores: {min_players}")
    print("=" * 60)

    card_db = load_card_database()
    tournaments = find_tournaments(set_code, min_players)
    
    if not tournaments:
        print(f"Nenhum torneio recente encontrado para o Set {set_code} com >= {min_players} jogadores.")
        return False

    print(f"\n--> Processando {len(tournaments)} torneios encontrados...")
    
    all_player_records = {}
    all_leader_decks = {}
    leader_info_map = {}
    matchup_matrix = {}
    leader_sample_builds = {}

    total_decks_tracked = 0

    for t_idx, t in enumerate(tournaments):
        t_id = t["id"]
        t_name = t["name"]
        t_players = t["players"]
        top_cut_decks, top_cut_builds = get_top_cut(t_players)
        print(f"\n[{t_idx+1}/{len(tournaments)}] Coletando dados do Torneio: {t_name}...", flush=True)
        print(f"    Jogadores: {t_players} | Top cut decklists: {top_cut_decks} | Top cut builds: {top_cut_builds}", flush=True)
        
        # 1. Standings
        standings = parse_standings(t_id)
        print(f"    Standings: {len(standings)} jogadores listados.", flush=True)
        
        tournament_players = {}
        for p in standings:
            p_id = p["player_id"]
            leader_id = p["leader_id"]
            deck_name = p["deck_name"]
            
            tournament_players[p_id] = p
            all_player_records[(t_id, p_id)] = p
            total_decks_tracked += 1
            
            if leader_id not in leader_info_map:
                c_info = card_db.get(leader_id, {})
                l_set = leader_id.split("-")[0] if "-" in leader_id else set_code
                img = c_info.get("card_image") or f"https://limitlesstcg.nyc3.digitaloceanspaces.com/one-piece/{l_set}/{leader_id}_EN.webp"
                color = c_info.get("card_color") or "Multi"
                name_display = f"{deck_name} ({color})" if color != "Multi" and "(" not in deck_name else deck_name
                
                leader_info_map[leader_id] = {
                    "name": name_display,
                    "leader_card_id": leader_id,
                    "deck_count": 0,
                    "image": img,
                    "archetype_code": f"{leader_id}||{color}"
                }
            leader_info_map[leader_id]["deck_count"] += 1
            
            # 2. Decklists completas (Top cut dinâmico por tamanho do torneio)
            if p["has_decklist"] and p["decklist_url"] and p["placing"] <= top_cut_decks:
                cards = parse_decklist(p["decklist_url"])
                if cards:
                    if leader_id not in all_leader_decks:
                        all_leader_decks[leader_id] = []
                    
                    deck_dict = {c["card_id"]: c["quantity"] for c in cards}
                    all_leader_decks[leader_id].append({
                        "player_name": p["player_name"],
                        "placing": p["placing"],
                        "cards": cards,
                        "deck_dict": deck_dict
                    })
                    
                    if p["placing"] <= top_cut_builds:
                        if leader_id not in leader_sample_builds:
                            leader_sample_builds[leader_id] = []
                        
                        txt_lines = [f"1x{leader_id}"]
                        for c in cards:
                            if c["card_id"] != leader_id:
                                txt_lines.append(f"{c['quantity']}x{c['card_id']}")
                        
                        leader_sample_builds[leader_id].append({
                            "player_name": p["player_name"],
                            "country": p["country"],
                            "placing": p["placing"],
                            "tournament_name": t_name,
                            "deck_txt": "\n".join(txt_lines)
                        })

        # 3. Pairings
        pairings = parse_pairings(t_id)
        print(f"    Pairings: {len(pairings)} partidas registradas.", flush=True)
        
        for m in pairings:
            p1_id = m["p1"]
            p2_id = m["p2"]
            winner = m["winner"]
            
            p1_info = tournament_players.get(p1_id)
            p2_info = tournament_players.get(p2_id)
            
            if not p1_info or not p2_info:
                continue
                
            l1 = p1_info["leader_id"]
            l2 = p2_info["leader_id"]
            
            if l1 not in matchup_matrix: matchup_matrix[l1] = {}
            if l2 not in matchup_matrix: matchup_matrix[l2] = {}
            if l2 not in matchup_matrix[l1]: matchup_matrix[l1][l2] = {"wins": 0, "losses": 0, "ties": 0, "total": 0}
            if l1 not in matchup_matrix[l2]: matchup_matrix[l2][l1] = {"wins": 0, "losses": 0, "ties": 0, "total": 0}
            
            matchup_matrix[l1][l2]["total"] += 1
            matchup_matrix[l2][l1]["total"] += 1
            
            if winner == p1_id:
                matchup_matrix[l1][l2]["wins"] += 1
                matchup_matrix[l2][l1]["losses"] += 1
            elif winner == p2_id:
                matchup_matrix[l1][l2]["losses"] += 1
                matchup_matrix[l2][l1]["wins"] += 1
            else:
                matchup_matrix[l1][l2]["ties"] += 1
                matchup_matrix[l2][l1]["ties"] += 1

    # --- Consolidação Estatística ---
    print("\n--> Consolidando porcentagens de inclusão de cartas e matriz de confrontos...")
    
    leaders_output = []
    
    for leader_id, l_data in leader_info_map.items():
        deck_count = l_data["deck_count"]
        share_pct = round((deck_count / max(1, total_decks_tracked)) * 100.0, 1)
        
        submitted_lists = all_leader_decks.get(leader_id, [])
        num_lists = len(submitted_lists)
        
        card_stats = {}
        
        for s in submitted_lists:
            for c in s["cards"]:
                cid = c["card_id"]
                if cid == leader_id:
                    continue
                qty = c["quantity"]
                cname = c["card_name"]
                
                if cid not in card_stats:
                    c_info = card_db.get(cid, {})
                    c_set = cid.split("-")[0] if "-" in cid else set_code
                    c_img = c_info.get("card_image") or f"https://limitlesstcg.nyc3.digitaloceanspaces.com/one-piece/{c_set}/{cid}_EN.webp"
                    c_raw_name = c_info.get("card_name") or cname
                    card_stats[cid] = {
                        "card_name": clean_card_name(c_raw_name),
                        "card_id": cid,
                        "deck_appearances": 0,
                        "total_copies": 0,
                        "image": c_img
                    }
                card_stats[cid]["deck_appearances"] += 1
                card_stats[cid]["total_copies"] += qty
                
        cards_list = []
        for cid, c_data in card_stats.items():
            inclusion_pct = round((c_data["deck_appearances"] / max(1, num_lists)) * 100.0, 1) if num_lists > 0 else 0.0
            avg_copies = round(c_data["total_copies"] / max(1, c_data["deck_appearances"]), 1)
            recommended_copies = f"usually {int(round(avg_copies))}x" if avg_copies > 0 else "1x"
            
            if inclusion_pct >= 70.0:
                category = "core"
            elif inclusion_pct >= 30.0:
                category = "suggested"
            else:
                category = "tech"
                
            card_entry = {
                "card_name": c_data["card_name"],
                "card_id": cid,
                "inclusion_percentage": inclusion_pct,
                "copies_recommendation": recommended_copies,
                "avg_copies": avg_copies,
                "category": category,
                "decks_count_text": f"{c_data['deck_appearances']}/{num_lists} decks",
                "image": c_data["image"]
            }
            
            # Fetch real card attributes from Limitless
            card_details = fetch_card_details(cid, card_db)
            if card_details.get('cost'):
                card_entry['cost'] = card_details['cost']
            if card_details.get('power'):
                card_entry['power'] = card_details['power']
            if card_details.get('card_type'):
                card_entry['card_type'] = card_details['card_type']
            if card_details.get('attribute'):
                card_entry['attribute'] = card_details['attribute']
            if card_details.get('counter'):
                card_entry['counter'] = card_details['counter']
                
            cards_list.append(card_entry)
            
        cards_list.sort(key=lambda x: x["inclusion_percentage"], reverse=True)
        
        leader_matchups = {}
        h2h = matchup_matrix.get(leader_id, {})
        total_wins = 0
        total_games = 0
        
        for opp_id, m_stat in h2h.items():
            opp_name = leader_info_map.get(opp_id, {}).get("name", opp_id)
            w = m_stat["wins"]
            l = m_stat["losses"]
            t = m_stat["ties"]
            tot = m_stat["total"]
            
            total_wins += w
            total_games += tot
            
            winrate = round((w / max(1, tot)) * 100.0, 1) if tot > 0 else 50.0
            
            leader_matchups[opp_id] = {
                "opponent_id": opp_id,
                "opponent_name": opp_name,
                "wins": w,
                "losses": l,
                "ties": t,
                "total_matches": tot,
                "winrate": winrate
            }
            
        overall_winrate = round((total_wins / max(1, total_games)) * 100.0, 1) if total_games > 0 else 0.0
        
        # REGRA: Se o deck nunca ganhou no meta (overall_winrate == 0 ou total_wins == 0) e não possui cartas coletadas,
        # puxe as cartas que ele mais usa (de metas anteriores ou fallback do banco de cartas).
        # MAS SÓ EM CASO DE NUNCA TER GANHO. CASO CONTRÁRIO MANTENHA IGUAL.
        if (overall_winrate == 0.0 or total_wins == 0) and len(cards_list) == 0:
            cards_list = fetch_fallback_meta_cards(leader_id, card_db, set_code)
        
        sample_builds = leader_sample_builds.get(leader_id, [])
        sample_builds.sort(key=lambda x: x["placing"])
        
        leaders_output.append({
            "name": l_data["name"],
            "leader_card_id": leader_id,
            "deck_count": deck_count,
            "share_percentage": share_pct,
            "overall_winrate": overall_winrate,
            "total_games_recorded": total_games,
            "archetype_code": l_data["archetype_code"],
            "image": l_data["image"],
            "cards": cards_list,
            "matchups": leader_matchups,
            "sample_builds": sample_builds[:4]
        })

    leaders_output.sort(key=lambda x: x["deck_count"], reverse=True)

    # --- Guard: Só salva se tiver dados válidos ---
    if len(leaders_output) == 0:
        print("\n" + "=" * 60)
        print(f"⚠️  AVISO: Nenhum líder encontrado para o Set {set_code.upper()}.")
        print("   O arquivo JSON existente NÃO foi sobrescrito para evitar perda de dados.")
        print("=" * 60)
        return False
    
    final_data = {
        "set_code": set_code.upper(),
        "source": "Limitless TCG (Past 7 Days - Western Meta)",
        "tournaments_tracked": len(tournaments),
        "decks_tracked": total_decks_tracked,
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "leaders": leaders_output
    }
    
    out_file = os.path.join(DATA_DIR, f"meta_{set_code.upper()}.json")
    if atomic_save_json(final_data, out_file):
        print("\n" + "=" * 60)
        print(f"✅ SUCCESS! Metagame for set {set_code.upper()} consolidated.")
        print(f"   Generated File: {out_file}")
        print(f"   Tournaments: {len(tournaments)} | Decks: {total_decks_tracked} | Leaders: {len(leaders_output)}")
        print("=" * 60)
        return True
    return False

if __name__ == "__main__":
    args = parse_args()
    scrape_limitless(set_code=args.set, min_players=args.min_players, days=args.days)
