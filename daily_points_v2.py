import json
from collections import defaultdict
import os
from typing import Dict, List
from utils.event_type import EventType
from utils.read_combined_sorted_events import read_combined_sorted_events
from utils.process_event_above_user_state import (
    process_event_above_user_state,
    UserState,
)
from utils.get_days_amount import get_days_amount
from utils.get_additional_data import (
    get_start_block_for_day,
    get_end_block_for_day,
    get_day_date,
)

ZERO_ADDRESS = "0x" + "0" * 40

POINTS_PER_PILOT_VAULT_TOKEN = 1000
POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT = (142 * 1000) // 100  # 1.42

lp_balances_snapshot = {}

type Points = int
    

def get_user_state(filename, state_key):
    with open(filename, "r") as f:
        state = json.load(f)

    user_state = defaultdict(UserState)
    for address, nft in state["nft"][state_key].items():
        user_state[address.lower()].nft_ids = set(nft)
    for address, state in state["pilot_vault"][state_key].items():
        user_state[address.lower()].balance = state["balance"]
        user_state[address.lower()].last_positive_balance_update_block = state[
            "last_positive_balance_update_block"
        ]
        user_state[address.lower()].last_negative_balance_update_block = state[
            "last_negative_balance_update_block"
        ]
    return user_state

def get_user_state_at_day(day_index, state_key):
    state_file = f"data/states/{day_index}.json"
    return get_user_state(state_file, state_key)


def give_points_for_user_state(user_state, points) -> Dict[str, Points]:
    for address, user_state in user_state.items():
        balance_excluding_snapshot = max(0, user_state.balance - lp_balances_snapshot[address].balance)
        if len(user_state.nft_ids) == 0:
            points[address.lower()] += balance_excluding_snapshot * POINTS_PER_PILOT_VAULT_TOKEN
        else:
            points[address.lower()] += (
                balance_excluding_snapshot * POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT
            )
    return points


def validate_end_state(day_index, result_user_balances):
    cached_user_balances = get_user_state_at_day(day_index, "end_state")

    result_user_balances_items = sorted(
        [
            [address.lower(), balance]
            for address, balance in result_user_balances.items()
            if balance.balance > 0 or len(balance.nft_ids) > 0
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
            result_user_balance[1].last_positive_balance_update_block
            == cached_user_balance[1].last_positive_balance_update_block
        ), f"User last positive balance update block mismatch: {result_user_balance[1].last_positive_balance_update_block} != {cached_user_balance[1].last_positive_balance_update_block}"
        assert (
            result_user_balance[1].last_negative_balance_update_block
            == cached_user_balance[1].last_negative_balance_update_block
        ), f"User last negative balance update block mismatch: {result_user_balance[1].last_negative_balance_update_block} != {cached_user_balance[1].last_negative_balance_update_block}"
    print(f"Verified end state for day {day_index}")


def get_points(day_index) -> Dict[str, Points]:
    start_block = get_start_block_for_day(day_index)
    end_block = get_end_block_for_day(day_index)
    block_number_to_events = read_combined_sorted_events(day_index)
    user_state = get_user_state_at_day(day_index, "start_state")

    points: Dict[str, Points] = defaultdict(int)

    for block_number in range(start_block, end_block + 1):
        events = block_number_to_events[block_number]
        for event in events:
            user_state = process_event_above_user_state(event, user_state)
        points = give_points_for_user_state(user_state, points)

    validate_end_state(day_index, user_state)
    return points


def process_points():
    days_amount = get_days_amount()
    for day_index in range(days_amount):
        points = get_points(day_index)
        path = f"data/points/{day_index}.json"
        os.makedirs(os.path.dirname(path), exist_ok=True)

        points = {
            address.lower(): points for address, points in points.items() if points > 0
        }
        json.dump(
            {
                "day_index": day_index,
                "date": get_day_date(day_index),
                "start_block": get_start_block_for_day(day_index),
                "end_block": get_end_block_for_day(day_index),
                "points": points,
            },
            open(path, "w"),
            indent=2,
        )

if __name__ == "__main__":
    lp_balances_snapshot = get_user_state("data/lp_balances_snapshot.json", "start_state")
    process_points()
