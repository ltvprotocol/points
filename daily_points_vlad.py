import json
from collections import defaultdict
from enum import Enum
import os
from typing import Dict, List


ZERO_ADDRESS = "0x" + "0" * 40

POINTS_PER_PILOT_VAULT_TOKEN = 1000
POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT = (142 * 1000) // 100  # 1.42

type Points = int


class UserBalance:
    balance: int = 0
    nft_ids: set[int] = set()


class EventType(Enum):
    TRANSFER = 0
    NFT = 1


def read_transfer_events_as_block_number_to_array(file_path) -> Dict[int, List[dict]]:
    with open(file_path, "r") as f:
        events = json.load(f)
    block_number_to_events: Dict[int, List[dict]] = defaultdict(list)

    for event in events["events"]:
        event["event_type"] = EventType.TRANSFER
        block_number_to_events[event["blockNumber"]].append(event)
    return block_number_to_events


def read_nft_events_as_block_number_to_array(file_path) -> Dict[int, List[dict]]:
    with open(file_path, "r") as f:
        events = json.load(f)
    block_number_to_nft_events = defaultdict(list)

    for event in events["events"]:
        event["event_type"] = EventType.NFT
        block_number_to_nft_events[event["blockNumber"]].append(event)
    return block_number_to_nft_events


def process_transfer_event(event, user_balances) -> Dict[str, UserBalance]:
    value = event["args"]["value"]
    from_addr = event["args"]["from"].lower()
    to_addr = event["args"]["to"].lower()
    if from_addr != ZERO_ADDRESS:
        user_balances[from_addr].balance -= value
    if to_addr != ZERO_ADDRESS:
        user_balances[to_addr].balance += value
    return user_balances


def process_nft_event(event, user_balances) -> Dict[str, UserBalance]:
    token_id = event["args"]["tokenId"]
    from_addr = event["args"]["from"].lower()
    to_addr = event["args"]["to"].lower()
    if from_addr != ZERO_ADDRESS:
        user_balances[from_addr].nft_ids.discard(token_id)
    if to_addr != ZERO_ADDRESS:
        user_balances[to_addr].nft_ids.add(token_id)
    return user_balances


def process_event(event, user_balances) -> Dict[str, UserBalance]:
    if event["event_type"] == EventType.TRANSFER:
        return process_transfer_event(event, user_balances)
    elif event["event_type"] == EventType.NFT:
        return process_nft_event(event, user_balances)
    else:
        raise ValueError(f"Invalid event type: {event['event_type']}")


def combine_events(block_number_to_transfer_events, block_number_to_nft_events):
    block_number_to_events = defaultdict(list)
    for block_number, transfer_events in block_number_to_transfer_events.items():
        block_number_to_events[block_number].extend(transfer_events)
    for block_number, nft_events in block_number_to_nft_events.items():
        block_number_to_events[block_number].extend(nft_events)

    for block_number, events in block_number_to_events.items():
        block_number_to_events[block_number] = sorted(
            events,
            key=lambda x: (x["blockNumber"], x["transactionIndex"], x["logIndex"]),
        )
    return block_number_to_events


def get_user_balance_at_day(day_index, state_key):
    state_file = f"data/states/{day_index}.json"
    with open(state_file, "r") as f:
        state = json.load(f)

    user_balances = defaultdict(UserBalance)

    for address, nft in state["nft"][state_key].items():
        user_balances[address.lower()].nft_ids = set(nft)
    for address, balance in state["pilot_vault"][state_key].items():
        user_balances[address.lower()].balance = balance

    print("=" * 100)
    print("user balances")
    for address, balance in user_balances.items():
        print(f"{address}: {balance.balance} {balance.nft_ids}")
    print("=" * 100)

    return user_balances


def get_events_at_block(day_index):
    transfer_events_file = f"data/events/pilot_vault/{day_index}.json"
    nft_events_file = f"data/events/nft/{day_index}.json"
    block_number_to_transfer_events = read_transfer_events_as_block_number_to_array(
        transfer_events_file
    )
    block_number_to_nft_events = read_nft_events_as_block_number_to_array(
        nft_events_file
    )
    return combine_events(block_number_to_transfer_events, block_number_to_nft_events)


def get_start_and_end_block_at_day(day_index):
    state_file = f"data/states/{day_index}.json"
    with open(state_file, "r") as f:
        state = json.load(f)
    return state["start_block"], state["end_block"]


def give_points_for_user_balances(user_balances, points) -> Dict[str, Points]:
    for address, user_balance in user_balances.items():
        if len(user_balance.nft_ids) == 0:
            points[address.lower()] += (
                user_balance.balance * POINTS_PER_PILOT_VAULT_TOKEN
            )
        else:
            points[address.lower()] += (
                user_balance.balance * POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT
            )
    return points


def validate_end_state(day_index, result_user_balances):
    cached_user_balances = get_user_balance_at_day(day_index, "end_state")

    # print( "=" * 100)
    # print("result user balances")
    # for address, balance in result_user_balances.items():
    #     print(f"{address}: {balance.balance} {balance.nft_ids}")
    # print( "=" * 100)
    # print("cached user balances")
    # for address, balance in cached_user_balances.items():
    #     print(f"{address}: {balance.balance} {balance.nft_ids}")
    # print( "=" * 100)

    result_user_balances_items = [
        [address, balance]
        for address, balance in result_user_balances.items()
        if balance.balance > 0 or len(balance.nft_ids) > 0
    ]
    cached_user_balances_items = list(cached_user_balances.items())

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
    print(f"Verified end state for day {day_index}")


def get_points(day_index) -> Dict[str, Points]:
    start_block, end_block = get_start_and_end_block_at_day(day_index)
    block_number_to_events = get_events_at_block(day_index)
    user_balances = get_user_balance_at_day(day_index, "start_state")

    points: Dict[str, Points] = defaultdict(int)

    block_number = start_block
    for block_number in range(start_block, end_block + 1):
        events = block_number_to_events[block_number]
        for event in events:
            user_balances = process_event(event, user_balances)
        points = give_points_for_user_balances(user_balances, points)

    validate_end_state(day_index, user_balances)
    return points


def process_points(day_index):
    points = get_points(day_index)
    path = f"data/points_2.0/{day_index}.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)

    points = {
        address.lower(): points for address, points in points.items() if points > 0
    }
    json.dump(points, open(path, "w"), indent=2)


process_points(77)
