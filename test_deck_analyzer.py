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
            {"card_name": "Zoro", "card_set_id": "OP17-095", "card_cost": "5", "card_power": "6000", "card_type": "Character"},
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
        
        # Test Control opponent
        opp_control = {"name": "Marshall.D.Teach (Black)", "leader_card_id": "OP09-081"}
        guide_control = generate_dynamic_combat_guide(user_deck, opp_control)
        self.assertEqual(guide_control["tactical_type"], "control")
        self.assertIn("🛡️ Oponente de Controle", guide_control["tactical_badge"])
        self.assertIn("Zoro", guide_control["mulligan_tips"])

if __name__ == "__main__":
    unittest.main()
