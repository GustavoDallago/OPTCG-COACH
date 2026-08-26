"""
OPTCG Deck Analyzer Core Logic Module
Extracted business logic for deck validation, statistics calculation,
meta alignment calculation, banlist verification, and dynamic combat guides.
"""
from __future__ import annotations

import os
import sys
import re
import json
from typing import Optional, List, Dict, Any, Union, Tuple, TypedDict

# ==============================================================================
# Type Definitions & Schemas
# ==============================================================================

class CardDict(TypedDict, total=False):
    card_id: str
    card_set_id: str
    card_name: str
    card_color: str
    card_cost: Union[int, str]
    card_power: Union[int, str]
    counter_amount: Union[int, str]
    card_type: str
    card_text: str
    attribute: str
    sub_types: str
    rarity: str
    card_image: str
    image: str
    quantity: int
    inclusion_percentage: float
    in_user_deck: bool

class DeckStatsDict(TypedDict):
    total_cards: int
    counter_2000_count: int
    counter_1000_count: int
    blockers_count: int
    removal_count: int
    cost_distribution: Dict[int, int]

class DeckLegalityReport(TypedDict):
    is_legal: bool
    banned_cards_found: List[Dict[str, str]]
    banned_pairs_found: List[List[str]]
    overcopy_violations: List[Dict[str, Any]]
    size_violations: List[Dict[str, Any]]
    total_cards: int

class ReplacementCandidate(TypedDict):
    cut_card: CardDict
    cut_inclusion: float
    add_card: CardDict
    add_inclusion: float

class MatchupReport(TypedDict):
    winrate: float
    status: str
    recommendations: List[str]
    is_real_data: bool
    total_matches: int

class KeyCounterCard(TypedDict):
    card_id: str
    card_name: str
    image: str
    in_deck: bool
    user_qty: int
    winrate_boost: float
    status_badge: str
    tip: str

class HandComposition(TypedDict):
    searchers: str
    attackers: str
    defenses: str
    bricks: str

class CombatGuideReport(TypedDict):
    tactical_badge: str
    tactical_type: str
    tactical_message: str
    user_avg_cost: str
    opp_avg_cost: str
    turn_preference_title: str
    turn_preference_desc: str
    opp_curve_strategy: str
    turn_preference: str
    hand_composition: HandComposition
    mulligan_tips: str
    don_strategy: Dict[str, str]
    matchup_explanation: str
    key_counter_cards: List[KeyCounterCard]


# ==============================================================================
# Game Rules & Configuration Loader
# ==============================================================================

GAME_RULES_CACHE: Optional[Dict[str, Any]] = None

def load_game_rules(force_reload: bool = False) -> Dict[str, Any]:
    """
    Loads shared game rules and thresholds from optcg_data/game_rules.json.
    Falls back to sensible defaults if the file is missing or corrupted.
    """
    global GAME_RULES_CACHE
    if force_reload:
        GAME_RULES_CACHE = None

    if GAME_RULES_CACHE is not None:
        return GAME_RULES_CACHE

    default_rules: Dict[str, Any] = {
        "deck_constraints": {
            "deck_size": 50,
            "max_card_copies": 4,
            "max_cost": 10
        },
        "counter_tiers": [2000, 1000],
        "synergy_keywords": ["[blocker]", "[trigger]", "[rush]", "[double attack]", "[banish]"],
        "removal_keywords": ["k.o.", "trash", "place into bottom", "place into trash", "return to hand"]
    }

    rules_path = os.path.join("optcg_data", "game_rules.json")
    if os.path.exists(rules_path):
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                default_rules.update(loaded)
        except Exception:
            pass

    GAME_RULES_CACHE = default_rules
    return GAME_RULES_CACHE


# ==============================================================================
# Core Validation & Calculation Functions
# ==============================================================================

def validate_deck_color(leader_color: str, card_color: str) -> bool:
    """
    Checks if a card's color is compatible with the leader's allowed colors.
    Supports dual-color combinations separated by '/' or whitespace (e.g. 'Blue/Yellow').
    """
    if not leader_color or not card_color:
        return False

    if card_color == "DON!!":
        return True

    leader_colors = [c.strip().lower() for c in leader_color.replace("/", " ").split() if c.strip()]
    card_colors = [c.strip().lower() for c in card_color.replace("/", " ").split() if c.strip()]

    for c in card_colors:
        if c in leader_colors:
            return True

    return False


def calculate_deck_stats(deck_cards: List[Union[Dict[str, Any], CardDict]]) -> DeckStatsDict:
    """
    Calculates basic statistics for a deck list (card count, counter breakdown, blockers, removals, cost curve).
    """
    stats: DeckStatsDict = {
        "total_cards": 0,
        "counter_2000_count": 0,
        "counter_1000_count": 0,
        "blockers_count": 0,
        "removal_count": 0,
        "cost_distribution": {i: 0 for i in range(11)}
    }

    for card in deck_cards:
        qty = int(card.get("quantity", 1))
        stats["total_cards"] += qty

        # Cost curve distribution
        try:
            cost = int(card.get("card_cost", 0))
            if 0 <= cost <= 10:
                stats["cost_distribution"][cost] += qty
        except (ValueError, TypeError):
            pass

        # Counter breakdown
        try:
            counter = int(card.get("counter_amount", 0))
            if counter == 2000:
                stats["counter_2000_count"] += qty
            elif counter == 1000:
                stats["counter_1000_count"] += qty
        except (ValueError, TypeError):
            pass

        # Blockers detection
        text = (card.get("card_text") or "").lower()
        if "[blocker]" in text or "blocker" in text:
            stats["blockers_count"] += qty

        # Removals detection
        is_event = card.get("card_type", "").lower() == "event"
        has_ko_effect = any(kw in text for kw in ["k.o.", "trash", "place into", "rest up to"])
        if is_event and has_ko_effect:
            stats["removal_count"] += qty

    return stats


def calculate_meta_alignment(user_deck_ids: List[str], leader_meta_cards: List[Dict[str, Any]]) -> float:
    """
    Calculates percentage alignment between user deck cards and tournament meta core staples (>=50% inclusion).
    """
    if not leader_meta_cards:
        return 50.0

    meta_core_ids = {
        c["card_id"].upper().strip(): float(c.get("inclusion_percentage", 0.0))
        for c in leader_meta_cards
        if float(c.get("inclusion_percentage", 0.0)) >= 50.0 and c.get("card_id")
    }

    if not meta_core_ids:
        return 50.0

    matched_weight = 0.0
    total_weight = sum(meta_core_ids.values())

    user_id_set = {cid.upper().strip() for cid in user_deck_ids if cid}
    for card_id, weight in meta_core_ids.items():
        if card_id in user_id_set:
            matched_weight += weight

    return min(100.0, (matched_weight / total_weight) * 100.0)


# Known leader baseline winrates for heuristic estimations
KNOWN_LEADER_BASE_WINRATES: Dict[str, float] = {
    "OP05-060": 48.0,  # Monkey.D.Luffy (Purple)
    "OP09-001": 50.0,  # Shanks (Red)
    "OP09-081": 47.0,  # Marshall.D.Teach (Black)
    "OP03-040": 52.0,  # Nami (Blue)
    "OP05-098": 48.0,  # Enel (Yellow)
    "OP01-060": 53.0,  # Doflamingo (Blue)
    "OP06-022": 49.0,  # Yamato (Green/Yellow)
}


def get_real_matchup_winrate(opponent_leader_id: str, leader_matchups_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Retrieves real tournament matchup statistics between user's leader and opponent leader.
    """
    if not leader_matchups_data or not opponent_leader_id:
        return None
    matchup = leader_matchups_data.get(opponent_leader_id.upper())
    if matchup and matchup.get("total_matches", 0) > 0:
        return matchup
    return None


# ==============================================================================
# Banlist & Legality Verification Engine
# ==============================================================================

BANLIST_CACHE: Optional[Dict[str, Any]] = None

def load_banlist(mode: str = "EN", force_reload: bool = False) -> Dict[str, Any]:
    """
    Loads banlist rules with support for multi-format modes (EN, JP, NONE) and cached reads.
    """
    global BANLIST_CACHE
    if force_reload:
        BANLIST_CACHE = None

    if BANLIST_CACHE is None:
        banlist_path = os.path.join("optcg_data", "banlist.json")
        ban_sets_path = os.path.join("optcg_data", "ban_sets.json")
        ban_st_path = os.path.join("optcg_data", "ban_st.json")
        whitelist_path = os.path.join("optcg_data", "whitelist.json")

        data: Dict[str, Any] = {
            "banned_cards": [],
            "banned_sets": [],
            "banned_starter_decks": [],
            "whitelisted_cards": [],
            "restricted_cards": {},
            "banned_pairs": []
        }

        if os.path.exists(banlist_path):
            try:
                with open(banlist_path, "r", encoding="utf-8") as f:
                    data.update(json.load(f))
            except Exception:
                pass

        if os.path.exists(ban_sets_path):
            try:
                with open(ban_sets_path, "r", encoding="utf-8") as f:
                    data["banned_sets"] = json.load(f).get("banned_sets", [])
            except Exception:
                pass

        if os.path.exists(ban_st_path):
            try:
                with open(ban_st_path, "r", encoding="utf-8") as f:
                    data["banned_starter_decks"] = json.load(f).get("banned_starter_decks", [])
            except Exception:
                pass

        if os.path.exists(whitelist_path):
            try:
                with open(whitelist_path, "r", encoding="utf-8") as f:
                    data["whitelisted_cards"] = json.load(f).get("whitelisted_cards", [])
            except Exception:
                pass

        BANLIST_CACHE = data

    if mode == "NONE":
        return {
            "banned_cards": [],
            "banned_sets": [],
            "banned_starter_decks": [],
            "whitelisted_cards": [],
            "restricted_cards": {},
            "banned_pairs": []
        }

    modes = BANLIST_CACHE.get("modes", {})
    if mode in modes:
        res = dict(modes[mode])
        for key in ["banned_sets", "banned_starter_decks", "whitelisted_cards"]:
            if key not in res:
                res[key] = BANLIST_CACHE.get(key, [])
        return res

    return BANLIST_CACHE


def validate_deck_legality(
    user_deck_cards: List[Dict[str, Any]],
    leader_card_id: str = "",
    mode: str = "EN",
    banlist_data: Optional[Dict[str, Any]] = None,
    check_size: bool = True
) -> DeckLegalityReport:
    """
    Validates complete deck legality against banned cards, banned sets, banned starters,
    restricted card counts, banned pairs, and deck size constraints.
    """
    banlist = banlist_data if banlist_data is not None else load_banlist(mode)
    banned_cards = {c.strip().upper() for c in banlist.get("banned_cards", [])}
    banned_sets = {s.strip().upper() for s in banlist.get("banned_sets", [])}
    banned_starter_decks = {s.strip().upper() for s in banlist.get("banned_starter_decks", [])}
    whitelisted_cards = {c.strip().upper() for c in banlist.get("whitelisted_cards", [])}
    banned_pairs = banlist.get("banned_pairs", [])
    restricted_cards = {k.strip().upper(): int(v) for k, v in banlist.get("restricted_cards", {}).items()}

    deck_card_ids = set()
    if leader_card_id:
        deck_card_ids.add(leader_card_id.strip().upper())

    copy_counts: Dict[str, int] = {}
    total_cards = 0
    found_banned: List[Dict[str, str]] = []
    overcopy_violations: List[Dict[str, Any]] = []

    for item in user_deck_cards:
        cid = (item.get("card_set_id") or item.get("card_id") or "").strip().upper()
        if not cid:
            continue

        qty = int(item.get("quantity", 1))
        total_cards += qty
        copy_counts[cid] = copy_counts.get(cid, 0) + qty
        deck_card_ids.add(cid)
        c_prefix = cid.split("-")[0] if "-" in cid else cid

        is_card_banned = cid in banned_cards
        is_set_banned = (c_prefix in banned_sets or c_prefix in banned_starter_decks) and (cid not in whitelisted_cards)

        if is_card_banned or is_set_banned:
            cname = item.get("card_name") or cid
            if is_card_banned:
                reason = "Carta banida individualmente"
            elif c_prefix in banned_starter_decks:
                reason = f"Starter Deck ({c_prefix}) banido"
            else:
                reason = f"Coleção ({c_prefix}) banida"
            found_banned.append({"card_id": cid, "card_name": cname, "reason": reason})

    # Check copy limits (default 4x or restricted max)
    for cid, total_copies in copy_counts.items():
        max_allowed = restricted_cards.get(cid, 4)
        if total_copies > max_allowed:
            cname = next((i.get("card_name") or cid for i in user_deck_cards if (i.get("card_set_id") or i.get("card_id") or "").upper() == cid), cid)
            label = f"Restrita (máx. {max_allowed} cópias)" if cid in restricted_cards else f"Limite de 4 cópias excedido ({total_copies}x)"
            overcopy_violations.append({"card_id": cid, "card_name": cname, "copies": total_copies, "max_allowed": max_allowed, "reason": label})

    # Check banned pairs
    found_illegal_pairs: List[List[str]] = []
    for pair in banned_pairs:
        if len(pair) == 2:
            p1, p2 = pair[0].strip().upper(), pair[1].strip().upper()
            if p1 in deck_card_ids and p2 in deck_card_ids:
                found_illegal_pairs.append([p1, p2])

    # Check deck size constraints (exactly 50 cards)
    size_violations: List[Dict[str, Any]] = []
    if check_size and total_cards != 50 and total_cards > 0:
        size_violations.append({
            "total": total_cards,
            "reason": f"Deck tem {total_cards} carta(s). O deck principal deve ter exatamente 50 cartas."
        })

    is_legal = (
        len(found_banned) == 0 and
        len(found_illegal_pairs) == 0 and
        len(overcopy_violations) == 0 and
        len(size_violations) == 0
    )

    return {
        "is_legal": is_legal,
        "banned_cards_found": found_banned,
        "banned_pairs_found": found_illegal_pairs,
        "overcopy_violations": overcopy_violations,
        "size_violations": size_violations,
        "total_cards": total_cards
    }


def find_smart_replacements(
    user_deck_cards: List[Dict[str, Any]],
    leader_meta_cards: List[Dict[str, Any]],
    banlist_data: Optional[Dict[str, Any]] = None
) -> List[ReplacementCandidate]:
    """
    Recommends smart card replacements: replaces cards in user deck with lowest meta inclusion %
    with missing core/staple cards with highest meta inclusion %.
    Excludes any banned cards from recommendations.
    """
    if not leader_meta_cards or not user_deck_cards:
        return []

    if banlist_data is None:
        banlist_data = load_banlist("EN")

    banned_ids = {c.strip().upper() for c in banlist_data.get("banned_cards", [])}
    banned_sets = {s.strip().upper() for s in banlist_data.get("banned_sets", [])}
    banned_starters = {s.strip().upper() for s in banlist_data.get("banned_starter_decks", [])}
    whitelisted = {c.strip().upper() for c in banlist_data.get("whitelisted_cards", [])}

    def is_card_illegal(cid: str) -> bool:
        if not cid:
            return False
        cid_u = cid.strip().upper()
        c_prefix = cid_u.split("-")[0] if "-" in cid_u else cid_u
        if cid_u in banned_ids:
            return True
        if (c_prefix in banned_sets or c_prefix in banned_starters) and (cid_u not in whitelisted):
            return True
        return False

    meta_pct_map = {c.get("card_id", "").upper(): float(c.get("inclusion_percentage", 0.0)) for c in leader_meta_cards}
    user_deck_ids = {c.get("card_set_id", "").upper() for c in user_deck_cards}

    # Missing staples (>= 50% inclusion) - excluding banned cards
    missing_staples = [
        c for c in leader_meta_cards
        if c.get("card_id", "").upper() not in user_deck_ids
        and not is_card_illegal(c.get("card_id", ""))
        and float(c.get("inclusion_percentage", 0.0)) >= 50.0
    ]
    missing_staples.sort(key=lambda x: float(x.get("inclusion_percentage", 0.0)), reverse=True)

    # Scored user cards
    scored_user_cards = []
    for c in user_deck_cards:
        cid = c.get("card_set_id", "").upper()
        pct = meta_pct_map.get(cid, 0.0)
        scored_user_cards.append({"card": c, "inclusion_percentage": pct})
    scored_user_cards.sort(key=lambda x: x["inclusion_percentage"])

    replacements: List[ReplacementCandidate] = []
    for i in range(min(len(missing_staples), len(scored_user_cards))):
        if scored_user_cards[i]["inclusion_percentage"] < float(missing_staples[i].get("inclusion_percentage", 0.0)):
            replacements.append({
                "cut_card": scored_user_cards[i]["card"],
                "cut_inclusion": scored_user_cards[i]["inclusion_percentage"],
                "add_card": missing_staples[i],
                "add_inclusion": float(missing_staples[i].get("inclusion_percentage", 0.0))
            })

    return replacements


def evaluate_matchup(
    opponent_leader: Dict[str, Any],
    user_stats: DeckStatsDict,
    meta_alignment: float,
    leader_matchups_data: Optional[Dict[str, Any]] = None
) -> MatchupReport:
    """
    Evaluates estimated win rate against a meta opponent leader.
    Uses real Limitless tournament match records if available, otherwise falls back to heuristics.
    """
    opp_name = opponent_leader.get("name", "").lower()
    opp_id = opponent_leader.get("leader_card_id", "").strip().upper()

    # 1. Check real tournament matchup records first
    real_match = get_real_matchup_winrate(opp_id, leader_matchups_data)
    if real_match:
        real_winrate = float(real_match.get("winrate", 50.0))
        tot = int(real_match.get("total_matches", 0))
        w = int(real_match.get("wins", 0))
        l = int(real_match.get("losses", 0))

        status = "Equilibrado"
        if real_winrate >= 55.0:
            status = "Vantajoso"
        elif real_winrate < 45.0:
            status = "Desfavorável"

        recomends = [
            f"Taxa real de {real_winrate}% em {tot} partidas de torneio ({w} vitórias, {l} derrotas)."
        ]
        return {
            "winrate": real_winrate,
            "status": status,
            "recommendations": recomends,
            "is_real_data": True,
            "total_matches": tot
        }

    # 2. Heuristic baseline lookup
    base_winrate = KNOWN_LEADER_BASE_WINRATES.get(opp_id, 50.0)

    # 3. Meta alignment impact
    meta_modifier = (meta_alignment - 70.0) / 6.0
    estimated_winrate = base_winrate + meta_modifier

    # 4. Archetype classification
    is_aggro = "shanks" in opp_name or "zoro" in opp_name or "betty" in opp_name
    is_big_character = "luffy" in opp_name or "teach" in opp_name or "enel" in opp_name

    recomends = []
    if is_aggro:
        defense = user_stats["counter_2000_count"] + user_stats["blockers_count"]
        if defense >= 12:
            estimated_winrate += 5.0
            recomends.append("Sua alta quantidade de defesas (+2000 counters/blockers) é ideal contra a velocidade deste líder.")
        elif defense < 6:
            estimated_winrate -= 10.0
            recomends.append("Cuidado: Seu deck tem poucas defesas contra a agressividade rápida deste líder. Adicione blockers ou counters +2000.")
        else:
            recomends.append("Defesa equilibrada para lidar com a pressão inicial.")

    if is_big_character:
        removals = user_stats["removal_count"]
        if removals >= 6:
            estimated_winrate += 4.0
            recomends.append("Suas cartas de remoção ajudam a controlar os personagens grandes deste oponente.")
        elif removals < 3:
            estimated_winrate -= 7.0
            recomends.append("Atenção: Este oponente joga personagens grandes e você tem poucas remoções eficientes.")
        else:
            recomends.append("Remoções moderadas para lidar com ameaças pontuais.")

    estimated_winrate = max(30.0, min(70.0, estimated_winrate))

    if estimated_winrate >= 55.0:
        status = "Vantajoso"
    elif estimated_winrate >= 45.0:
        status = "Equilibrado"
    else:
        status = "Desfavorável"

    return {
        "winrate": round(estimated_winrate, 1),
        "status": status,
        "recommendations": recomends,
        "is_real_data": False,
        "total_matches": 0
    }


def generate_dynamic_combat_guide(
    user_deck_cards: List[Dict[str, Any]],
    opponent_leader: Dict[str, Any],
    leader_meta_cards: Optional[List[Dict[str, Any]]] = None
) -> CombatGuideReport:
    """
    Generates a 100% dynamic combat guide tailored to the user's specific deck cards
    and the opponent's archetype (Aggro, Control, Tempo).
    """
    opp_name = opponent_leader.get("name", "").lower()
    opp_display_name = opponent_leader.get("name", "Oponente")
    is_aggro = any(k in opp_name for k in ["shanks", "zoro", "betty", "law", "ace", "kid"])
    is_big = any(k in opp_name for k in ["teach", "kaido", "enel", "linlin", "luffy", "sabo", "sakazuki", "kuzan"])
    opp_type = 'aggro' if is_aggro else ('control' if is_big else 'tempo')

    # Categorize user cards and compute user average cost
    searchers = []
    blockers = []
    bosses = []
    counters_2k = []
    removals = []
    early_drops = []
    mid_drops = []
    odd_count = 0
    even_count = 0
    user_total_cost = 0
    user_total_cards = 0

    user_deck_set_map: Dict[str, int] = {}
    for c in user_deck_cards:
        cid = (c.get("card_set_id") or c.get("card_id") or "").strip().upper()
        qty = int(c.get("quantity", 1))
        if cid:
            user_deck_set_map[cid] = user_deck_set_map.get(cid, 0) + qty

        txt = (c.get("card_text") or "").lower()
        cost = int(c.get("card_cost") or 0)
        counter = int(c.get("counter_amount") or 0)
        ctype = (c.get("card_type") or "").lower()

        user_total_cost += cost * qty
        user_total_cards += qty

        if cost % 2 == 1:
            odd_count += qty
        elif cost > 0:
            even_count += qty

        if cost <= 2 and any(k in txt for k in ["look", "search", "reveal", "add"]):
            searchers.append(c)
        if "[blocker]" in txt or "blocker" in txt:
            blockers.append(c)
        if cost >= 7 and ctype == "character":
            bosses.append(c)
        if counter == 2000:
            counters_2k.append(c)
        if any(k in txt for k in ["k.o.", "trash", "bottom of", "rest up to"]):
            removals.append(c)
        if 1 <= cost <= 3 and ctype == "character":
            early_drops.append(c)
        if 4 <= cost <= 6 and ctype == "character":
            mid_drops.append(c)

    user_avg_cost = f"{user_total_cost / user_total_cards:.1f}" if user_total_cards > 0 else "3.5"

    searchers.sort(key=lambda x: int(x.get("card_cost") or 0))
    blockers.sort(key=lambda x: int(x.get("card_cost") or 0))
    early_drops.sort(key=lambda x: int(x.get("card_power") or 0), reverse=True)
    mid_drops.sort(key=lambda x: int(x.get("card_power") or 0), reverse=True)
    bosses.sort(key=lambda x: int(x.get("card_power") or 0), reverse=True)

    # Opponent cost and curve analysis
    opp_meta = leader_meta_cards or []
    opp_total_cost = 0
    opp_total_cards = 0
    opp_odd_count = 0
    opp_even_count = 0
    opp_early_drops = []
    opp_mid_drops = []

    for mc in opp_meta:
        c_cost = int(mc.get("card_cost") or 0)
        c_qty = int(mc.get("avg_copies") or 3)
        opp_total_cost += c_cost * c_qty
        opp_total_cards += c_qty
        if c_cost % 2 == 1:
            opp_odd_count += c_qty
        elif c_cost > 0:
            opp_even_count += c_qty
        if 1 <= c_cost <= 3:
            opp_early_drops.append(mc)
        elif 4 <= c_cost <= 6:
            opp_mid_drops.append(mc)

    if opp_total_cards > 0:
        opp_avg_cost = f"{opp_total_cost / opp_total_cards:.1f}"
    else:
        opp_avg_cost = "2.8" if is_aggro else ("4.8" if is_big else "3.6")
        opp_odd_count = 28 if is_aggro else 20
        opp_even_count = 22 if is_aggro else 30

    # Posture recommendation
    if is_aggro:
        badge = "🚨 Oponente Agressivo (Rush / Swarm)"
        msg = "Este oponente tentará zerar seus pontos de vida em ritmo acelerado desde os primeiros turnos. Postura recomendada: CONTROLE DE MESA E DEFESA. Não dispute corrida de vida; use seus personagens para limpar os atacantes virados (rested) dele e mantenha sua mão cheia de Counters (+2000)."
    elif is_big:
        badge = "🛡️ Oponente de Controle (Late Game / Chefes)"
        msg = "Este oponente quer arrastar o jogo para os turnos 8 a 10 e dominar o campo com personagens gigantes. Postura recomendada: PRESSÃO E AGRESSIVIDADE INICIAL. Ataque a vida do oponente nos turnos 2 a 4 para forçá-lo a queimar cartas da mão se defendendo."
    else:
        badge = "🔄 Oponente de Ritmo (Manipulação & Recursos)"
        msg = "Este líder manipula a mesa virando ou retornando peças. Postura recomendada: JOGO CADENCIADO E VALOR. Faça trocas vantajosas e evite deixar personagens virados sem proteção."

    # Turn preference & steal-curve analysis
    top_searcher = searchers[0] if searchers else None
    top_blocker = blockers[0] if blockers else None
    top_2k = counters_2k[0] if counters_2k else None
    top_early = early_drops[0] if early_drops else None
    top_mid = mid_drops[0] if mid_drops else None
    top_boss = bosses[0] if bosses else None
    top_removal = removals[0] if removals else None

    user_prefers_first = odd_count >= even_count
    opp_prefers_first = opp_odd_count >= opp_even_count

    if opp_prefers_first:
        opp_curve_scenarios = {
            "ideal_label": f"Melhor Curva para {opp_display_name}",
            "ideal_badge": "1º Turno (Ímpar)",
            "ideal_desc": f"Curva ideal de {opp_display_name}: PRIMEIRO (Média: {opp_avg_cost} Don, {opp_odd_count} cartas ímpares){' para descer ' + top_early.get('card_name') + ' no Turno 1/2' if top_early else ''} e acelerar o desenvolvimento de campo sem desperdício de Don.",
            "steal_label": "Tática de Bloqueio (Roubar Curva)",
            "steal_badge": "Escolha ir 1º para bloquear",
            "steal_desc": f"Se você escolher ir PRIMEIRO, você rouba a curva do oponente, quebrando a sequência rápida de {opp_display_name} e forçando-o a jogar no 2º turno com Don desfavorável no início."
        }
    else:
        opp_curve_scenarios = {
            "ideal_label": f"Melhor Curva para {opp_display_name}",
            "ideal_badge": "2º Turno (Par)",
            "ideal_desc": f"Curva ideal de {opp_display_name}: SEGUNDO (Média: {opp_avg_cost} Don, {opp_even_count} cartas pares){' para descer ' + top_mid.get('card_name') + ' no tempo perfeito' if top_mid else ''} e aproveitar a compra extra inicial.",
            "steal_label": "Tática de Bloqueio (Roubar Curva)",
            "steal_badge": "Escolha ir 2º para bloquear",
            "steal_desc": f"Se você escolher ir SEGUNDO, você atrasa a descida do drop par do oponente{' (' + top_mid.get('card_name') + ')' if top_mid else ''} em 1 rodada inteira, mas precisará adaptar seus custos para aproveitar o Don livre."
        }

    turn_scenarios = {}
    if user_prefers_first and opp_prefers_first:
        pref_title = "Disputa de Turno! Escolha PRIMEIRO (Ímpar - 1, 3, 5, 7, 9 Don!!)"
        pref_desc = f"Seu deck (Média: {user_avg_cost} Don, {odd_count} cartas ímpares) e o de {opp_display_name} (Média: {opp_avg_cost} Don) disputam a mesma curva inicial. Escolha PRIMEIRO para garantir seu tempo de jogo e ROUBAR A CURVA DO ADVERSÁRIO, forçando {opp_display_name} a jogar no 2º turno com Don ocioso."
        opp_strategy = f"Curva ideal de {opp_display_name}: PRIMEIRO (Média {opp_avg_cost} Don). Ao pegar o 1º turno, você impede a aceleração de custos ímpares do oponente."
        turn_scenarios = {
            "option1_label": "Opção 1: Ímpar",
            "option1_badge": "1º Turno (Ímpar - Drop Cheio)",
            "option1_desc": f"Seu deck é mais ágil em custos ímpares (Média: {user_avg_cost} Don, {odd_count} cartas ímpares), enquanto {opp_display_name} (Média: {opp_avg_cost} Don) disputa a mesma curva. Ir PRIMEIRO ativa seu plano de drop cheio e ROUBA A CURVA DO ADVERSÁRIO, forçando {opp_display_name} a jogar no 2º turno com Don ocioso.",
            "option2_label": "Opção 2: Par",
            "option2_badge": "2º Turno (Par - Don Aberto / Reativo)",
            "option2_desc": "Se você quiser jogar de forma reativa com 1 Don em pé para Eventos de Counter ou bater 6k no Líder, escolher o 2º Turno (2, 4, 6, 8 Don) encaixa suas peças de 1, 3 e 5 Don com 1 Don livre todo turno!"
        }
    elif not user_prefers_first and not opp_prefers_first:
        pref_title = "Disputa de Turno! Escolha SEGUNDO (Par - 2, 4, 6, 8, 10 Don!!)"
        pref_desc = f"Ambos os decks possuem custos pares predominantes (Seu Deck: Média {user_avg_cost} Don | Oponente: Média {opp_avg_cost} Don). Escolha SEGUNDO para sincronizar seus custos pares, receber +1 carta de compra inicial E ROUBAR A CURVA DO ADVERSÁRIO, impedindo a jogada de 4 Don no turno 2 de {opp_display_name}."
        opp_strategy = f"Curva ideal de {opp_display_name}: SEGUNDO (Média {opp_avg_cost} Don). Escolher o 2º turno força o oponente a jogar fora da curva par favorita dele."
        turn_scenarios = {
            "option1_label": "Opção 1: Par",
            "option1_badge": "2º Turno (Par - Drop Cheio)",
            "option1_desc": f"Ambos os decks possuem custos pares predominantes (Seu Deck: Média {user_avg_cost} Don | Oponente: Média {opp_avg_cost} Don). Escolha ir SEGUNDO para sincronizar seus custos pares, receber +1 carta de compra inicial E ROUBAR A CURVA DO ADVERSÁRIO, impedindo o drop de 4 Don no Turno 2 de {opp_display_name}.",
            "option2_label": "Opção 2: Ímpar",
            "option2_badge": "1º Turno (Ímpar - Don Aberto / Reativo)",
            "option2_desc": "Se você quiser jogar no 1º Turno (1, 3, 5, 7 Don), você desce suas cartas de custo par (2, 4 e 6 Don) e sobra exatamente 1 Don ativo para Eventos Defensivos ou bater com Don anexado no Líder!"
        }
    elif user_prefers_first and not opp_prefers_first:
        pref_title = "Escolha PRIMEIRO (Ímpar - 1, 3, 5, 7, 9 Don!!)"
        pref_desc = f"Seu deck é mais ágil em custos ímpares (Média: {user_avg_cost} Don), enquanto {opp_display_name} prefere a curva par (Média: {opp_avg_cost} Don). Ir PRIMEIRO ativa seu plano de drop cheio sem desperdício de Don."
        opp_strategy = f"Curva ideal de {opp_display_name}: SEGUNDO (Média {opp_avg_cost} Don). 💡 Tática de Bloqueio (Roubar Curva): Se optar por ir 2º, você atrasa os drops pares do oponente, mas precisará adaptar seus custos."
        turn_scenarios = {
            "option1_label": "Opção 1: Ímpar",
            "option1_badge": "1º Turno (Ímpar - Drop Cheio)",
            "option1_desc": f"Seu deck é mais ágil em custos ímpares (Média: {user_avg_cost} Don), enquanto {opp_display_name} prefere a curva par (Média: {opp_avg_cost} Don). Ir PRIMEIRO ativa seu plano de drop cheio sem desperdício de Don.",
            "option2_label": "Opção 2: Par",
            "option2_badge": "2º Turno (Par - Don Aberto / Reativo)",
            "option2_desc": "Se você quiser jogar de forma reativa com 1 Don em pé para Eventos ou bater 6k no Líder, escolher o 2º Turno (2, 4, 6, 8 Don) encaixa suas peças de 1, 3 e 5 Don com 1 Don livre todo turno!"
        }
    else:
        pref_title = "Escolha SEGUNDO (Par - 2, 4, 6, 8, 10 Don!!)"
        pref_desc = f"Seu deck performa melhor na curva par (Média: {user_avg_cost} Don, {even_count} cartas pares). Ir SEGUNDO dá +1 carta na mão e permite responder imediatamente à pressão de {opp_display_name} (Média: {opp_avg_cost} Don)."
        opp_strategy = f"Curva ideal de {opp_display_name}: PRIMEIRO (Média {opp_avg_cost} Don). 💡 Tática de Bloqueio: Ir 1º desestrutura o início rápido dele, mas exige cartas de custo 1 e 3 na mão."
        turn_scenarios = {
            "option1_label": "Opção 1: Par",
            "option1_badge": "2º Turno (Par - Drop Cheio)",
            "option1_desc": f"Seu deck performa melhor na curva par (Média: {user_avg_cost} Don, {even_count} cartas pares). Ir SEGUNDO dá +1 compra e encaixa seus drops de 2, 4 e 6 Don, além de permitir responder de imediato à agressão de {opp_display_name} (Média: {opp_avg_cost} Don).",
            "option2_label": "Opção 2: Ímpar",
            "option2_badge": "1º Turno (Ímpar - Don Aberto / Reativo)",
            "option2_desc": "Se você optar pelo 1º Turno (1, 3, 5, 7 Don), você quebra o início rápido de {opp_display_name} e desce seus drops pares de 2, 4 e 6 Don com 1 Don ativo de folga para Eventos de Counter ou ataque com o Líder!"
        }

    # Hand Composition
    hand_searcher_str = f"1x {top_searcher.get('card_name')} (Garante fluxo)" if top_searcher else "0x (Sem buscador 1-2)"
    
    if top_early and top_mid:
        if is_aggro:
            hand_attacker_str = f"1-2x {top_early.get('card_name')} (Contestar atacantes virados)"
        elif is_big:
            hand_attacker_str = f"1-2x {top_mid.get('card_name')} (Pressão direta na Vida)"
        else:
            hand_attacker_str = f"1x {top_early.get('card_name')} + 1x {top_mid.get('card_name')}"
    elif top_early:
        hand_attacker_str = f"1-2x {top_early.get('card_name')} (Ataque proativo)"
    elif top_mid:
        hand_attacker_str = f"1-2x {top_mid.get('card_name')} (Presença de campo)"
    else:
        hand_attacker_str = "0x (Sem atacantes de custo 1-6 no deck)"

    if top_blocker and top_2k:
        if is_aggro:
            hand_defense_str = f"1-2x {top_blocker.get('card_name')} + 1-2x {top_2k.get('card_name')}"
        elif is_big:
            hand_defense_str = f"1x {top_2k.get('card_name')} + {'1x ' + top_removal.get('card_name') if top_removal else '1x ' + top_blocker.get('card_name')}"
        else:
            hand_defense_str = f"1x {top_blocker.get('card_name')} + 1x {top_2k.get('card_name')}"
    elif top_blocker:
        if is_aggro:
            hand_defense_str = f"2x {top_blocker.get('card_name')} (Proteção de mesa)"
        else:
            hand_defense_str = f"1-2x {top_blocker.get('card_name')} (Controle de dano)"
    elif top_2k:
        if is_aggro:
            hand_defense_str = f"2x {top_2k.get('card_name')} (Sem blocker: foco em +2000)"
        else:
            hand_defense_str = f"1-2x {top_2k.get('card_name')} (Counter de emergência)"
    else:
        hand_defense_str = "0x (Sem Blockers e sem Counters +2000 no deck!)"

    hand_brick_str = f"Máximo 0-1x {top_boss.get('card_name')} (2+ = Mão travada/Brick)" if top_boss else "0x (Deck ágil sem cartas de custo 7+)"

    hand_comp: HandComposition = {
        "searchers": hand_searcher_str,
        "attackers": hand_attacker_str,
        "defenses": hand_defense_str,
        "bricks": hand_brick_str
    }

    # Mulligan advice
    defense_items = []
    if top_2k:
        defense_items.append(f"+2000 Counter ({top_2k.get('card_name')})")
    if top_blocker:
        defense_items.append(f"Blocker ({top_blocker.get('card_name')})")
    defense_mention = " / ".join(defense_items) if defense_items else "suas defesas disponíveis"

    proactive_items = []
    if top_searcher:
        proactive_items.append(f"Buscador ({top_searcher.get('card_name')})")
    if top_early:
        proactive_items.append(f"Drop inicial ({top_early.get('card_name')})")
    if top_mid:
        proactive_items.append(f"Atacante de curva ({top_mid.get('card_name')})")
    proactive_mention = " + ".join(proactive_items) if proactive_items else "peças de ataque proativo"

    if is_aggro:
        mulligan = f"🚨 Prioridade contra Agressividade ({opp_display_name}): Mantenha {('Buscador (' + top_searcher.get('card_name') + ')') if top_searcher else (('Drop inicial (' + top_early.get('card_name') + ')') if top_early else 'drops rápidos')} e defesas ({defense_mention}). MULLIGAN IMEDIATO se a mão vier {('com 2+ cópias de ' + top_boss.get('card_name') + ' (Bricks)') if top_boss else 'pesada'} ou sem nenhuma resposta para os turnos 1 a 3."
    elif is_big:
        mulligan = f"🛡️ Prioridade contra Controle ({opp_display_name}): Garanta {proactive_mention} para pressionar a vida do oponente antes do turno 10. MULLIGAN IMEDIATO se a mão for puramente defensiva/passiva ou contiver cartas mortas sem presença de mesa inicial."
    else:
        mulligan = f"🔄 Prioridade para Ritmo ({opp_display_name}): Busque curva balanceada {('com ' + top_early.get('card_name')) if top_early else 'de custo baixo'} e {top_mid.get('card_name') if top_mid else 'custo médio'}. Dê Mulligan se a mão não tiver nenhuma jogada para os dois primeiros turnos."

    # Don curve strategy
    if is_aggro:
        if top_early and top_blocker:
            early = f"Early Game (1-4 Don): Baixar {top_early.get('card_name')} ({top_early.get('card_set_id')}) e posicionar seu blocker {top_blocker.get('card_name')} ({top_blocker.get('card_set_id')}) para disputar a mesa. Ataque apenas personagens virados de {opp_display_name} e evite dar dano na vida que aumente a mão adversária."
        elif top_early:
            early = f"Early Game (1-4 Don): Baixar {top_early.get('card_name')} ({top_early.get('card_set_id')}) para contestar os primeiros atacantes de {opp_display_name}. Ataque apenas personagens virados dele e evite dar dano na vida que aumente a mão adversária."
        elif top_blocker:
            early = f"Early Game (1-4 Don): Posicionar seu blocker {top_blocker.get('card_name')} ({top_blocker.get('card_set_id')}) para conter os primeiros ataques rápidos de {opp_display_name}."
        else:
            early = f"Early Game (1-4 Don): Utilizar Don no Líder para trocas vantajosas contra os primeiros atacantes virados de {opp_display_name} e preservar seus pontos de vida."

        if top_mid and top_removal:
            mid = f"Mid Game (5-8 Don): Estabelecer {top_mid.get('card_name')} ({top_mid.get('card_set_id')}) e usar {top_removal.get('card_name')} ({top_removal.get('card_set_id')}) para limpar atacantes virados, neutralizando a ofensiva inimiga."
        elif top_mid:
            mid = f"Mid Game (5-8 Don): Desenvolver {top_mid.get('card_name')} ({top_mid.get('card_set_id')}) com poder 5000+ para controlar a mesa e punir personagens virados de {opp_display_name}."
        elif top_removal:
            mid = f"Mid Game (5-8 Don): Usar {top_removal.get('card_name')} ({top_removal.get('card_set_id')}) para remover peças-chave adversárias e desacelerar a pressão."
        else:
            mid = f"Mid Game (5-8 Don): Usar seus personagens intermediários e o Don no Líder para manter a mesa limpa e conter a agressividade."

        if top_boss:
            late = f"Late Game (9-10 Don): Descer seu Boss {top_boss.get('card_name')} ({top_boss.get('card_set_id')}) com 8000+ de poder e usar Don no Líder para aplicar ataques pesados decisivos na vida, aproveitando que a mão de {opp_display_name} estará esgotada."
        else:
            late = f"Late Game (9-10 Don): Distribuir Don nos atacantes estabelecidos e no Líder para ataques com 7000-8000+ de poder para finalizar a partida enquanto o oponente está sem recursos."
    elif is_big:
        if top_searcher and top_early:
            early = f"Early Game (1-4 Don): Baixar {top_searcher.get('card_name')} ({top_searcher.get('card_set_id')}) para filtrar a mão e desenvolver {top_early.get('card_name')} ({top_early.get('card_set_id')}) para iniciar pressão direta na vida de {opp_display_name} antes que ele tenha Don para os chefes de late game."
        elif top_searcher:
            early = f"Early Game (1-4 Don): Baixar {top_searcher.get('card_name')} ({top_searcher.get('card_set_id')}) para filtrar sua mão e buscar seus atacantes e remoções antes do late game de {opp_display_name}."
        elif top_early:
            early = f"Early Game (1-4 Don): Baixar {top_early.get('card_name')} ({top_early.get('card_set_id')}) para iniciar pressão proativa na vida de {opp_display_name} nos primeiros turnos."
        else:
            early = f"Early Game (1-4 Don): Acoplar Don no Líder para atacar a vida de {opp_display_name} e forçar o oponente a queimar cartas da mão se defendendo."

        if top_mid and top_removal:
            mid = f"Mid Game (5-8 Don): Colocar {top_mid.get('card_name')} ({top_mid.get('card_set_id')}) em campo para forçar o oponente a gastar cartas da mão se defendendo, guardando {top_removal.get('card_name')} ({top_removal.get('card_set_id')}) para responder ao primeiro Boss que {opp_display_name} descer."
        elif top_mid:
            mid = f"Mid Game (5-8 Don): Desenvolver {top_mid.get('card_name')} ({top_mid.get('card_set_id')}) para manter pressão contínua na vida de {opp_display_name} antes dos turnos 8 a 10."
        elif top_removal:
            mid = f"Mid Game (5-8 Don): Guardar {top_removal.get('card_name')} ({top_removal.get('card_set_id')}) para responder de imediato aos personagens gigantes que {opp_display_name} colocar em campo."
        else:
            mid = f"Mid Game (5-8 Don): Pressionar com ataques médios sucessivos para forçar o oponente a entrar no late game com a vida zerada ou poucos recursos na mão."

        if top_boss:
            late = f"Late Game (9-10 Don): Descer seu Boss {top_boss.get('card_name')} ({top_boss.get('card_set_id')}) de impacto para confrontar os monstros de {opp_display_name} e focar todo o Don restante em golpes letais antes que ele recupere o controle total."
        else:
            late = f"Late Game (9-10 Don): Alocar todo o Don restante nos atacantes e no Líder para buscar a vitória letal antes que os chefes pesados de {opp_display_name} dominem a partida."
    else:
        if top_searcher and top_early:
            early = f"Early Game (1-4 Don): Desenvolver {top_searcher.get('card_name')} ({top_searcher.get('card_set_id')}) para consistência e {top_early.get('card_name')} ({top_early.get('card_set_id')}) para presença de mesa inicial."
        elif top_searcher:
            early = f"Early Game (1-4 Don): Desenvolver {top_searcher.get('card_name')} ({top_searcher.get('card_set_id')}) para estruturar a mão e garantir fluxo de cartas para os turnos médios."
        elif top_early:
            early = f"Early Game (1-4 Don): Baixar {top_early.get('card_name')} ({top_early.get('card_set_id')}) para estabelecer presença de campo nos primeiros turnos."
        else:
            early = f"Early Game (1-4 Don): Distribuir Don no Líder para trocas eficientes e segurar Don ativo para eventos defensivos."

        if top_mid and top_removal:
            mid = f"Mid Game (5-8 Don): Realizar trocas vantajosas na mesa com {top_mid.get('card_name')} ({top_mid.get('card_set_id')}) e utilizar {top_removal.get('card_name')} ({top_removal.get('card_set_id')}) para quebrar o ritmo de {opp_display_name}."
        elif top_mid:
            mid = f"Mid Game (5-8 Don): Desenvolver {top_mid.get('card_name')} ({top_mid.get('card_set_id')}) para ditar o ritmo de mesa e pressionar peças adversárias."
        else:
            mid = f"Mid Game (5-8 Don): Manter seus atacantes intermediários ativos para trocas de recursos equilibradas e preservar Don para respostas."

        if top_boss:
            late = f"Late Game (9-10 Don): Descer seu Boss {top_boss.get('card_name')} ({top_boss.get('card_set_id')}) e alocar Don estrategicamente para finalizar a partida com sobrecarga de poder."
        else:
            late = f"Late Game (9-10 Don): Alocar Don estrategicamente nos atacantes estabelecidos e no Líder para aplicar ataques múltiplos difíceis de defender."

    def get_clean_name(n: str) -> str:
        return re.sub(r'\s*\([^)]*\)', '', n).strip().lower()

    def score_card_against_opponent(c_obj: Dict[str, Any], is_in_user_deck: bool) -> Tuple[float, str]:
        txt = (c_obj.get("card_text") or "").lower()
        cost = int(c_obj.get("card_cost") or 0)
        power = int(c_obj.get("card_power") or 0)
        counter = int(c_obj.get("counter_amount") or 0)
        inc_pct = float(c_obj.get("inclusion_percentage") or 50.0)

        score = 0.0
        reason = ""

        # Specific opponent mechanic heuristics
        if "sabo" in opp_name:
            if "bottom of" in txt or "place at bottom" in txt:
                score += 100.0
                reason = "Ignora a proteção contra K.O. do Sabo enviando o personagem para o fundo do deck."
            elif "trash" in txt:
                score += 85.0
                reason = "Envia diretamente ao Trash ultrapassando os efeitos de proteção contra destruição."
            elif power >= 8000:
                score += 70.0
                reason = "Ataque pesado (8000+) para ultrapassar a vida reforçada do Sabo."
            elif "[blocker]" in txt or "blocker" in txt:
                score += 60.0
                reason = "Blocker para conter os ataques impulsionados com Don do Sabo."

        elif "kaido" in opp_name or "teach" in opp_name or "luffy" in opp_name:
            if "rush" in txt or "[rush]" in txt:
                score += 95.0
                reason = "Ataque imediato com Rush para punir os turnos de aceleração de Don do oponente."
            elif any(k in txt for k in ["k.o.", "trash", "bottom"]) and cost >= 4:
                score += 85.0
                reason = "Remoção direta para responder aos Bosses pesados antes que dominem o campo."
            elif counter == 2000:
                score += 65.0
                reason = "Counter +2000 fundamental para defender de ataques massivos de 9000+ de poder."

        elif "enel" in opp_name or "linlin" in opp_name:
            if "trash 1 card" in txt or "trash" in txt:
                score += 95.0
                reason = "Descarta a Vida do oponente sem disparar os Triggers defensivos do Enel."
            elif power >= 8000:
                score += 80.0
                reason = "Golpes pesados (8000+) para forçar o Enel a esvaziar a mão se defendendo."
            elif "rest up to" in txt or "cannot be k.o." in txt:
                score += 70.0
                reason = "Imobiliza os defensores inimigos garantindo dano direto na Vida."

        elif "shanks" in opp_name or "zoro" in opp_name or "betty" in opp_name or "ace" in opp_name:
            if "[blocker]" in txt or "blocker" in txt:
                score += 95.0
                reason = "Blocker para defender múltiplos ataques rápidos sem perder cartas da mão."
            elif counter == 2000:
                score += 90.0
                reason = "Counter +2000 de máxima eficiência defensiva contra o ritmo Rush."
            elif cost <= 3 and any(k in txt for k in ["k.o.", "rest"]):
                score += 75.0
                reason = "Limpa os atacantes de custo baixo adversários nos primeiros turnos."

        elif "nami" in opp_name:
            if "rush" in txt or cost <= 2:
                score += 95.0
                reason = "Pressão rápida de dano para vencer a partida antes que a Nami zere o próprio deck."
            elif power >= 6000:
                score += 75.0
                reason = "Atacante de curva média para pressionar a Vida da Nami turno a turno."

        if score == 0.0:
            if is_aggro:
                if counter == 2000 or "[blocker]" in txt:
                    score += 50.0
                    reason = f"Recurso defensivo importante para conter a velocidade de {opp_display_name}."
                elif cost <= 2:
                    score += 40.0
                    reason = f"Drop inicial para disputar a mesa nos primeiros turnos contra {opp_display_name}."
            elif is_big:
                if "k.o." in txt or "trash" in txt:
                    score += 55.0
                    reason = f"Opção de remoção para conter os personagens grandes de {opp_display_name}."
                elif power >= 7000:
                    score += 45.0
                    reason = f"Ameaça pesada para pressionar a mesa no late game contra {opp_display_name}."
            else:
                if any(k in txt for k in ["search", "look", "reveal", "add"]):
                    score += 50.0
                    reason = f"Buscador para filtrar a mão e garantir consistência contra {opp_display_name}."
                elif 3 <= cost <= 5:
                    score += 40.0
                    reason = f"Atacante de curva intermediária para trocas eficientes contra {opp_display_name}."

        score += inc_pct * 0.25
        if not is_in_user_deck:
            score += 25.0

        return score, reason

    all_candidates: List[Dict[str, Any]] = []
    seen_cand_ids = set()

    for item in user_deck_cards:
        cid = (item.get("card_set_id") or item.get("card_id") or "").strip().upper()
        if cid and cid not in seen_cand_ids:
            seen_cand_ids.add(cid)
            c_copy = dict(item)
            c_copy["in_user_deck"] = True
            all_candidates.append(c_copy)

    if leader_meta_cards:
        for mcard in leader_meta_cards:
            cid = (mcard.get("card_id") or mcard.get("card_set_id") or "").strip().upper()
            if cid and cid not in seen_cand_ids:
                seen_cand_ids.add(cid)
                c_copy = dict(mcard)
                c_copy["card_set_id"] = cid
                c_copy["in_user_deck"] = cid in user_deck_set_map
                all_candidates.append(c_copy)

    # Filter illegal candidates
    banlist_obj = load_banlist("EN")
    banned_cards_set = {c.strip().upper() for c in banlist_obj.get("banned_cards", [])}
    banned_sets_set = {s.strip().upper() for s in banlist_obj.get("banned_sets", [])}
    banned_starters_set = {s.strip().upper() for s in banlist_obj.get("banned_starter_decks", [])}
    whitelisted_set = {c.strip().upper() for c in banlist_obj.get("whitelisted_cards", [])}

    def is_candidate_illegal(cid: str) -> bool:
        if not cid:
            return False
        cid_u = cid.strip().upper()
        c_prefix = cid_u.split("-")[0] if "-" in cid_u else cid_u
        if cid_u in banned_cards_set:
            return True
        if (c_prefix in banned_sets_set or c_prefix in banned_starters_set) and (cid_u not in whitelisted_set):
            return True
        return False

    scored_pool = []
    seen_names = set()

    for c_obj in all_candidates:
        cid = (c_obj.get("card_set_id") or c_obj.get("card_id") or "").strip().upper()
        if is_candidate_illegal(cid):
            continue

        cname = c_obj.get("card_name") or cid
        clean_n = get_clean_name(cname)

        if clean_n in seen_names:
            continue

        in_deck = c_obj.get("in_user_deck", False)
        sc, reason_text = score_card_against_opponent(c_obj, in_deck)

        scored_pool.append({
            "card_obj": c_obj,
            "cid": cid,
            "cname": cname,
            "clean_n": clean_n,
            "in_deck": in_deck,
            "score": sc,
            "reason": reason_text,
            "inc_pct": float(c_obj.get("inclusion_percentage") or 50.0)
        })

    scored_pool.sort(key=lambda x: x["score"], reverse=True)

    in_deck_candidates = [item for item in scored_pool if item["in_deck"]]
    missing_candidates = [item for item in scored_pool if not item["in_deck"]]

    selected_items = []
    for item in in_deck_candidates[:2]:
        selected_items.append(item)
    for item in missing_candidates[:2]:
        selected_items.append(item)
    if len(selected_items) < 4:
        for item in scored_pool:
            if item not in selected_items:
                selected_items.append(item)
                if len(selected_items) >= 4:
                    break

    key_counter_cards: List[KeyCounterCard] = []
    for item in selected_items[:4]:
        cid = item["cid"]
        cname = item["cname"]
        in_deck = item["in_deck"]
        reason_text = item["reason"]
        inc_pct = item["inc_pct"]
        c_obj = item["card_obj"]
        cimg = c_obj.get("card_image") or c_obj.get("image") or ""

        seen_names.add(item["clean_n"])

        is_outlier = 15.0 <= inc_pct <= 65.0
        base_boost = (inc_pct / 12.0) if is_outlier else (inc_pct / 18.0)
        boost = round(min(8.5, max(3.5, base_boost)), 1)

        if in_deck:
            qty = user_deck_set_map.get(cid, 1)
            key_counter_cards.append({
                "card_id": cid,
                "card_name": cname,
                "image": cimg,
                "in_deck": True,
                "user_qty": qty,
                "winrate_boost": 0.0,
                "status_badge": "Peça Tática no Deck",
                "tip": f"Você possui {qty}x no deck. {reason_text}"
            })
        else:
            badge_title = f"💡 Outlier Recomendado (+{boost}%)" if is_outlier else f"💡 Recomendada (+{boost}%)"
            key_counter_cards.append({
                "card_id": cid,
                "card_name": cname,
                "image": cimg,
                "in_deck": False,
                "user_qty": 0,
                "winrate_boost": boost,
                "status_badge": badge_title,
                "tip": f"{reason_text} Adicionar ao deck aumenta a chance em +{boost}% contra {opp_display_name}."
            })

    return {
        "tactical_badge": badge,
        "tactical_type": opp_type,
        "tactical_message": msg,
        "user_avg_cost": user_avg_cost,
        "opp_avg_cost": opp_avg_cost,
        "turn_preference_title": pref_title,
        "turn_preference_desc": pref_desc,
        "turn_scenarios": turn_scenarios,
        "opp_curve_strategy": opp_strategy,
        "opp_curve_scenarios": opp_curve_scenarios,
        "turn_preference": f"{pref_title} - {pref_desc}",
        "hand_composition": hand_comp,
        "mulligan_tips": mulligan,
        "don_strategy": {
            "early": early,
            "mid": mid,
            "late": late
        },
        "matchup_explanation": msg,
        "key_counter_cards": key_counter_cards
    }
