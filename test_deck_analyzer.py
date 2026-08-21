import unittest
from analyzer import (
    validate_deck_color,
    calculate_deck_stats,
    calculate_meta_alignment,
    evaluate_matchup,
    get_real_matchup_winrate,
    find_smart_replacements,
    generate_dynamic_combat_guide
)

class TestDeckAnalyzer(unittest.TestCase):

    def test_color_validation(self):
        # Mono Green Leader
        self.assertTrue(validate_deck_color("Green", "Green"))
        self.assertTrue(validate_deck_color("Green", "Green/Black"))
        self.assertFalse(validate_deck_color("Green", "Red"))
        
        # Dual Color Red/Green Leader
        self.assertTrue(validate_deck_color("Red/Green", "Red"))
        self.assertTrue(validate_deck_color("Red/Green", "Green"))
        self.assertTrue(validate_deck_color("Red/Green", "Red/Yellow"))
        self.assertFalse(validate_deck_color("Red/Green", "Blue"))
        
        # Don!! Case
        self.assertTrue(validate_deck_color("Green", "DON!!"))

    def test_deck_stats_calculation(self):
        mock_deck = [
            {"card_name": "Kikunojo", "card_cost": "4", "counter_amount": 1000, "card_text": "Character", "quantity": 4},
            {"card_name": "Tony.Tony.Chopper", "card_cost": "1", "counter_amount": 0, "card_text": "[Blocker] Rest this card...", "quantity": 2},
            {"card_name": "Otama", "card_cost": "1", "counter_amount": 2000, "card_text": "Character", "quantity": 4},
            {"card_name": "Radical Beam", "card_type": "Event", "card_cost": "1", "card_text": "[Counter] K.O. up to 1 character.", "quantity": 3}
        ]
        
        stats = calculate_deck_stats(mock_deck)
        
        self.assertEqual(stats["total_cards"], 13)
        self.assertEqual(stats["counter_2000_count"], 4)
        self.assertEqual(stats["counter_1000_count"], 4)
        self.assertEqual(stats["blockers_count"], 2)
        self.assertEqual(stats["removal_count"], 3)
        
        # Cost distribution
        self.assertEqual(stats["cost_distribution"][4], 4)
        self.assertEqual(stats["cost_distribution"][1], 9)

    def test_meta_alignment(self):
        leader_meta = [
            {"card_id": "OP01-001", "inclusion_percentage": 100.0},
            {"card_id": "OP01-002", "inclusion_percentage": 80.0},
            {"card_id": "OP01-003", "inclusion_percentage": 60.0},
            {"card_id": "OP01-004", "inclusion_percentage": 20.0}
        ]
        
        # Case 1: Deck with all staples
        deck_perfect = ["OP01-001", "OP01-002", "OP01-003"]
        alignment = calculate_meta_alignment(deck_perfect, leader_meta)
        self.assertEqual(alignment, 100.0)
        
        # Case 2: Deck with only 1 staple
        deck_weak = ["OP01-001", "OP01-099"]
        alignment_weak = calculate_meta_alignment(deck_weak, leader_meta)
        self.assertAlmostEqual(alignment_weak, 41.66, places=1)

    def test_matchup_heuristic_evaluation(self):
        # Case 1: Defensive deck against aggro opponent (Shanks Red)
        opp_aggro = {"name": "Shanks (Red)", "leader_card_id": "OP09-001"}
        user_stats_defensive = {
            "counter_2000_count": 10,
            "blockers_count": 4,
            "removal_count": 2
        }
        res = evaluate_matchup(opp_aggro, user_stats_defensive, 100.0)
        self.assertEqual(res["status"], "Equilibrado" if res["winrate"] < 55.0 else "Vantajoso")
        self.assertIn("Sua alta quantidade de defesas", res["recommendations"][0])
        self.assertFalse(res["is_real_data"])
        
        # Case 2: Real Limitless Matchup Data Available
        matchups_data = {
            "OP09-001": {
                "opponent_id": "OP09-001",
                "opponent_name": "Shanks (Red)",
                "wins": 18,
                "losses": 6,
                "total_matches": 24,
                "winrate": 75.0
            }
        }
        res_real = evaluate_matchup(opp_aggro, user_stats_defensive, 100.0, leader_matchups_data=matchups_data)
        self.assertTrue(res_real["is_real_data"])
        self.assertEqual(res_real["winrate"], 75.0)
        self.assertEqual(res_real["status"], "Vantajoso")
        self.assertEqual(res_real["total_matches"], 24)

    def test_smart_card_replacements(self):
        user_deck = [
            {"card_name": "Random Vanilla", "card_set_id": "OP01-999"},
            {"card_name": "Core Card A", "card_set_id": "OP17-039"}
        ]
        meta_cards = [
            {"card_name": "Core Card A", "card_id": "OP17-039", "inclusion_percentage": 100.0},
            {"card_name": "Essential Staple B", "card_id": "OP17-056", "inclusion_percentage": 95.0}
        ]
        replacements = find_smart_replacements(user_deck, meta_cards)
        self.assertEqual(len(replacements), 1)
        self.assertEqual(replacements[0]["cut_card"]["card_set_id"], "OP01-999")
        self.assertEqual(replacements[0]["add_card"]["card_id"], "OP17-056")

    def test_dynamic_combat_guide(self):
        user_deck = [
            {"card_name": "Otama", "card_set_id": "OP07-022", "card_cost": "1", "card_text": "Look at 5 cards and add 1", "counter_amount": 2000, "card_type": "Character"},
            {"card_name": "Chopper", "card_set_id": "OP17-084", "card_cost": "2", "card_text": "[Blocker]", "counter_amount": 1000, "card_type": "Character"},
            {"card_name": "Zoro", "card_set_id": "OP17-095", "card_cost": "5", "card_power": "6000", "card_text": "[On Play] K.O. 1 character.", "card_type": "Character"},
            {"card_name": "Loki", "card_set_id": "OP17-119", "card_cost": "9", "card_power": "10000", "card_type": "Character"}
        ]
        
        # Test Aggro opponent
        opp_aggro = {"name": "Shanks (Red)", "leader_card_id": "OP09-001"}
        guide_aggro = generate_dynamic_combat_guide(user_deck, opp_aggro)
        self.assertEqual(guide_aggro["tactical_type"], "aggro")
        self.assertIn("🚨 Oponente Agressivo", guide_aggro["tactical_badge"])
        self.assertIn("Otama", guide_aggro["mulligan_tips"])
        self.assertIn("Early Game", guide_aggro["don_strategy"]["early"])
        self.assertIn("Otama", guide_aggro["don_strategy"]["early"])
        
        # Test Control opponent with meta cards
        opp_control = {"name": "Marshall.D.Teach (Black)", "leader_card_id": "OP09-081"}
        meta_cards = [
            {"card_id": "OP17-095", "card_name": "Zoro", "inclusion_percentage": 100.0},
            {"card_id": "OP17-056", "card_name": "Sanji", "inclusion_percentage": 90.0}
        ]
        guide_control = generate_dynamic_combat_guide(user_deck, opp_control, leader_meta_cards=meta_cards)
        self.assertEqual(guide_control["tactical_type"], "control")
        self.assertIn("🛡️ Oponente de Controle", guide_control["tactical_badge"])
        self.assertIn("Zoro", guide_control["mulligan_tips"])
        self.assertIn("key_counter_cards", guide_control)
        self.assertTrue(len(guide_control["key_counter_cards"]) > 0)
        
        # Check that Zoro is recognized as in_deck: True
        zoro_entry = next((c for c in guide_control["key_counter_cards"] if c["card_id"] == "OP17-095"), None)
        self.assertIsNotNone(zoro_entry)
        self.assertTrue(zoro_entry["in_deck"])
        
        # Check that Sanji is recognized as in_deck: False with winrate_boost
        sanji_entry = next((c for c in guide_control["key_counter_cards"] if c["card_id"] == "OP17-056"), None)
        self.assertIsNotNone(sanji_entry)
        self.assertFalse(sanji_entry["in_deck"])
        self.assertTrue(sanji_entry["winrate_boost"] > 0)

    def test_txt_import_parser_formats(self):
        """Tests that various TXT import formats are all parsed correctly."""
        import re
        
        def parse_txt_line(line):
            """Mirror the TXT import logic from index.html's importFromText function."""
            line = line.strip()
            if not line:
                return None
            # Various formats: 4xOP01-001, 4 x OP01-001, 4 OP01-001, OP01-001 (qty=1)
            patterns = [
                r'^(\d+)\s*[xX]\s*([A-Z0-9]+-\d+[A-Z]?)$',     # 4xOP01-001 or 4 x OP01-001
                r'^(\d+)\s+([A-Z0-9]+-\d+[A-Z]?)$',              # 4 OP01-001
                r'^([A-Z0-9]+-\d+[A-Z]?)\s*[xX]\s*(\d+)$',      # OP01-001x4
                r'^([A-Z0-9]+-\d+[A-Z]?)$',                        # OP01-001 (qty=1)
            ]
            for i, p in enumerate(patterns):
                m = re.match(p, line, re.IGNORECASE)
                if m:
                    if i < 2:
                        return {'qty': int(m.group(1)), 'id': m.group(2).upper()}
                    elif i == 2:
                        return {'qty': int(m.group(2)), 'id': m.group(1).upper()}
                    else:
                        return {'qty': 1, 'id': m.group(1).upper()}
            return None
        
        self.assertEqual(parse_txt_line('4xOP01-001'), {'qty': 4, 'id': 'OP01-001'})
        self.assertEqual(parse_txt_line('4 x OP01-001'), {'qty': 4, 'id': 'OP01-001'})
        self.assertEqual(parse_txt_line('4 OP01-001'), {'qty': 4, 'id': 'OP01-001'})
        self.assertEqual(parse_txt_line('OP01-001x4'), {'qty': 4, 'id': 'OP01-001'})
        self.assertEqual(parse_txt_line('OP01-001'), {'qty': 1, 'id': 'OP01-001'})
        self.assertIsNone(parse_txt_line(''))
        self.assertIsNone(parse_txt_line('# comment line'))

    def test_meta_json_integrity(self):
        """Tests that no meta JSON file contains Japanese card names or JP image URLs."""
        import glob
        import json
        import re
        
        JP_PATTERNS = [
            re.compile(r'_JP\.webp', re.IGNORECASE),
            re.compile(r'_jp\.webp', re.IGNORECASE),
            re.compile(r'japanese', re.IGNORECASE),
        ]
        
        meta_files = glob.glob('optcg_data/meta_*.json')
        self.assertTrue(len(meta_files) > 0, 'No meta JSON files found in optcg_data/')
        
        violations = []
        for filepath in meta_files:
            with open(filepath, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except Exception:
                    continue
            for leader in data.get('leaders', []):
                for card in leader.get('cards', []):
                    image = card.get('image', '')
                    name = card.get('card_name', '')
                    for pat in JP_PATTERNS:
                        if pat.search(image) or pat.search(name):
                            violations.append(f"{filepath}: card {card.get('card_id','')} - {image or name}")
        
        self.assertEqual(violations, [], f"JP cards found:\n" + "\n".join(violations[:5]))

    def test_manifest_generation(self):
        """Tests that manifest.json exists and lists available sets correctly."""
        import json
        import glob
        import os
        
        manifest_path = 'optcg_data/manifest.json'
        self.assertTrue(os.path.exists(manifest_path), 'manifest.json not found. Run update_all.py to generate it.')
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        self.assertIn('available_meta_sets', manifest)
        self.assertIn('generated_at', manifest)
        self.assertIn('total_sets', manifest)
        self.assertIsInstance(manifest['available_meta_sets'], list)
        self.assertEqual(manifest['total_sets'], len(manifest['available_meta_sets']))
        
        # Verify each entry in manifest corresponds to a real file
        for entry in manifest['available_meta_sets']:
            self.assertIn('code', entry)
            code = entry['code']
            expected_file = f'optcg_data/meta_{code}.json'
            self.assertTrue(glob.glob(expected_file), f'Manifest references {code} but file not found')

    def test_zero_win_leader_cards_fallback(self):
        """Tests that zero-win leaders in meta files have fallback cards populated."""
        import json
        import glob

        for filepath in glob.glob('optcg_data/meta_*.json'):
            with open(filepath, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except Exception:
                    continue
            for leader in data.get('leaders', []):
                winrate = leader.get('overall_winrate', 0.0)
                total_wins = sum(m.get('wins', 0) for m in leader.get('matchups', {}).values())
                if (winrate == 0.0 or total_wins == 0):
                    cards = leader.get('cards', [])
                    self.assertTrue(len(cards) > 0, f"Leader {leader.get('name')} in {filepath} has 0 wins but empty cards list")

    def test_banlist_integrity_and_filtering(self):
        """Tests banlist integrity and exclusion from recommendations in analyzer.py."""
        import json
        import os
        from analyzer import load_banlist, find_smart_replacements, validate_deck_legality

        banlist_path = 'optcg_data/banlist.json'
        self.assertTrue(os.path.exists(banlist_path), "banlist.json does not exist. Run scrape_banlist.py first.")

        banlist = load_banlist("EN")
        self.assertIn("banned_cards", banlist)
        self.assertTrue(len(banlist["banned_cards"]) > 0)
        self.assertIn("OP06-086", banlist["banned_cards"]) # Gecko Moria

        # Test smart replacement filtering with EN mode
        mock_user_deck = [{"card_set_id": "OP01-016", "card_name": "Nami"}]
        mock_leader_meta_cards = [
            {"card_id": "OP06-086", "card_name": "Gecko Moria (Banned)", "inclusion_percentage": 95.0},
            {"card_id": "OP09-025", "card_name": "Roronoa Zoro (Legal)", "inclusion_percentage": 80.0}
        ]

        replacements = find_smart_replacements(mock_user_deck, mock_leader_meta_cards, banlist)
        added_ids = [r["add_card"]["card_id"] for r in replacements]
        
        # Gecko Moria (OP06-086) MUST NOT be suggested because it is banned!
        self.assertNotIn("OP06-086", added_ids)
        self.assertIn("OP09-025", added_ids)

        # Test deck legality validation (EN mode)
        deck_with_banned = [{"card_set_id": "OP06-086", "card_name": "Gecko Moria"}]
        val_res = validate_deck_legality(deck_with_banned, mode="EN")
        self.assertFalse(val_res["is_legal"])
        self.assertEqual(len(val_res["banned_cards_found"]), 1)

        # Test NONE mode (Histórico / Sem Banlist)
        val_none = validate_deck_legality(deck_with_banned, mode="NONE")
        self.assertTrue(val_none["is_legal"])
        self.assertEqual(len(val_none["banned_cards_found"]), 0)

        # Test Banned Sets & Starter Decks with Whitelisted Exception (Sobrevida)
        custom_banlist = {
            "banned_sets": ["OP01"],
            "banned_starter_decks": ["ST01"],
            "whitelisted_cards": ["ST01-001"],
            "banned_cards": [],
            "banned_pairs": []
        }
        test_deck = [
            {"card_set_id": "OP01-025", "card_name": "Zoro"}, # Banned set
            {"card_set_id": "ST01-005", "card_name": "Jinbe"}, # Banned starter
            {"card_set_id": "ST01-001", "card_name": "Luffy Leader"} # Whitelisted (Sobrevida)
        ]
        val_custom = validate_deck_legality(test_deck, mode="EN", banlist_data=custom_banlist)
        # Ensure ST01-001 (Luffy Leader) is whitelisted and OP01-025 / ST01-005 are flagged as banned
        banned_ids = [c["card_id"] for c in val_custom["banned_cards_found"]]
        self.assertIn("OP01-025", banned_ids)
        self.assertIn("ST01-005", banned_ids)
        self.assertNotIn("ST01-001", banned_ids)

if __name__ == "__main__":
    unittest.main()
