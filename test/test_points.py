from test.test_states import load_states_sorted
from pathlib import Path
import json
from collections import defaultdict
import sys
from datetime import datetime, timedelta, date

# Add parent directory to path to import daily_points_v2
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.daily_points_v2 import DailyPointsProcessor, POINTS_PER_PILOT_VAULT_TOKEN, POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT
from src.utils.process_event_above_user_state import UserState
from src.utils.get_points_data import UserLpSnapshot, LpProgram

DATA_DIR = Path("data")
LP_PROGRAM_DURATION_DAYS = 90  # test constant matching lp_snapshot.json


def make_lp_snapshot(entries):
    """entries: dict[address, list of (balance, lp_start_date, lp_program_duration_days)]"""
    return {
        addr: UserLpSnapshot([LpProgram(b, d, dur) for b, d, dur in programs])
        for addr, programs in entries.items()
    }


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
        points_per_one_wei = (point["end_block"] - point["start_block"] + 1) * POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT
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
            user_balance_before * POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT * (event_block_number - state["start_block"])
        )
        expected_points += (
            (user_balance_before + balance_increase)
            * POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT
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

    def test_give_points_user_without_nft(self):
        """Test that users without NFT get POINTS_PER_PILOT_VAULT_TOKEN per token"""
        lp_snapshot = make_lp_snapshot({
            "0x1234567890123456789012345678901234567890": [(100, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        processor = DailyPointsProcessor(lp_snapshot, 0)
        
        user_state = {
            "0x1234567890123456789012345678901234567890": UserState(balance=500, nft_ids=set())
        }
        user_state["0x1234567890123456789012345678901234567890"].last_positive_balance_update_day = "2026-01-01"
        points = defaultdict(int)
        test_date = "2026-01-15"  # Within 90 days, so should subtract snapshot
        
        result = processor.give_points_for_user_state(user_state, points, test_date)
        
        balance_excluding_snapshot = max(0, 500 - 100)  # 400
        expected_points = balance_excluding_snapshot * POINTS_PER_PILOT_VAULT_TOKEN  # 400 * 1500 = 600000
        
        assert result["0x1234567890123456789012345678901234567890"] == expected_points
        assert result["0x1234567890123456789012345678901234567890"] == 600000

    def test_give_points_user_with_nft(self):
        """Test that users with NFT get POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT per token"""
        lp_snapshot = make_lp_snapshot({
            "0xABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD": [(200, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        processor = DailyPointsProcessor(lp_snapshot, 0)
        
        user_state = {
            "0xABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD": UserState(balance=1000, nft_ids={1, 2, 3})
        }
        user_state["0xABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD"].last_positive_balance_update_day = "2026-01-01"
        points = defaultdict(int)
        test_date = "2026-01-15"  # Within 90 days, so should subtract snapshot
        
        result = processor.give_points_for_user_state(user_state, points, test_date)
        
        balance_excluding_snapshot = max(0, 1000 - 200)  # 800
        expected_points = balance_excluding_snapshot * POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT  # 800 * 1420 * 1.5 = 1704000
        
        assert result["0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"] == expected_points
        assert result["0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"] == 1704000

    def test_give_points_balance_excluding_snapshot(self):
        """Test that balance_excluding_snapshot correctly subtracts snapshot balance"""
        lp_snapshot = make_lp_snapshot({
            "0x1111111111111111111111111111111111111111": [(1000, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        processor = DailyPointsProcessor(lp_snapshot, 0)
        
        user_state = {
            "0x1111111111111111111111111111111111111111": UserState(balance=500, nft_ids=set())
        }
        user_state["0x1111111111111111111111111111111111111111"].last_positive_balance_update_day = "2026-01-01"
        points = defaultdict(int)
        test_date = "2026-01-15"  # Within 90 days, so should subtract snapshot
        
        result = processor.give_points_for_user_state(user_state, points, test_date)
        
        # balance_excluding_snapshot should be max(0, 500 - 1000) = 0
        assert result["0x1111111111111111111111111111111111111111"] == 0

    def test_give_points_address_lowercasing(self):
        """Test that addresses are properly lowercased"""
        lp_snapshot = make_lp_snapshot({
            "0xABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD": [(0, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        processor = DailyPointsProcessor(lp_snapshot, 0)
        
        user_state = {
            "0xABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD": UserState(balance=100, nft_ids=set())
        }
        user_state["0xABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD"].last_positive_balance_update_day = "2026-01-01"
        points = defaultdict(int)
        test_date = "2026-01-15"  # Within 90 days, so should subtract snapshot
        
        result = processor.give_points_for_user_state(user_state, points, test_date)
        
        # Should use lowercase address as key
        assert "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd" in result
        assert "0xABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD" not in result
        assert result["0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"] == 100 * POINTS_PER_PILOT_VAULT_TOKEN

    def test_give_points_points_accumulation(self):
        """Test that points are accumulated (added to existing points)"""
        lp_snapshot = make_lp_snapshot({
            "0x2222222222222222222222222222222222222222": [(0, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        processor = DailyPointsProcessor(lp_snapshot, 0)
        
        user_state = {
            "0x2222222222222222222222222222222222222222": UserState(balance=100, nft_ids=set())
        }
        user_state["0x2222222222222222222222222222222222222222"].last_positive_balance_update_day = "2026-01-01"
        points = defaultdict(int)
        points["0x2222222222222222222222222222222222222222"] = 5000  # Existing points
        test_date = "2026-01-15"  # Within 90 days, so should subtract snapshot
        
        result = processor.give_points_for_user_state(user_state, points, test_date)
        
        expected_new_points = 100 * POINTS_PER_PILOT_VAULT_TOKEN  # 150000
        assert result["0x2222222222222222222222222222222222222222"] == 5000 + expected_new_points
        assert result["0x2222222222222222222222222222222222222222"] == 155000

    def test_give_points_multiple_users(self):
        """Test that multiple users are handled correctly"""
        lp_snapshot = make_lp_snapshot({
            "0x1111111111111111111111111111111111111111": [(100, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
            "0x2222222222222222222222222222222222222222": [(200, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        processor = DailyPointsProcessor(lp_snapshot, 0)
        
        user_state = {
            "0x1111111111111111111111111111111111111111": UserState(balance=500, nft_ids=set()),
            "0x2222222222222222222222222222222222222222": UserState(balance=1000, nft_ids={1}),
        }
        user_state["0x1111111111111111111111111111111111111111"].last_positive_balance_update_day = "2026-01-01"
        user_state["0x2222222222222222222222222222222222222222"].last_positive_balance_update_day = "2026-01-01"
        points = defaultdict(int)
        test_date = "2026-01-15"  # Within 90 days, so should subtract snapshot
        
        result = processor.give_points_for_user_state(user_state, points, test_date)
        
        # User 1: no NFT, balance_excluding_snapshot = 500 - 100 = 400
        assert result["0x1111111111111111111111111111111111111111"] == 400 * POINTS_PER_PILOT_VAULT_TOKEN
        
        # User 2: with NFT, balance_excluding_snapshot = 1000 - 200 = 800
        assert result["0x2222222222222222222222222222222222222222"] == 800 * POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT

    def test_give_points_zero_balance_excluding_snapshot(self):
        """Test that zero balance_excluding_snapshot results in zero points"""
        lp_snapshot = make_lp_snapshot({
            "0x3333333333333333333333333333333333333333": [(500, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        processor = DailyPointsProcessor(lp_snapshot, 0)
        
        user_state = {
            "0x3333333333333333333333333333333333333333": UserState(balance=500, nft_ids=set())
        }
        user_state["0x3333333333333333333333333333333333333333"].last_positive_balance_update_day = "2026-01-01"
        points = defaultdict(int)
        test_date = "2026-01-15"  # Within 90 days, so should subtract snapshot
        
        result = processor.give_points_for_user_state(user_state, points, test_date)
        
        # balance_excluding_snapshot = max(0, 500 - 500) = 0
        assert result["0x3333333333333333333333333333333333333333"] == 0

    def test_give_points_empty_nft_set(self):
        """Test that empty NFT set is treated as no NFT"""
        lp_snapshot = make_lp_snapshot({
            "0x4444444444444444444444444444444444444444": [(0, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        processor = DailyPointsProcessor(lp_snapshot, 0)
        
        user_state = {
            "0x4444444444444444444444444444444444444444": UserState(balance=100, nft_ids=set())
        }
        user_state["0x4444444444444444444444444444444444444444"].last_positive_balance_update_day = "2026-01-01"
        points = defaultdict(int)
        test_date = "2026-01-15"  # Within 90 days, so should subtract snapshot
        
        result = processor.give_points_for_user_state(user_state, points, test_date)
        
        # Empty set should use POINTS_PER_PILOT_VAULT_TOKEN (not FOR_NFT)
        assert result["0x4444444444444444444444444444444444444444"] == 100 * POINTS_PER_PILOT_VAULT_TOKEN

    def test_give_points_unlocked_rewards_without_nft(self):
        """Test that rewards are unlocked (full balance used) when date > last_positive_balance_update_day + 90 days"""
        lp_snapshot = make_lp_snapshot({
            "0x5555555555555555555555555555555555555555": [(200, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        processor = DailyPointsProcessor(lp_snapshot, 0)
        
        user_state = {
            "0x5555555555555555555555555555555555555555": UserState(balance=500, nft_ids=set())
        }
        # Set date 100 days after LP start so program is outside duration
        last_update_date = date(2026, 1, 1)
        current_date = last_update_date + timedelta(days=LP_PROGRAM_DURATION_DAYS + 10)  # 100 days later
        user_state["0x5555555555555555555555555555555555555555"].last_positive_balance_update_day = str(last_update_date)
        points = defaultdict(int)
        test_date = str(current_date)
        
        result = processor.give_points_for_user_state(user_state, points, test_date)
        
        # Should use full balance (500), not subtract snapshot (200)
        expected_points = 500 * POINTS_PER_PILOT_VAULT_TOKEN  # 750000
        assert result["0x5555555555555555555555555555555555555555"] == expected_points
        assert result["0x5555555555555555555555555555555555555555"] == 750000

    def test_give_points_unlocked_rewards_with_nft(self):
        """Test that rewards are unlocked (full balance used) when date > last_positive_balance_update_day + 90 days for users with NFT"""
        lp_snapshot = make_lp_snapshot({
            "0x6666666666666666666666666666666666666666": [(300, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        processor = DailyPointsProcessor(lp_snapshot, 0)
        
        user_state = {
            "0x6666666666666666666666666666666666666666": UserState(balance=1000, nft_ids={1, 2})
        }
        # Set date 100 days after LP start so program is outside duration
        last_update_date = date(2026, 1, 1)
        current_date = last_update_date + timedelta(days=LP_PROGRAM_DURATION_DAYS + 10)  # 100 days later
        user_state["0x6666666666666666666666666666666666666666"].last_positive_balance_update_day = str(last_update_date)
        points = defaultdict(int)
        test_date = str(current_date)
        
        result = processor.give_points_for_user_state(user_state, points, test_date)
        
        # Should use full balance (1000), not subtract snapshot (300)
        expected_points = 1000 * POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT  # 2130000
        assert result["0x6666666666666666666666666666666666666666"] == expected_points
        assert result["0x6666666666666666666666666666666666666666"] == 2130000

    def test_give_points_not_unlocked_within_90_days(self):
        """Test that rewards are NOT unlocked when date <= last_positive_balance_update_day + 90 days"""
        lp_snapshot = make_lp_snapshot({
            "0x7777777777777777777777777777777777777777": [(200, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        processor = DailyPointsProcessor(lp_snapshot, 0)
        
        user_state = {
            "0x7777777777777777777777777777777777777777": UserState(balance=500, nft_ids=set())
        }
        # Set date 50 days after LP start (within 90 day period)
        last_update_date = date(2026, 1, 1)
        current_date = last_update_date + timedelta(days=50)  # 50 days later
        user_state["0x7777777777777777777777777777777777777777"].last_positive_balance_update_day = str(last_update_date)
        points = defaultdict(int)
        test_date = str(current_date)
        
        result = processor.give_points_for_user_state(user_state, points, test_date)
        
        # Should subtract snapshot: max(0, 500 - 200) = 300
        expected_points = 300 * POINTS_PER_PILOT_VAULT_TOKEN  # 450000
        assert result["0x7777777777777777777777777777777777777777"] == expected_points
        assert result["0x7777777777777777777777777777777777777777"] == 450000

    def test_give_points_unlocked_exactly_90_days(self):
        """Test that rewards are NOT unlocked exactly at 90 days (must be > 90 days)"""
        lp_snapshot = make_lp_snapshot({
            "0x8888888888888888888888888888888888888888": [(100, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        processor = DailyPointsProcessor(lp_snapshot, 0)
        
        user_state = {
            "0x8888888888888888888888888888888888888888": UserState(balance=500, nft_ids=set())
        }
        # Set date exactly 90 days after LP start (still within duration)
        last_update_date = date(2026, 1, 1)
        current_date = last_update_date + timedelta(days=LP_PROGRAM_DURATION_DAYS)  # Exactly 90 days later
        user_state["0x8888888888888888888888888888888888888888"].last_positive_balance_update_day = str(last_update_date)
        points = defaultdict(int)
        test_date = str(current_date)
        
        result = processor.give_points_for_user_state(user_state, points, test_date)
        
        # Should still subtract snapshot since date is not > 90 days: max(0, 500 - 100) = 400
        expected_points = 400 * POINTS_PER_PILOT_VAULT_TOKEN  # 600000
        assert result["0x8888888888888888888888888888888888888888"] == expected_points
        assert result["0x8888888888888888888888888888888888888888"] == 600000

    def test_give_points_180_day_duration(self):
        """Test that LP program with 180-day duration correctly excludes balance at day 100"""
        LP_180_DAYS = 180
        lp_snapshot = make_lp_snapshot({
            "0x9999999999999999999999999999999999999999": [(200, date(2026, 1, 1), LP_180_DAYS)],
        })
        processor = DailyPointsProcessor(lp_snapshot, 0)
        
        user_state = {
            "0x9999999999999999999999999999999999999999": UserState(balance=500, nft_ids=set())
        }
        # Set date 100 days after LP start (within 180-day duration, but would be outside 90-day duration)
        last_update_date = date(2026, 1, 1)
        current_date = last_update_date + timedelta(days=100)  # 100 days later
        user_state["0x9999999999999999999999999999999999999999"].last_positive_balance_update_day = str(last_update_date)
        points = defaultdict(int)
        test_date = str(current_date)
        
        result = processor.give_points_for_user_state(user_state, points, test_date)
        
        # Should subtract snapshot since date is within 180-day duration: max(0, 500 - 200) = 300
        expected_points = 300 * POINTS_PER_PILOT_VAULT_TOKEN  # 450000
        assert result["0x9999999999999999999999999999999999999999"] == expected_points
        assert result["0x9999999999999999999999999999999999999999"] == 450000

    def test_give_points_180_day_duration_unlocked(self):
        """Test that LP program with 180-day duration unlocks after 180 days"""
        LP_180_DAYS = 180
        lp_snapshot = make_lp_snapshot({
            "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA": [(150, date(2026, 1, 1), LP_180_DAYS)],
        })
        processor = DailyPointsProcessor(lp_snapshot, 0)
        
        user_state = {
            "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA": UserState(balance=600, nft_ids=set())
        }
        # Set date 190 days after LP start (outside 180-day duration)
        last_update_date = date(2026, 1, 1)
        current_date = last_update_date + timedelta(days=190)  # 190 days later
        user_state["0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"].last_positive_balance_update_day = str(last_update_date)
        points = defaultdict(int)
        test_date = str(current_date)
        
        result = processor.give_points_for_user_state(user_state, points, test_date)
        
        # Should use full balance (600), not subtract snapshot (150) since outside 180-day duration
        expected_points = 600 * POINTS_PER_PILOT_VAULT_TOKEN  # 900000
        assert result["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"] == expected_points
        assert result["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"] == 900000
