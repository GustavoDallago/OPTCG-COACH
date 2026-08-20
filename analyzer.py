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

def get_real_matchup_winrate(opponent_leader_id: str, leader_matchups_data: dict) -> Optional[dict]:
    """
    Retrieves real tournament matchup statistics between user's leader and opponent leader.
    """
    if not leader_matchups_data or not opponent_leader_id:
        return None
    matchup = leader_matchups_data.get(opponent_leader_id.upper())
    if matchup and matchup.get("total_matches", 0) > 0:
        return matchup
    return None

def find_smart_replacements(user_deck_cards: list, leader_meta_cards: list) -> list:
    """
    Recommends smart card replacements: replaces cards in user deck with lowest meta inclusion %
    with missing core/staple cards with highest meta inclusion %.
    """
    if not leader_meta_cards or not user_deck_cards:
        return []
    
    meta_pct_map = {c.get("card_id", "").upper(): float(c.get("inclusion_percentage", 0.0)) for c in leader_meta_cards}
    user_deck_ids = {c.get("card_set_id", "").upper() for c in user_deck_cards}
    
    # Missing high-inclusion staples (>= 50%)
    missing_staples = [c for c in leader_meta_cards if c.get("card_id", "").upper() not in user_deck_ids and float(c.get("inclusion_percentage", 0.0)) >= 50.0]
    missing_staples.sort(key=lambda x: float(x.get("inclusion_percentage", 0.0)), reverse=True)
    
    # User cards with lowest meta inclusion
    scored_user_cards = []
    for c in user_deck_cards:
        cid = c.get("card_set_id", "").upper()
        pct = meta_pct_map.get(cid, 0.0)
        scored_user_cards.append({"card": c, "inclusion_percentage": pct})
    scored_user_cards.sort(key=lambda x: x["inclusion_percentage"])
    
    replacements = []
    for i in range(min(len(missing_staples), len(scored_user_cards))):
        if scored_user_cards[i]["inclusion_percentage"] < float(missing_staples[i].get("inclusion_percentage", 0.0)):
            replacements.append({
                "cut_card": scored_user_cards[i]["card"],
                "cut_inclusion": scored_user_cards[i]["inclusion_percentage"],
                "add_card": missing_staples[i],
                "add_inclusion": float(missing_staples[i].get("inclusion_percentage", 0.0))
            })
    return replacements

def evaluate_matchup(opponent_leader: dict, user_stats: dict, meta_alignment: float, leader_matchups_data: dict = None) -> dict:
    """
    Evaluates estimated win rate against a meta opponent leader.
    Uses real Limitless tournament match records if available, otherwise falls back to heuristics.
    """
    opp_name = opponent_leader.get("name", "").lower()
    opp_id = opponent_leader.get("leader_card_id", "").strip().upper()
    
    # 1. Check Real Limitless Matchup Data first
    real_match = get_real_matchup_winrate(opp_id, leader_matchups_data)
    if real_match:
        real_winrate = float(real_match.get("winrate", 50.0))
        tot = real_match.get("total_matches", 0)
        w = real_match.get("wins", 0)
        l = real_match.get("losses", 0)
        
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
    
    # 2. Heuristic Base Matchup Lookup
    base_winrate = KNOWN_LEADER_BASE_WINRATES.get(opp_id, 50.0)
        
    # 3. Meta Alignment Impact
    meta_modifier = (meta_alignment - 70.0) / 6.0
    estimated_winrate = base_winrate + meta_modifier
    
    # 4. Strategy Type Classification
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

def generate_dynamic_combat_guide(user_deck_cards: list, opponent_leader: dict) -> dict:
    """
    Generates a 100% dynamic combat guide tailored to the user's specific deck cards
    and the opponent's archetype (Aggro, Control, Tempo).
    """
    opp_name = opponent_leader.get("name", "").lower()
    is_aggro = any(k in opp_name for k in ["shanks", "zoro", "betty", "law", "ace", "kid"])
    is_big = any(k in opp_name for k in ["teach", "kaido", "enel", "linlin", "luffy", "sabo", "sakazuki", "kuzan"])
    opp_type = 'aggro' if is_aggro else ('control' if is_big else 'tempo')
    
    # Categorize user cards
    searchers = []
    blockers = []
    bosses = []
    counters_2k = []
    removals = []
    early_drops = []
    mid_drops = []
    odd_count = 0
    even_count = 0
    
    for c in user_deck_cards:
        txt = (c.get("card_text") or "").lower()
        cost = int(c.get("card_cost") or 0)
        counter = int(c.get("counter_amount") or 0)
        ctype = (c.get("card_type") or "").lower()
        
        if cost % 2 == 1:
            odd_count += 1
        elif cost > 0:
            even_count += 1
            
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
            
    searchers.sort(key=lambda x: int(x.get("card_cost") or 0))
    blockers.sort(key=lambda x: int(x.get("card_cost") or 0))
    early_drops.sort(key=lambda x: int(x.get("card_power") or 0), reverse=True)
    mid_drops.sort(key=lambda x: int(x.get("card_power") or 0), reverse=True)
    bosses.sort(key=lambda x: int(x.get("card_power") or 0), reverse=True)
    
    # Posture
    if is_aggro:
        badge = "🚨 Oponente Agressivo (Rush / Swarm)"
        msg = "Este oponente tentará zerar seus pontos de vida em ritmo acelerado desde os primeiros turnos. Postura recomendada: CONTROLE DE MESA E DEFESA. Não dispute corrida de vida; use seus personagens para limpar os atacantes virados (rested) dele e mantenha sua mão cheia de Counters (+2000)."
    elif is_big:
        badge = "🛡️ Oponente de Controle (Late Game / Chefes)"
        msg = "Este oponente quer arrastar o jogo para os turnos 8 a 10 e dominar o campo com personagens gigantes. Postura recomendada: PRESSÃO E AGRESSIVIDADE INICIAL. Ataque a vida do oponente nos turnos 2 a 4 para forçá-lo a queimar cartas da mão se defendendo."
    else:
        badge = "🔄 Oponente de Ritmo (Manipulação & Recursos)"
        msg = "Este líder manipula a mesa virando ou retornando peças. Postura recomendada: JOGO CADENCIADO E VALOR. Faça trocas vantajosas e evite deixar personagens virados sem proteção."

    # Turn Preference
    top_searcher = searchers[0] if searchers else None
    top_blocker = blockers[0] if blockers else None
    top_2k = counters_2k[0] if counters_2k else None
    top_mid = mid_drops[0] if mid_drops else None
    top_boss = bosses[0] if bosses else None
    top_removal = removals[0] if removals else None
    
    if odd_count >= even_count:
        pref_title = "Primeiro (Ímpar - 1, 3, 5, 7, 9 Don!!)"
        pref_desc = f"Seu deck possui predominância de custos ímpares ({odd_count} cartas). Ir primeiro encaixa com perfeição sua curva ideal sem deixar Don ocioso."
    else:
        pref_title = "Segundo (Par - 2, 4, 6, 8, 10 Don!!)"
        pref_desc = f"Seu deck possui predominância de custos pares ({even_count} cartas). Ir segundo garante +1 carta comprada e curva de Don sincronizada."

    # Mulligan
    if is_aggro:
        mulligan = f"🚨 Prioridade contra Agressividade: Mantenha defesas e cartas de custo baixo (ex: {top_searcher.get('card_name') if top_searcher else 'Buscador'} e {top_2k.get('card_name') if top_2k else '+2000 Counter'}). Se a mão vier pesada, faça Mulligan imediatamente."
    elif is_big:
        mulligan = f"🛡️ Prioridade contra Controle: Garanta peças de ataque proativo (ex: {top_mid.get('card_name') if top_mid else 'Atacante Mid'} e {top_searcher.get('card_name') if top_searcher else 'Buscador'}) para pressionar antes do turno 10."
    else:
        mulligan = "🔄 Prioridade para Ritmo: Busque curva balanceada de custo baixo e médio para trocas de recursos eficientes."

    # Don Curve
    early = f"Early Game (1-4 Don): Baixar {top_searcher.get('card_name') if top_searcher else 'buscador/drop inicial'} para estruturar o campo."
    mid = f"Mid Game (5-8 Don): Estabelecer {top_mid.get('card_name') if top_mid else 'atacante de custo médio'} para controlar a mesa."
    late = f"Late Game (9-10 Don): Descer {top_boss.get('card_name') if top_boss else 'Boss principal'} para finalizar com alta força."

    return {
        "tactical_badge": badge,
        "tactical_type": opp_type,
        "tactical_message": msg,
        "turn_preference": f"{pref_title} - {pref_desc}",
        "mulligan_tips": mulligan,
        "don_strategy": {
            "early": early,
            "mid": mid,
            "late": late
        },
        "matchup_explanation": msg
    }

