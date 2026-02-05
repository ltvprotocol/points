import json
from collections import defaultdict
import os
from typing import Dict, List
from .utils.event_type import EventType
from .utils.read_combined_sorted_events import read_combined_sorted_events
from .utils.process_event_above_user_state import (
    process_event_above_user_state,
    UserState,
)
from .utils.get_days_amount import get_days_amount
from .utils.get_additional_data import (
    get_start_block_for_day,
    get_end_block_for_day,
    get_day_date,
)
from .utils.get_points_data import get_points_data, LpSnapshot
from datetime import datetime

ZERO_ADDRESS = "0x" + "0" * 40

POINTS_PER_PILOT_VAULT_TOKEN = 1500
POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT = (142 * 1500) // 100  # 1.42

type Points = int


def get_user_state(filename, state_key):
    with open(filename, "r") as f:
        state = json.load(f)

    user_state = defaultdict(UserState)
    for address, nft in state["nft"][state_key].items():
        user_state[address.lower()].nft_ids = set(nft)
    for address, state in state["pilot_vault"][state_key].items():
        user_state[address.lower()].balance = state["balance"]
        user_state[address.lower()].last_positive_balance_update_day = state[
            "last_positive_balance_update_day"
        ]
        user_state[address.lower()].last_negative_balance_update_day = state[
            "last_negative_balance_update_day"
        ]
    return user_state


def get_user_state_at_day(day_index, state_key):
    state_file = f"data/states/{day_index}.json"
    return get_user_state(state_file, state_key)


class DailyPointsProcessor:
    def __init__(
        self,
        lp_snapshot: LpSnapshot,
        points_program_start_block: int,
    ):
        self.lp_snapshot = lp_snapshot
        self.points_program_start_block = points_program_start_block

    def get_balance_excluding_snapshot(self, address, user_state, date_unparsed) -> int:
        if address not in self.lp_snapshot.keys():
            return user_state.balance

        balance_to_exclude = 0
        date = datetime.fromisoformat(date_unparsed).date()
        for program in self.lp_snapshot[address].lp_programs:
            days_since_lp_start = (date - program.lp_start_date).days
            if (
                days_since_lp_start <= program.lp_program_duration_days
                and days_since_lp_start >= 0
            ):
                balance_to_exclude += program.balance

        return max(0, user_state.balance - balance_to_exclude)

    def give_points_for_user_state(self, user_state, points, date) -> Dict[str, Points]:
        for address, user_state in user_state.items():
            balance_excluding_snapshot = self.get_balance_excluding_snapshot(
                address, user_state, date
            )
            if len(user_state.nft_ids) == 0:
                points[address.lower()] += (
                    balance_excluding_snapshot * POINTS_PER_PILOT_VAULT_TOKEN
                )
            else:
                points[address.lower()] += (
                    balance_excluding_snapshot * POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT
                )
        return points

    def get_points(self, day_index) -> Dict[str, Points]:
        start_block = get_start_block_for_day(day_index)
        end_block = get_end_block_for_day(day_index)
        block_number_to_events = read_combined_sorted_events(day_index)
        user_state = get_user_state_at_day(day_index, "start_state")
        date = get_day_date(day_index)

        points: Dict[str, Points] = defaultdict(int)

        for block_number in range(start_block, end_block + 1):
            events = block_number_to_events[block_number]
            for event in events:
                user_state = process_event_above_user_state(event, user_state, date)
            if block_number > self.points_program_start_block:
                points = self.give_points_for_user_state(user_state, points, date)

        validate_end_state(day_index, user_state)
        return points

    def process_points(self) -> List[Dict]:
        """Process points for all days and return results as a list of dictionaries."""
        days_amount = get_days_amount()
        results = []

        for day_index in range(days_amount):
            points = self.get_points(day_index)
            path = f"data/points/{day_index}.json"
            os.makedirs(os.path.dirname(path), exist_ok=True)

            points = {
                address.lower(): points
                for address, points in points.items()
                if points > 0
            }

            result = {
                "day_index": day_index,
                "date": get_day_date(day_index),
                "start_block": get_start_block_for_day(day_index),
                "end_block": get_end_block_for_day(day_index),
                "points": points,
            }

            json.dump(
                result,
                open(path, "w"),
                indent=2,
            )

            results.append(result)

        return results


def validate_end_state(day_index, result_user_balances):
    cached_user_balances = get_user_state_at_day(day_index, "end_state")

    result_user_balances_items = sorted(
        [
            [address.lower(), balance]
            for address, balance in result_user_balances.items()
            if balance.balance > 0
            or balance.last_negative_balance_update_day != ""
            or balance.last_positive_balance_update_day != ""
            or len(balance.nft_ids) > 0
        ]
    )
    cached_user_balances_items = sorted(list(cached_user_balances.items()))

    assert len(result_user_balances_items) == len(
        cached_user_balances_items
    ), f"User balances length mismatch: {len(result_user_balances_items)} != {len(cached_user_balances_items)}"

    for result_user_balance, cached_user_balance in zip(
        result_user_balances_items, cached_user_balances_items
    ):
        assert (
            result_user_balance[0].lower() == cached_user_balance[0].lower()
        ), f"User address mismatch: {result_user_balance[0]} != {cached_user_balance[0]}"
        assert (
            result_user_balance[1].balance == cached_user_balance[1].balance
        ), f"User balance mismatch: {result_user_balance[1]} != {cached_user_balance[1]}"
        assert (
            result_user_balance[1].nft_ids == cached_user_balance[1].nft_ids
        ), f"User NFT IDs mismatch: {result_user_balance[1].nft_ids} != {cached_user_balance[1].nft_ids}"
        assert (
            result_user_balance[1].last_positive_balance_update_day
            == cached_user_balance[1].last_positive_balance_update_day
        ), f"User last positive balance update day mismatch: {result_user_balance[1].last_positive_balance_update_day} != {cached_user_balance[1].last_positive_balance_update_day}"
        assert (
            result_user_balance[1].last_negative_balance_update_day
            == cached_user_balance[1].last_negative_balance_update_day
        ), f"User last negative balance update day mismatch: {result_user_balance[1].last_negative_balance_update_day} != {cached_user_balance[1].last_negative_balance_update_day}"
    print(f"Verified end state for day {day_index}")


def process_points():
    points_program_start_block, lp_snapshot = get_points_data()
    processor = DailyPointsProcessor(lp_snapshot, points_program_start_block)
    processor.process_points()


if __name__ == "__main__":
    process_points()
