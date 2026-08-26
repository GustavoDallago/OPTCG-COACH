"""
OPTCG COACH - Comprehensive Unit & Integration Test Suite
Validates color compatibility, deck statistics, meta alignment, heuristic & tournament matchups,
smart replacements, dynamic combat guide, banlist multi-mode legality, atomic file writes, and game rules.
"""
from __future__ import annotations

import os
import re
import json
import glob
import tempfile
import unittest

from analyzer import (
    validate_deck_color,
    calculate_deck_stats,
    calculate_meta_alignment,
    evaluate_matchup,
    get_real_matchup_winrate,
    find_smart_replacements,
    generate_dynamic_combat_guide,
    load_banlist,
    validate_deck_legality,
    load_game_rules
)
from update_all import atomic_save_json

class TestDeckAnalyzer(unittest.TestCase):

    def test_color_validation(self):
        """Tests leader color compatibility for single and dual-color leaders."""
        # Mono Green Leader
        self.assertTrue(validate_deck_color("Green", "Green"))
        self.assertTrue(validate_deck_color("Green", "Green/Black"))
        self.assertFalse(validate_deck_color("Green", "Red"))

        # Dual Color Red/Green Leader
        self.assertTrue(validate_deck_color("Red/Green", "Red"))
        self.assertTrue(validate_deck_color("Red/Green", "Green"))
        self.assertTrue(validate_deck_color("Red/Green", "Red/Yellow"))
        self.assertFalse(validate_deck_color("Red/Green", "Blue"))

        # Don!! card is universal
        self.assertTrue(validate_deck_color("Green", "DON!!"))

    def test_deck_stats_calculation(self):
        """Tests deck card statistics, counters, blockers, removal count, and cost curve."""
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
        """Tests meta deck core card alignment percentage calculation."""
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
        """Tests matchup evaluation with heuristics and real tournament matchup data."""
        opp_aggro = {"name": "Shanks (Red)", "leader_card_id": "OP09-001"}
        user_stats_defensive = {
            "total_cards": 50,
            "counter_2000_count": 10,
            "counter_1000_count": 14,
            "blockers_count": 4,
            "removal_count": 2,
            "cost_distribution": {i: 0 for i in range(11)}
        }
        res = evaluate_matchup(opp_aggro, user_stats_defensive, 100.0)
        self.assertEqual(res["status"], "Equilibrado" if res["winrate"] < 55.0 else "Vantajoso")
        self.assertIn("Sua alta quantidade de defesas", res["recommendations"][0])
        self.assertFalse(res["is_real_data"])

        # Real Limitless Tournament Data
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
        """Tests intelligent card replacement recommendation excluding banned cards."""
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
        """Tests dynamic combat guide generation against Aggro and Control archetypes."""
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
        self.assertIn("user_avg_cost", guide_aggro)
        self.assertIn("opp_avg_cost", guide_aggro)
        self.assertIn("hand_composition", guide_aggro)
        self.assertIn("searchers", guide_aggro["hand_composition"])
        self.assertIn("bricks", guide_aggro["hand_composition"])
        self.assertTrue(len(guide_aggro["opp_curve_strategy"]) > 0)

        # Test Control opponent
        opp_control = {"name": "Marshall.D.Teach (Black)", "leader_card_id": "OP09-081"}
        meta_cards = [
            {"card_id": "OP17-095", "card_name": "Zoro", "inclusion_percentage": 100.0, "card_cost": "5"},
            {"card_id": "OP17-056", "card_name": "Sanji", "inclusion_percentage": 90.0, "card_cost": "4"}
        ]
        guide_control = generate_dynamic_combat_guide(user_deck, opp_control, leader_meta_cards=meta_cards)
        self.assertEqual(guide_control["tactical_type"], "control")
        self.assertIn("🛡️ Oponente de Controle", guide_control["tactical_badge"])
        self.assertIn("Zoro", guide_control["mulligan_tips"])
        self.assertTrue(len(guide_control["key_counter_cards"]) > 0)
        self.assertIn("searchers", guide_control["hand_composition"])
        self.assertIn("bricks", guide_control["hand_composition"])
        self.assertIn("opp_curve_strategy", guide_control)

        zoro_entry = next((c for c in guide_control["key_counter_cards"] if c["card_id"] == "OP17-095"), None)
        self.assertIsNotNone(zoro_entry)
        self.assertTrue(zoro_entry["in_deck"])

        sanji_entry = next((c for c in guide_control["key_counter_cards"] if c["card_id"] == "OP17-056"), None)
        self.assertIsNotNone(sanji_entry)
        self.assertFalse(sanji_entry["in_deck"])
        self.assertTrue(sanji_entry["winrate_boost"] > 0)

        # Test Deck without Blockers and without 2k counters
        deck_no_defense = [
            {"card_name": "Luffy", "card_set_id": "OP01-001", "card_cost": "4", "card_power": "6000", "card_type": "Character"},
            {"card_name": "Zoro", "card_set_id": "OP01-025", "card_cost": "3", "card_power": "5000", "card_type": "Character"}
        ]
        guide_no_def = generate_dynamic_combat_guide(deck_no_defense, opp_control)
        self.assertNotIn("Blocker (Blocker)", guide_no_def["hand_composition"]["defenses"])
        self.assertIn("0x (Sem Blockers", guide_no_def["hand_composition"]["defenses"])

    def test_banned_pairs_and_copy_limit_violations(self):
        """Tests that illegal card pairs and over-copy limits are correctly detected."""
        banlist_with_pairs = {
            "banned_cards": [],
            "banned_sets": [],
            "banned_starter_decks": [],
            "whitelisted_cards": [],
            "restricted_cards": {"OP02-001": 1},
            "banned_pairs": [["OP07-115", "EB04-058"]]
        }

        # 1. Deck with illegal pair
        deck_with_pair = [
            {"card_set_id": "OP07-115", "card_name": "Card A", "quantity": 2},
            {"card_set_id": "EB04-058", "card_name": "Card B", "quantity": 2}
        ]
        val_pair = validate_deck_legality(deck_with_pair, banlist_data=banlist_with_pairs, check_size=False)
        self.assertFalse(val_pair["is_legal"])
        self.assertEqual(len(val_pair["banned_pairs_found"]), 1)
        self.assertEqual(val_pair["banned_pairs_found"][0], ["OP07-115", "EB04-058"])

        # 2. Deck with over-copy violation (5x of normal card or 2x of restricted card)
        deck_with_overcopy = [
            {"card_set_id": "OP01-001", "card_name": "Normal Card", "quantity": 5},
            {"card_set_id": "OP02-001", "card_name": "Restricted Card", "quantity": 2}
        ]
        val_overcopy = validate_deck_legality(deck_with_overcopy, banlist_data=banlist_with_pairs, check_size=False)
        self.assertFalse(val_overcopy["is_legal"])
        self.assertEqual(len(val_overcopy["overcopy_violations"]), 2)

    def test_game_rules_loader(self):
        """Tests loading of shared game rules configuration."""
        rules = load_game_rules(force_reload=True)
        self.assertIn("deck_constraints", rules)
        self.assertEqual(rules["deck_constraints"]["deck_size"], 50)
        self.assertEqual(rules["deck_constraints"]["max_card_copies"], 4)
        self.assertIn("counter_tiers", rules)

    def test_atomic_save_json(self):
        """Tests that atomic_save_json writes data safely without corrupting files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test_data.json")
            test_payload = {"status": "ok", "items": [1, 2, 3]}

            success = atomic_save_json(test_payload, test_file)
            self.assertTrue(success)
            self.assertTrue(os.path.exists(test_file))

            with open(test_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertEqual(loaded, test_payload)

    def test_manifest_generation(self):
        """Tests that manifest.json exists and lists available sets correctly."""
        manifest_path = 'optcg_data/manifest.json'
        self.assertTrue(os.path.exists(manifest_path), 'manifest.json not found. Run update_all.py to generate it.')

        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        self.assertIn('available_meta_sets', manifest)
        self.assertIn('generated_at', manifest)
        self.assertIn('total_sets', manifest)
        self.assertIsInstance(manifest['available_meta_sets'], list)
        self.assertEqual(manifest['total_sets'], len(manifest['available_meta_sets']))

    def test_banlist_integrity_and_filtering(self):
        """Tests banlist integrity and exclusion from recommendations in analyzer.py."""
        banlist = load_banlist("EN")
        self.assertIn("banned_cards", banlist)
        self.assertTrue(len(banlist["banned_cards"]) > 0)

        # Verify ban_sets.json, ban_st.json, and whitelist.json integration
        self.assertIn("banned_sets", banlist)
        self.assertIn("OP01", banlist["banned_sets"])
        self.assertIn("banned_starter_decks", banlist)
        self.assertIn("ST01", banlist["banned_starter_decks"])
        self.assertIn("whitelisted_cards", banlist)

        # Test smart replacement filtering with EN mode
        mock_user_deck = [
            {"card_set_id": "OP09-001", "card_name": "Koby"},
            {"card_set_id": "OP09-002", "card_name": "Helmeppo"}
        ]
        mock_leader_meta_cards = [
            {"card_id": "OP06-086", "card_name": "Gecko Moria (Banned Individual)", "inclusion_percentage": 95.0},
            {"card_id": "OP01-025", "card_name": "Roronoa Zoro (Banned Set OP01, Not Whitelisted)", "inclusion_percentage": 90.0},
            {"card_id": "OP01-016", "card_name": "Nami (Whitelisted)", "inclusion_percentage": 85.0},
            {"card_id": "OP09-025", "card_name": "Roronoa Zoro (Legal)", "inclusion_percentage": 80.0}
        ]

        replacements = find_smart_replacements(mock_user_deck, mock_leader_meta_cards, banlist)
        added_ids = [r["add_card"]["card_id"] for r in replacements]

        self.assertNotIn("OP06-086", added_ids)
        self.assertNotIn("OP01-025", added_ids)
        self.assertIn("OP01-016", added_ids)
        self.assertIn("OP09-025", added_ids)

if __name__ == "__main__":
    unittest.main()
