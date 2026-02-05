from collections import defaultdict
import sys
from pathlib import Path
from datetime import datetime, timedelta, date
from unittest.mock import patch

# Add parent directory to path to import modules
# sys.path.insert(0, str(Path(__file__).parent.parent))
from src.check_lp_integrity import LpIntegrityChecker
from src.utils.process_event_above_user_state import UserState
from src.utils.get_points_data import UserLpSnapshot, LpProgram

LP_PROGRAM_DURATION_DAYS = 90  # test constant matching lp_snapshot.json


def make_lp_snapshot(entries):
    """entries: dict[address, list of (balance, lp_start_date, lp_program_duration_days)]"""
    return {
        addr: UserLpSnapshot([LpProgram(b, d, dur) for b, d, dur in programs])
        for addr, programs in entries.items()
    }


class TestValidateLpIntegrity:
    def test_balance_above_snapshot_no_integrity_issue(self):
        """Test that balance above snapshot does not indicate integrity issue"""
        lp_snapshot = make_lp_snapshot({
            "0x1111111111111111111111111111111111111111": [(100, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        checker = LpIntegrityChecker(lp_snapshot, 0)

        user_state = {
            "0x1111111111111111111111111111111111111111": UserState(balance=500)
        }
        date_str = "2026-01-15"  # Within 90 days

        result = checker._validate_lp_integrity(user_state, date_str)

        assert result["0x1111111111111111111111111111111111111111"] == False  # No integrity issue

    def test_balance_below_snapshot_integrity_broken(self):
        """Test that balance below snapshot indicates integrity issue"""
        lp_snapshot = make_lp_snapshot({
            "0x2222222222222222222222222222222222222222": [(500, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        checker = LpIntegrityChecker(lp_snapshot, 0)

        user_state = {
            "0x2222222222222222222222222222222222222222": UserState(balance=300)
        }
        date_str = "2026-01-15"  # Within 90 days

        result = checker._validate_lp_integrity(user_state, date_str)

        assert result["0x2222222222222222222222222222222222222222"] == True  # Integrity broken

    def test_balance_equal_to_snapshot_no_integrity_issue(self):
        """Test that balance equal to snapshot does not indicate integrity issue"""
        lp_snapshot = make_lp_snapshot({
            "0x3333333333333333333333333333333333333333": [(300, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        checker = LpIntegrityChecker(lp_snapshot, 0)

        user_state = {
            "0x3333333333333333333333333333333333333333": UserState(balance=300)
        }
        date_str = "2026-01-15"  # Within 90 days

        result = checker._validate_lp_integrity(user_state, date_str)

        assert result["0x3333333333333333333333333333333333333333"] == False  # No integrity issue

    def test_user_outside_90_day_period_not_checked(self):
        """Test that programs outside 90-day window contribute zero to balance_to_exclude"""
        lp_snapshot = make_lp_snapshot({
            "0x4444444444444444444444444444444444444444": [(100, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        checker = LpIntegrityChecker(lp_snapshot, 0)

        user_state = {
            "0x4444444444444444444444444444444444444444": UserState(balance=50)  # Below snapshot
        }
        # Date is more than 90 days after LP start → balance_to_exclude = 0 → no integrity issue
        lp_start = date(2026, 1, 1)
        current_date = lp_start + timedelta(days=LP_PROGRAM_DURATION_DAYS + 10)
        date_str = str(current_date)

        result = checker._validate_lp_integrity(user_state, date_str)

        assert result["0x4444444444444444444444444444444444444444"] == False

    def test_user_not_in_snapshot_no_integrity_issue(self):
        """Test that user not in lp_snapshot is not flagged (result False)"""
        lp_snapshot = make_lp_snapshot({
            "0x9999999999999999999999999999999999999999": [(100, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        checker = LpIntegrityChecker(lp_snapshot, 0)

        # Different address not in snapshot
        user_state = {
            "0x5555555555555555555555555555555555555555": UserState(balance=200)
        }
        user_state["0x5555555555555555555555555555555555555555"].last_positive_balance_update_day = ""
        date_str = "2026-01-15"

        result = checker._validate_lp_integrity(user_state, date_str)

        assert result["0x5555555555555555555555555555555555555555"] == False

    def test_multiple_users_mixed_scenarios(self):
        """Test multiple users with different scenarios"""
        lp_snapshot = make_lp_snapshot({
            "0x1111111111111111111111111111111111111111": [(100, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],  # Above
            "0x2222222222222222222222222222222222222222": [(500, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],  # Below
            "0x3333333333333333333333333333333333333333": [(200, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],  # Equal
        })
        checker = LpIntegrityChecker(lp_snapshot, 0)

        user_state = {
            "0x1111111111111111111111111111111111111111": UserState(balance=300),  # Above
            "0x2222222222222222222222222222222222222222": UserState(balance=400),  # Below
            "0x3333333333333333333333333333333333333333": UserState(balance=200),  # Equal
        }
        date_str = "2026-01-15"

        result = checker._validate_lp_integrity(user_state, date_str)

        assert result["0x1111111111111111111111111111111111111111"] == False  # No issue
        assert result["0x2222222222222222222222222222222222222222"] == True   # Integrity broken
        assert result["0x3333333333333333333333333333333333333333"] == False  # No issue

    def test_address_matching(self):
        """Test that addresses must match exactly between snapshot and user state"""
        address = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        lp_snapshot = make_lp_snapshot({
            address: [(100, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS)],
        })
        checker = LpIntegrityChecker(lp_snapshot, 0)

        user_state = {
            address: UserState(balance=50)  # Below snapshot
        }
        date_str = "2026-01-15"

        result = checker._validate_lp_integrity(user_state, date_str)

        assert result[address] == True

    def test_multiple_programs_same_user(self):
        """Test user with multiple LP programs: balance_to_exclude is sum of active programs"""
        # One program 100 (active), one 200 (active) → balance_to_exclude = 300
        lp_snapshot = make_lp_snapshot({
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": [
                (100, date(2026, 1, 1), LP_PROGRAM_DURATION_DAYS),
                (200, date(2026, 1, 10), LP_PROGRAM_DURATION_DAYS),
            ],
        })
        checker = LpIntegrityChecker(lp_snapshot, 0)

        user_state = {
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": UserState(balance=250)  # Below 300
        }
        date_str = "2026-01-15"  # Both programs within 90 days

        result = checker._validate_lp_integrity(user_state, date_str)

        assert result["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"] == True  # 250 < 300

    def test_180_day_duration_program(self):
        """Test that LP program with 180-day duration correctly validates integrity"""
        LP_180_DAYS = 180
        lp_snapshot = make_lp_snapshot({
            "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb": [(400, date(2026, 1, 1), LP_180_DAYS)],
        })
        checker = LpIntegrityChecker(lp_snapshot, 0)

        user_state = {
            "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb": UserState(balance=300)  # Below snapshot
        }
        # Date is 100 days after LP start (within 180-day duration, but outside 90-day duration)
        lp_start = date(2026, 1, 1)
        current_date = lp_start + timedelta(days=100)
        date_str = str(current_date)

        result = checker._validate_lp_integrity(user_state, date_str)

        # Should flag integrity issue since 300 < 400 and program is still active (within 180 days)
        assert result["0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"] == True  # Integrity broken

    def test_180_day_duration_program_unlocked(self):
        """Test that LP program with 180-day duration doesn't check integrity after 180 days"""
        LP_180_DAYS = 180
        lp_snapshot = make_lp_snapshot({
            "0xcccccccccccccccccccccccccccccccccccccccc": [(500, date(2026, 1, 1), LP_180_DAYS)],
        })
        checker = LpIntegrityChecker(lp_snapshot, 0)

        user_state = {
            "0xcccccccccccccccccccccccccccccccccccccccc": UserState(balance=200)  # Below snapshot
        }
        # Date is 190 days after LP start (outside 180-day duration)
        lp_start = date(2026, 1, 1)
        current_date = lp_start + timedelta(days=190)
        date_str = str(current_date)

        result = checker._validate_lp_integrity(user_state, date_str)

        # Should not flag integrity issue since program is outside 180-day duration
        assert result["0xcccccccccccccccccccccccccccccccccccccccc"] == False  # No integrity issue