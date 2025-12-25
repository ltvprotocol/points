#!/usr/bin/env python3
import json
from datetime import datetime, timezone
import os
from utils.aggregated_w3_request import w3_instances, make_aggregated_call


def get_min_deployment_block():
    """Get the minimum block_number from deployment_blocks.json"""
    with open("data/deployment_blocks.json", "r") as f:
        deployment_data = json.load(f)
    
    deployments = deployment_data.get("deployments", {})
    if not deployments:
        raise ValueError("No deployments found in deployment_blocks.json")
    
    min_block = None
    for contract_name, contract_data in deployments.items():
        block_num = contract_data.get("block_number")
        if block_num is not None:
            if min_block is None or block_num < min_block:
                min_block = block_num
    
    if min_block is None:
        raise ValueError("No block_number found in deployments")
    
    return min_block


def get_block(num, cache):
    """Fetch block with simple cache."""
    if num in cache:
        return cache[num]
    blk = make_aggregated_call(w3_instances, lambda w3: w3.eth.get_block(num))
    cache[num] = blk
    return blk


def get_block_date(block):
    """Return UTC date (YYYY-MM-DD) of block timestamp."""
    return datetime.fromtimestamp(block["timestamp"], tz=timezone.utc).date()


def find_first_block_strictly_after_day(start_block, latest_block, target_day):
    """
    Binary search for the smallest block number in [start_block, latest_block]
    whose UTC date is strictly greater than target_day.
    Returns block number or None if not found.
    """
    cache = {}
    lo = start_block
    hi = latest_block + 1  # exclusive

    while lo < hi:
        mid = (lo + hi) // 2
        blk = get_block(mid, cache)
        blk_day = get_block_date(blk)

        if blk_day <= target_day:
            # still same day or earlier (shouldn’t be earlier if start_block is same day)
            lo = mid + 1
        else:
            # this block is after target_day, move left
            hi = mid

    # lo is the first index where blk_day > target_day, if it exists
    if lo > latest_block:
        return None

    # sanity check
    blk = get_block(lo, cache)
    if get_block_date(blk) > target_day:
        return lo
    return None


def main():
    latest_block = make_aggregated_call(w3_instances, lambda w3: w3.eth.block_number)
    start_block = get_min_deployment_block()

    if start_block > latest_block:
        raise ValueError(f"start-block {start_block} is greater than latest block {latest_block}")

    # Get starting block and its day
    start_blk = make_aggregated_call(w3_instances, lambda w3: w3.eth.get_block(start_block))
    start_day = get_block_date(start_blk)
    
    # Get latest block and its day
    latest_blk = make_aggregated_call(w3_instances, lambda w3: w3.eth.get_block(latest_block))
    latest_day = get_block_date(latest_blk)

    print(f"Starting from block {start_block}, day = {start_day}")
    print(f"Latest block on chain: {latest_block}, day = {latest_day}")

    # Find boundaries for every day in the range
    all_boundaries = []
    current_day = start_day
    current_search_start = start_block
    cache = {}  # Reuse cache across iterations

    while current_day <= latest_day:
        print(f"\nProcessing day: {current_day}")
        
        # Binary search for first block *after* this day
        first_after = find_first_block_strictly_after_day(
            current_search_start, latest_block, current_day
        )

        if first_after is None:
            # No next day found yet (we're at the latest day)
            # Use latest_block as the last block of current day
            last_block_same_day = latest_block
            last_blk = get_block(last_block_same_day, cache)
            
            all_boundaries.append({
                "day": str(current_day),
                "last_block_of_day": {
                    "number": last_blk["number"],
                    "timestamp": last_blk["timestamp"],
                    "utc_datetime": datetime.fromtimestamp(
                        last_blk["timestamp"], tz=timezone.utc
                    ).isoformat(),
                    "hash": last_blk["hash"].hex(),
                },
                "first_block_of_next_day": None,  # No next day yet
                "is_final_day": True,
            })
            print(f"  Last block of {current_day}: {last_block_same_day} (final day)")
            break

        last_block_same_day = first_after - 1
        last_blk = get_block(last_block_same_day, cache)
        first_next_blk = get_block(first_after, cache)
        next_day = get_block_date(first_next_blk)

        all_boundaries.append({
            "day": str(current_day),
            "last_block_of_day": {
                "number": last_blk["number"],
                "timestamp": last_blk["timestamp"],
                "utc_datetime": datetime.fromtimestamp(
                    last_blk["timestamp"], tz=timezone.utc
                ).isoformat(),
                "hash": last_blk["hash"].hex(),
            },
            "first_block_of_next_day": {
                "number": first_next_blk["number"],
                "timestamp": first_next_blk["timestamp"],
                "utc_datetime": datetime.fromtimestamp(
                    first_next_blk["timestamp"], tz=timezone.utc
                ).isoformat(),
                "hash": first_next_blk["hash"].hex(),
            },
            "is_final_day": False,
        })

        print(f"  Last block of {current_day}: {last_block_same_day}")
        print(f"  First block of {next_day}: {first_after}")

        # Move to next day
        current_day = next_day
        current_search_start = first_after


    if not os.path.exists('data'):
        os.makedirs('data')

    if not os.path.exists('data/days_blocks'):
        os.makedirs('data/days_blocks')
    
    saved_count = 0
    for index, boundary in enumerate(all_boundaries):
        if not boundary.get("is_final_day", False):
            date_str = boundary["day"]
            filename = f"data/days_blocks/{index}_{date_str}.json"
            
            with open(filename, "w") as f:
                json.dump(boundary, f, indent=2)
            
            saved_count += 1
            print(f"Saved day {index} ({date_str}) to {filename}")
    
    print(f"\nSaved {saved_count} individual day files (excluding final day)")


if __name__ == "__main__":
    main()