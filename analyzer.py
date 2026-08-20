"""
OPTCG Deck Analyzer Core Logic Module
Extracted business logic for deck validation, statistics calculation, and matchup estimation.
"""

def validate_deck_color(leader_color: str, card_color: str) -> bool:
    """
    Checks if a card's color is compatible with the leader's allowed colors.
    Dual-color leaders contain '/' (e.g. 'Blue/Yellow').
    """
    if not leader_color or not card_color:
        return False
    
    if card_color == "DON!!":
        return True
        
    leader_colors = [c.strip().lower() for c in leader_color.split('/')]
    card_colors = [c.strip().lower() for c in card_color.split('/')]
    
    for c in card_colors:
        if c in leader_colors:
            return True
            
    return False

def calculate_deck_stats(deck_cards: list) -> dict:
    """
    Calculates basic statistics for the user's deck.
    deck_cards: list of dicts containing card information and quantities.
    """
    stats = {
        "total_cards": 0,
        "counter_2000_count": 0,
        "counter_1000_count": 0,
        "blockers_count": 0,
        "removal_count": 0,
        "cost_distribution": {i: 0 for i in range(11)}
    }
    
    for card in deck_cards:
        qty = card.get("quantity", 1)
        stats["total_cards"] += qty
        
        # Cost distribution
        try:
            cost = int(card.get("card_cost", 0))
            if 0 <= cost <= 10:
                stats["cost_distribution"][cost] += qty
        except (ValueError, TypeError):
            pass
            
        # Counters
        try:
            counter = int(card.get("counter_amount", 0))
            if counter == 2000:
                stats["counter_2000_count"] += qty
            elif counter == 1000:
                stats["counter_1000_count"] += qty
        except (ValueError, TypeError):
            pass
            
        # Blockers
        text = (card.get("card_text") or "").lower()
        if "[blocker]" in text:
            stats["blockers_count"] += qty
            
        # Removals
        is_event = card.get("card_type", "").lower() == "event"
        has_ko_effect = "k.o." in text or "trash" in text or "place" in text
        if is_event and has_ko_effect:
            stats["removal_count"] += qty
            
    return stats

def calculate_meta_alignment(user_deck_ids: list, leader_meta_cards: list) -> float:
    """
    Calculates percentage alignment between user deck and leader's meta deck.
    """
    if not leader_meta_cards:
        return 50.0
        
    meta_core_ids = {c["card_id"]: c["inclusion_percentage"] for c in leader_meta_cards if c.get("inclusion_percentage", 0) >= 50.0}
    if not meta_core_ids:
        return 50.0
        
    matched_weight = 0.0
    total_weight = sum(meta_core_ids.values())
    
    for card_id in user_deck_ids:
        if card_id in meta_core_ids:
            matched_weight += meta_core_ids[card_id]
            
    return min(100.0, (matched_weight / total_weight) * 100.0)

# Specific base win rates keyed by exact card_set_id for precision (Item 6)
KNOWN_LEADER_BASE_WINRATES = {
    "OP05-060": 48.0,  # Monkey.D.Luffy (Purple)
    "OP09-001": 50.0,  # Shanks (Red)
    "OP09-081": 47.0,  # Marshall.D.Teach (Black)
    "OP03-040": 52.0,  # Nami (Blue)
    "OP05-098": 48.0,  # Enel (Yellow)
    "OP01-060": 53.0,  # Doflamingo (Blue)
    "OP06-022": 49.0,  # Yamato (Green/Yellow)
}

def evaluate_matchup(opponent_leader: dict, user_stats: dict, meta_alignment: float) -> dict:
    """
    Evaluates estimated win rate against a meta opponent leader.
    """
    opp_name = opponent_leader.get("name", "").lower()
    opp_id = opponent_leader.get("leader_card_id", "").strip().upper()
    
    # 1. Base Matchup Lookup by card_set_id (Item 6)
    base_winrate = KNOWN_LEADER_BASE_WINRATES.get(opp_id, 50.0)
        
    # 2. Meta Alignment Impact
    meta_modifier = (meta_alignment - 70.0) / 6.0
    estimated_winrate = base_winrate + meta_modifier
    
    # 3. Strategy Type Classification
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
        "recommendations": recomends
    }
