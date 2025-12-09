#!/usr/bin/env python3
import json
import os
import glob
import re
from collections import defaultdict
from decimal import Decimal

def get_day_block_files():
    """Get all day block files sorted by index"""
    days_blocks_dir = "data/days_blocks"
    if not os.path.exists(days_blocks_dir):
        raise ValueError(f"Directory {days_blocks_dir} not found")
    
    pattern = os.path.join(days_blocks_dir, "*_*.json")
    files = glob.glob(pattern)
    
    file_data = []
    for filepath in files:
        filename = os.path.basename(filepath)
        match = re.match(r"^(\d+)_", filename)
        if match:
            index = int(match.group(1))
            file_data.append((index, filepath))
    
    file_data.sort(key=lambda x: x[0])
    return file_data


def load_events_file(filepath):
    """Load events from a JSON file, handle errors"""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Check if there's an error
        if data.get("error", False):
            return None, data.get("error_message", "Unknown error")
        
        return data.get("events", []), None
    except Exception as e:
        return None, str(e)


def process_nft_events(events):
    """Process NFT Transfer events and return state changes"""
    # NFT state: {address: set of tokenIds}
    state = defaultdict(set)
    
    # Sort events by blockNumber, then transactionIndex, then logIndex
    sorted_events = sorted(events, key=lambda x: (
        x['blockNumber'],
        x.get('transactionIndex', 0),
        x.get('logIndex', 0)
    ))
    
    for event in sorted_events:
        args = event['args']
        from_addr = args.get('from', '').lower()
        to_addr = args.get('to', '').lower()
        token_id = args.get('tokenId')
        
        if token_id is None:
            continue
        
        # Remove from sender (if not zero address)
        if from_addr and from_addr != '0x0000000000000000000000000000000000000000':
            state[from_addr].discard(token_id)
            # Remove from state if empty
            if not state[from_addr]:
                del state[from_addr]
        
        # Add to receiver (if not zero address)
        if to_addr and to_addr != '0x0000000000000000000000000000000000000000':
            state[to_addr].add(token_id)
    
    # Convert sets to sorted lists for JSON serialization
    result = {}
    for addr, token_ids in state.items():
        result[addr] = sorted(list(token_ids))
    
    return result


def process_pilot_vault_events(events):
    """Process Pilot Vault Transfer events and return state changes"""
    # Pilot Vault state: {address: balance}
    state = defaultdict(int)
    
    # Sort events by blockNumber, then transactionIndex, then logIndex
    sorted_events = sorted(events, key=lambda x: (
        x['blockNumber'],
        x.get('transactionIndex', 0),
        x.get('logIndex', 0)
    ))
    
    for event in sorted_events:
        args = event['args']
        from_addr = args.get('from', '').lower()
        to_addr = args.get('to', '').lower()
        value = args.get('value')
        
        if value is None:
            continue
        
        # Convert value to int (assuming it's a string or int)
        try:
            if isinstance(value, str):
                value_int = int(value)
            else:
                value_int = int(value)
        except (ValueError, TypeError):
            continue
        
        # Subtract from sender (if not zero address)
        if from_addr and from_addr != '0x0000000000000000000000000000000000000000':
            state[from_addr] -= value_int
        
        # Add to receiver (if not zero address)
        if to_addr and to_addr != '0x0000000000000000000000000000000000000000':
            state[to_addr] += value_int
    
    # Remove zero balances
    result = {addr: balance for addr, balance in state.items() if balance != 0}
    return result


def calculate_daily_states():
    """Calculate state for every daily period"""
    print("Loading day block files...")
    day_files = get_day_block_files()
    print(f"Found {len(day_files)} day periods")
    
    if not day_files:
        print("No day block files found. Exiting.")
        return
    
    # Load deployment blocks to get contract addresses
    with open("data/deployment_blocks.json", 'r') as f:
        deployment_data = json.load(f)
    
    nft_deployment = deployment_data["deployments"]["nft"]["block_number"]
    pilot_vault_deployment = deployment_data["deployments"]["pilot_vault"]["block_number"]
    
    print(f"NFT deployment block: {nft_deployment}")
    print(f"Pilot vault deployment block: {pilot_vault_deployment}")
    
    # Initialize cumulative states
    nft_state = defaultdict(set)  # {address: set of tokenIds}
    pilot_vault_state = defaultdict(int)  # {address: balance}
    
    # Process each day period
    daily_states = []
    
    for day_index, day_filepath in day_files:
        print(f"\nProcessing day period {day_index}...")
        
        # Load day block info
        with open(day_filepath, 'r') as f:
            day_data = json.load(f)
        
        day_date = day_data.get("day", "unknown")
        print(f"  Date: {day_date}")
        
        # Determine block range for this day
        if day_index == 0:
            # First day: from NFT deployment to last block of day
            start_block = nft_deployment
            end_block = day_data["last_block_of_day"]["number"]
        else:
            # Subsequent days: from first block of next day (from previous day) to last block of current day
            prev_day_filepath = day_files[day_index - 1][1]
            with open(prev_day_filepath, 'r') as f:
                prev_day_data = json.load(f)
            start_block = prev_day_data["first_block_of_next_day"]["number"]
            end_block = day_data["last_block_of_day"]["number"]
        
        print(f"  Block range: {start_block} to {end_block}")
        
        # Capture starting state
        nft_start_state = {addr: sorted(list(token_ids)) for addr, token_ids in nft_state.items()}
        pilot_vault_start_state = dict(pilot_vault_state)
        
        # Load and process NFT events
        nft_file = f"data/events/nft/{day_index}.json"
        if os.path.exists(nft_file):
            nft_events, nft_error = load_events_file(nft_file)
            if nft_error:
                print(f"  NFT events error: {nft_error}")
            elif nft_events:
                print(f"  Processing {len(nft_events)} NFT events...")
                nft_changes = process_nft_events(nft_events)
                
                # Apply changes to cumulative state
                for addr, token_ids in nft_changes.items():
                    addr_lower = addr.lower()
                    # Remove old tokenIds for this address
                    if addr_lower in nft_state:
                        nft_state[addr_lower].clear()
                    # Add new tokenIds
                    for token_id in token_ids:
                        nft_state[addr_lower].add(token_id)
                
                # Clean up empty sets
                to_remove = [addr for addr, token_ids in nft_state.items() if not token_ids]
                for addr in to_remove:
                    del nft_state[addr]
        
        # Load and process Pilot Vault events
        pilot_vault_file = f"data/events/pilot_vault/{day_index}.json"
        if os.path.exists(pilot_vault_file):
            pilot_vault_events, pv_error = load_events_file(pilot_vault_file)
            if pv_error:
                print(f"  Pilot vault events error: {pv_error}")
            elif pilot_vault_events:
                print(f"  Processing {len(pilot_vault_events)} pilot vault events...")
                pv_changes = process_pilot_vault_events(pilot_vault_events)
                
                # Apply changes to cumulative state
                for addr, balance_change in pv_changes.items():
                    addr_lower = addr.lower()
                    pilot_vault_state[addr_lower] += balance_change
                
                # Remove zero balances
                to_remove = [addr for addr, balance in pilot_vault_state.items() if balance == 0]
                for addr in to_remove:
                    del pilot_vault_state[addr]
        
        # Capture ending state
        nft_end_state = {addr: sorted(list(token_ids)) for addr, token_ids in nft_state.items()}
        pilot_vault_end_state = dict(pilot_vault_state)
        
        # Save state for this day period
        day_state = {
            "day_index": day_index,
            "date": day_date,
            "start_block": start_block,
            "end_block": end_block,
            "nft": {
                "start_state": nft_start_state,
                "end_state": nft_end_state
            },
            "pilot_vault": {
                "start_state": pilot_vault_start_state,
                "end_state": pilot_vault_end_state
            }
        }
        
        daily_states.append(day_state)
        
        # Print summary
        nft_start_count = sum(len(tokens) for tokens in nft_start_state.values())
        nft_end_count = sum(len(tokens) for tokens in nft_end_state.values())
        pv_start_total = sum(pilot_vault_start_state.values())
        pv_end_total = sum(pilot_vault_end_state.values())

        print(f"  NFT: {nft_start_count} tokens at start, {nft_end_count} tokens at end")
        print(f"  Pilot Vault: {pv_start_total} tokens at start, {pv_end_total} tokens at end")
    
    # Save all daily states
    output_dir = "data/states"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save individual state files for each day period
    for day_state in daily_states:
        day_index = day_state["day_index"]
        output_file = os.path.join(output_dir, f"{day_index}.json")
        with open(output_file, 'w') as f:
            json.dump(day_state, f, indent=2)
        print(f"  Saved state for day {day_index} to {output_file}")

    print(f"Processed {len(daily_states)} day periods")


if __name__ == "__main__":
    calculate_daily_states()