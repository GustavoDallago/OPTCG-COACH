import unittest
from analyzer import (
    validate_deck_color,
    calculate_deck_stats,
    calculate_meta_alignment,
    evaluate_matchup
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
        
        # Case 2: Weak defense against aggro opponent
        user_stats_weak = {
            "counter_2000_count": 2,
            "blockers_count": 0,
            "removal_count": 2
        }
        res_weak = evaluate_matchup(opp_aggro, user_stats_weak, 70.0)
        self.assertEqual(res_weak["status"], "Desfavorável")
        self.assertTrue(res_weak["winrate"] < 45.0)
        self.assertIn("Cuidado: Seu deck tem poucas defesas", res_weak["recommendations"][0])

if __name__ == "__main__":
    unittest.main()
