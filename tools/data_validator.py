"""
data_validator.py
Data Integrity and Schema Validation for OPTCG-COACH Meta Data and Decks.
Follows strict schema assertions and defensive programming to protect production files.
"""
from typing import Dict, Any, List, Tuple, Optional
import re

class DataValidationError(Exception):
    """Raised when data structure does not satisfy schema requirements."""
    pass

def validate_meta_leader(leader: Dict[str, Any]) -> List[str]:
    """Validates an individual leader entry from a meta dataset. Returns list of error messages."""
    errors = []
    
    # Required core fields
    req_fields = ["name", "leader_card_id", "deck_count", "share_percentage"]
    for field in req_fields:
        if field not in leader:
            errors.append(f"Leader missing required field '{field}'")
    
    lid = leader.get("leader_card_id")
    if not lid or not isinstance(lid, str):
        errors.append("leader_card_id must be a non-empty string")
    
    deck_count = leader.get("deck_count")
    if deck_count is None or not isinstance(deck_count, (int, float)) or deck_count < 0:
        errors.append(f"Invalid deck_count for leader {lid}: {deck_count}")
        
    share = leader.get("share_percentage")
    if share is None or not isinstance(share, (int, float)) or not (0.0 <= float(share) <= 100.0):
        errors.append(f"Invalid share_percentage for leader {lid}: {share}")
        
    wr = leader.get("overall_winrate")
    if wr is not None:
        if not isinstance(wr, (int, float)) or not (0.0 <= float(wr) <= 100.0):
            errors.append(f"Invalid overall_winrate for leader {lid}: {wr}")
            
    # Validate card breakdown if present
    cards = leader.get("cards", [])
    if not isinstance(cards, list):
        errors.append(f"cards attribute must be a list for leader {lid}")
    else:
        for idx, c in enumerate(cards):
            if not isinstance(c, dict):
                errors.append(f"Card entry at index {idx} is not a dictionary for leader {lid}")
                continue
            if not c.get("card_id"):
                errors.append(f"Card entry at index {idx} missing card_id for leader {lid}")
            inc = c.get("inclusion_percentage")
            if inc is not None and (not isinstance(inc, (int, float)) or not (0.0 <= float(inc) <= 100.0)):
                errors.append(f"Invalid inclusion_percentage for card {c.get('card_id')}: {inc}")

    return errors

def validate_meta_dataset(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates a complete meta JSON dataset (e.g., meta_OP17.json).
    Returns (True, []) if valid, or (False, [errors]) if validation failed.
    """
    errors = []
    if not isinstance(data, dict):
        return False, ["Root meta payload must be a dictionary"]
        
    if not data.get("set_code"):
        errors.append("Meta payload missing 'set_code'")
        
    leaders = data.get("leaders")
    if leaders is None or not isinstance(leaders, list):
        return False, ["'leaders' field must be a list"]
        
    for l in leaders:
        if not isinstance(l, dict):
            errors.append("Encountered non-dict item in leaders list")
            continue
        l_errs = validate_meta_leader(l)
        if l_errs:
            errors.extend(l_errs)
            
    return len(errors) == 0, errors

def validate_deck_text(deck_txt: str) -> Tuple[bool, int, Optional[str], List[str]]:
    """
    Validates a One Piece TCG deck in standard simulator format (e.g. 1xOP01-001, 4xOP01-004).
    Returns (is_valid, total_card_count, leader_id, list_of_errors).
    """
    errors = []
    lines = deck_txt.strip().splitlines()
    leader_id = None
    main_deck_count = 0
    card_counts: Dict[str, int] = {}
    
    line_pattern = re.compile(r"^(\d+)[xX]([A-Za-z0-9_\-]+)")
    
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
            
        m = line_pattern.match(line)
        if not m:
            continue
            
        qty = int(m.group(1))
        cid = m.group(2).upper()
        
        # If leader detected (1x and at the beginning or explicitly marked)
        if leader_id is None and qty == 1:
            leader_id = cid
            continue
            
        card_counts[cid] = card_counts.get(cid, 0) + qty
        main_deck_count += qty
        
        if card_counts[cid] > 4:
            errors.append(f"Card {cid} exceeds maximum allowed limit of 4 copies (found {card_counts[cid]})")
            
    if main_deck_count != 50:
        errors.append(f"Main deck must have exactly 50 cards (found {main_deck_count})")
        
    if not leader_id:
        errors.append("No leader card identified in deck text")
        
    return len(errors) == 0, main_deck_count, leader_id, errors
