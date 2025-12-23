from test_states import load_states_sorted
from pathlib import Path
import json
from unittest.mock import patch, MagicMock
from collections import defaultdict
import sys

# Add parent directory to path to import daily_points_v2
sys.path.insert(0, str(Path(__file__).parent.parent))
from daily_points_v2 import give_points_for_user_state, POINTS_PER_PILOT_VAULT_TOKEN, POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT
from utils.process_event_above_user_state import UserState

DATA_DIR = Path("data")


def load_points_sorted():
    points_dir = DATA_DIR / "points"
    points = sorted(points_dir.glob("*.json"), key=lambda f: int(f.stem))
    return [json.loads(f.read_text()) for f in points]


class TestPoints:
    def test_points_borders_match_states_borders(self):
        points = load_points_sorted()
        states = load_states_sorted()
        for point, state in zip(points, states):
            assert (
                point["start_block"] == state["start_block"]
            ), f"Day {point['day_index']} point start block {point['start_block']} does not match state start block {state['start_block']}"
            assert (
                point["end_block"] == state["end_block"]
            ), f"Day {point['day_index']} point end block {point['end_block']} does not match state end block {state['end_block']}"
            assert (
                point["date"] == state["date"]
            ), f"Day {point['day_index']} point date {point['date']} does not match state date {state['date']}"

    def test_points_without_daily_change(self):
        points = load_points_sorted()
        states = load_states_sorted()

        point = points[81]
        state = states[81]

        user = "0xd23d8aead200401091022e5c4304b32b56042808"
        points_per_one_wei = (point["end_block"] - point["start_block"] + 1) * 1420
        expected_points = state["pilot_vault"]["end_state"][user]["balance"] * points_per_one_wei

        assert (
            expected_points == point["points"][user]
        ), f"Expected points for user {user} without nft and balance change does not match calculated points: {expected_points} != {point['points'][user]}"



    def test_user_balance_changed(self):
        points = load_points_sorted()
        states = load_states_sorted()

        point = points[79]
        state = states[79]

        user = "0xAfD8FB69E850D2Da8ac47E4443b0140F4dE5Fb4f".lower()

        event_block_number = 23993946
        user_balance_before = state["pilot_vault"]["start_state"][user]["balance"]
        balance_increase = 198777366745194886

        expected_points = (
            user_balance_before * 1420 * (event_block_number - state["start_block"])
        )
        expected_points += (
            (user_balance_before + balance_increase)
            * 1420
            * (point["end_block"] - event_block_number + 1)
        )

        assert (
            expected_points == point["points"][user]
        ), f"Expected points for user {user} without nft but with balance change does not match calculated points: {expected_points} != {point['points'][user]}"

    # Impossible to test with current data, since everyone has nfts. Worked before, to be added later
    # def test_nft_balance_changed(self):
    #     points = load_points_sorted()
    #     states = load_states_sorted()

    #     point = points[77]
    #     state = states[77]

    #     user = "0xC3cB47f1d74abc82Cc9acd748c9C6714F9c77EFF".lower()
    #     event_block_number = 23983629
    #     start_block = state["start_block"]
    #     end_block = state["end_block"]
    #     balance = state["pilot_vault"]["start_state"][user]
    #     expected_points = balance * 1000 * (event_block_number - start_block)
    #     expected_points += balance * 1420 * (end_block - event_block_number + 1)
    #     assert (
    #         expected_points == point["points"][user]
    #     ), f"Expected points for user {user} with nft balance change but without balance change does not match calculated points: {expected_points} != {point['points'][user]}"

    @patch('daily_points_v2.lp_balances_snapshot', new={
        "0x1234567890123456789012345678901234567890": UserState(balance=100)
    })
    def test_give_points_user_without_nft(self):
        """Test that users without NFT get POINTS_PER_PILOT_VAULT_TOKEN per token"""
        user_state = {
            "0x1234567890123456789012345678901234567890": UserState(balance=500, nft_ids=set())
        }
        points = defaultdict(int)
        
        result = give_points_for_user_state(user_state, points)
        
        balance_excluding_snapshot = max(0, 500 - 100)  # 400
        expected_points = balance_excluding_snapshot * POINTS_PER_PILOT_VAULT_TOKEN  # 400 * 1000 = 400000
        
        assert result["0x1234567890123456789012345678901234567890"] == expected_points
        assert result["0x1234567890123456789012345678901234567890"] == 400000

    @patch('daily_points_v2.lp_balances_snapshot', new={
        "0xABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD": UserState(balance=200)
    })
    def test_give_points_user_with_nft(self):
        """Test that users with NFT get POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT per token"""
        user_state = {
            "0xABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD": UserState(balance=1000, nft_ids={1, 2, 3})
        }
        points = defaultdict(int)
        
        result = give_points_for_user_state(user_state, points)
        
        balance_excluding_snapshot = max(0, 1000 - 200)  # 800
        expected_points = balance_excluding_snapshot * POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT  # 800 * 1420 = 1136000
        
        assert result["0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"] == expected_points
        assert result["0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"] == 1136000

    @patch('daily_points_v2.lp_balances_snapshot', new={
        "0x1111111111111111111111111111111111111111": UserState(balance=1000)
    })
    def test_give_points_balance_excluding_snapshot(self):
        """Test that balance_excluding_snapshot correctly subtracts snapshot balance"""
        user_state = {
            "0x1111111111111111111111111111111111111111": UserState(balance=500, nft_ids=set())
        }
        points = defaultdict(int)
        
        result = give_points_for_user_state(user_state, points)
        
        # balance_excluding_snapshot should be max(0, 500 - 1000) = 0
        assert result["0x1111111111111111111111111111111111111111"] == 0

    @patch('daily_points_v2.lp_balances_snapshot', new={
        "0xABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD": UserState(balance=0)
    })
    def test_give_points_address_lowercasing(self):
        """Test that addresses are properly lowercased"""
        user_state = {
            "0xABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD": UserState(balance=100, nft_ids=set())
        }
        points = defaultdict(int)
        
        result = give_points_for_user_state(user_state, points)
        
        # Should use lowercase address as key
        assert "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd" in result
        assert "0xABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD" not in result
        assert result["0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"] == 100 * POINTS_PER_PILOT_VAULT_TOKEN

    @patch('daily_points_v2.lp_balances_snapshot', new={
        "0x2222222222222222222222222222222222222222": UserState(balance=0)
    })
    def test_give_points_points_accumulation(self):
        """Test that points are accumulated (added to existing points)"""
        user_state = {
            "0x2222222222222222222222222222222222222222": UserState(balance=100, nft_ids=set())
        }
        points = defaultdict(int)
        points["0x2222222222222222222222222222222222222222"] = 5000  # Existing points
        
        result = give_points_for_user_state(user_state, points)
        
        expected_new_points = 100 * POINTS_PER_PILOT_VAULT_TOKEN  # 100000
        assert result["0x2222222222222222222222222222222222222222"] == 5000 + expected_new_points
        assert result["0x2222222222222222222222222222222222222222"] == 105000

    @patch('daily_points_v2.lp_balances_snapshot', new={
        "0x1111111111111111111111111111111111111111": UserState(balance=100),
        "0x2222222222222222222222222222222222222222": UserState(balance=200),
    })
    def test_give_points_multiple_users(self):
        """Test that multiple users are handled correctly"""
        user_state = {
            "0x1111111111111111111111111111111111111111": UserState(balance=500, nft_ids=set()),
            "0x2222222222222222222222222222222222222222": UserState(balance=1000, nft_ids={1}),
        }
        points = defaultdict(int)
        
        result = give_points_for_user_state(user_state, points)
        
        # User 1: no NFT, balance_excluding_snapshot = 500 - 100 = 400
        assert result["0x1111111111111111111111111111111111111111"] == 400 * POINTS_PER_PILOT_VAULT_TOKEN
        
        # User 2: with NFT, balance_excluding_snapshot = 1000 - 200 = 800
        assert result["0x2222222222222222222222222222222222222222"] == 800 * POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT

    @patch('daily_points_v2.lp_balances_snapshot', new={
        "0x3333333333333333333333333333333333333333": UserState(balance=500)
    })
    def test_give_points_zero_balance_excluding_snapshot(self):
        """Test that zero balance_excluding_snapshot results in zero points"""
        user_state = {
            "0x3333333333333333333333333333333333333333": UserState(balance=500, nft_ids=set())
        }
        points = defaultdict(int)
        
        result = give_points_for_user_state(user_state, points)
        
        # balance_excluding_snapshot = max(0, 500 - 500) = 0
        assert result["0x3333333333333333333333333333333333333333"] == 0

    @patch('daily_points_v2.lp_balances_snapshot', new={
        "0x4444444444444444444444444444444444444444": UserState(balance=0)
    })
    def test_give_points_empty_nft_set(self):
        """Test that empty NFT set is treated as no NFT"""
        user_state = {
            "0x4444444444444444444444444444444444444444": UserState(balance=100, nft_ids=set())
        }
        points = defaultdict(int)
        
        result = give_points_for_user_state(user_state, points)
        
        # Empty set should use POINTS_PER_PILOT_VAULT_TOKEN (not FOR_NFT)
        assert result["0x4444444444444444444444444444444444444444"] == 100 * POINTS_PER_PILOT_VAULT_TOKEN
