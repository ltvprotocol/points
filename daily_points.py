#!/usr/bin/env python3
import json
import os
import glob
import re
from collections import defaultdict

# Constants
POINTS_PER_PILOT_VAULT_TOKEN = 1000
POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT = (142 * 1000) // 100  # 1.42

# DECIMALS FOR POINTS = 24

def get_day_state_files():
    """Get all day state files sorted by index"""
    states_dir = "data/states"
    if not os.path.exists(states_dir):
        raise ValueError(f"Directory {states_dir} not found")
    
    pattern = os.path.join(states_dir, "*.json")
    files = glob.glob(pattern)
    
    file_data = []
    for filepath in files:
        filename = os.path.basename(filepath)
        # Skip daily_states.json if it exists
        if filename == "daily_states.json":
            continue
        match = re.match(r"^(\d+)\.json$", filename)
        if match:
            index = int(match.group(1))
            file_data.append((index, filepath))
    
    file_data.sort(key=lambda x: x[0])
    return file_data


def load_events_file(filepath):
    """Load events from a JSON file, handle errors"""
    if not os.path.exists(filepath):
        return [], None
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Check if there's an error
        if data.get("error", False):
            return [], data.get("error_message", "Unknown error")
        
        return data.get("events", []), None
    except Exception as e:
        return [], str(e)


def reconstruct_state_block_by_block(start_state, events, start_block, end_block):
    """
    Reconstruct state block by block from start_state and events.
    Returns: {block_number: state_at_block}
    """
    # Initialize state from start_state
    nft_state = defaultdict(set)
    pilot_vault_state = defaultdict(int)
    
    # Load start state
    for addr, token_ids in start_state.get("nft", {}).items():
        nft_state[addr.lower()] = set(token_ids)
    
    for addr, balance in start_state.get("pilot_vault", {}).items():
        pilot_vault_state[addr.lower()] = balance
    
    # Sort events by blockNumber, transactionIndex, logIndex
    sorted_events = sorted(events, key=lambda x: (
        x['blockNumber'],
        x.get('transactionIndex', 0),
        x.get('logIndex', 0)
    ))
    
    # Track state at each block
    block_states = {}
    current_block = None
    current_nft_state = None
    current_pilot_vault_state = None
    
    # Process events
    for event in sorted_events:
        block_num = event['blockNumber']
        
        # If we've moved to a new block, save previous block state
        if current_block is not None and block_num != current_block:
            block_states[current_block] = {
                "nft": {addr: sorted(list(token_ids)) for addr, token_ids in current_nft_state.items()},
                "pilot_vault": dict(current_pilot_vault_state)
            }
        
        # Initialize state for new block
        if block_num != current_block:
            current_block = block_num
            current_nft_state = defaultdict(set)
            current_pilot_vault_state = defaultdict(int)
            
            # Copy current state
            for addr, token_ids in nft_state.items():
                current_nft_state[addr] = set(token_ids)
            for addr, balance in pilot_vault_state.items():
                current_pilot_vault_state[addr] = balance
        
        # Process event
        args = event['args']
        from_addr = args.get('from', '').lower()
        to_addr = args.get('to', '').lower()
        
        # Check if it's NFT (has tokenId) or Pilot Vault (has value)
        if 'tokenId' in args:
            # NFT event
            token_id = args['tokenId']
            
            if from_addr and from_addr != '0x0000000000000000000000000000000000000000':
                nft_state[from_addr].discard(token_id)
                current_nft_state[from_addr].discard(token_id)
                if not nft_state[from_addr]:
                    del nft_state[from_addr]
                if not current_nft_state[from_addr]:
                    del current_nft_state[from_addr]
            
            if to_addr and to_addr != '0x0000000000000000000000000000000000000000':
                nft_state[to_addr].add(token_id)
                current_nft_state[to_addr].add(token_id)
        
        elif 'value' in args:
            # Pilot Vault event
            value = args['value']
            try:
                value_int = int(value) if isinstance(value, str) else int(value)
            except (ValueError, TypeError):
                continue
            
            if from_addr and from_addr != '0x0000000000000000000000000000000000000000':
                pilot_vault_state[from_addr] -= value_int
                current_pilot_vault_state[from_addr] -= value_int
                if pilot_vault_state[from_addr] == 0:
                    del pilot_vault_state[from_addr]
                if current_pilot_vault_state[from_addr] == 0:
                    del current_pilot_vault_state[from_addr]
            
            if to_addr and to_addr != '0x0000000000000000000000000000000000000000':
                pilot_vault_state[to_addr] += value_int
                current_pilot_vault_state[to_addr] += value_int
    
    # Save last block state
    if current_block is not None:
        block_states[current_block] = {
            "nft": {addr: sorted(list(token_ids)) for addr, token_ids in current_nft_state.items()},
            "pilot_vault": dict(current_pilot_vault_state)
        }
    
    # Fill in blocks without events (use state from previous block)
    last_state = {
        "nft": {addr: sorted(list(token_ids)) for addr, token_ids in nft_state.items()},
        "pilot_vault": dict(pilot_vault_state)
    }
    
    for block_num in range(start_block, end_block + 1):
        if block_num not in block_states:
            block_states[block_num] = last_state
        else:
            last_state = block_states[block_num]
    
    return block_states


def calculate_points_for_day(day_index):
    """Calculate points for a single day period"""
    print(f"\nProcessing day {day_index}...")
    
    # Load day state
    state_file = f"data/states/{day_index}.json"
    if not os.path.exists(state_file):
        print(f"  State file not found: {state_file}")
        return None
    
    with open(state_file, 'r') as f:
        day_state = json.load(f)
    
    start_block = day_state["start_block"]
    end_block = day_state["end_block"]
    date = day_state.get("date", "unknown")
    
    print(f"  Date: {date}")
    print(f"  Block range: {start_block} to {end_block}")
    
    # Load events
    nft_events, nft_error = load_events_file(f"data/events/nft/{day_index}.json")
    if nft_error:
        print(f"  NFT events error: {nft_error}")
    
    pilot_vault_events, pv_error = load_events_file(f"data/events/pilot_vault/{day_index}.json")
    if pv_error:
        print(f"  Pilot vault events error: {pv_error}")
    
    all_events = nft_events + pilot_vault_events
    print(f"  Total events: {len(all_events)} (NFT: {len(nft_events)}, Pilot Vault: {len(pilot_vault_events)})")
    
    # Get start state
    start_state = {
        "nft": day_state["nft"]["start_state"],
        "pilot_vault": day_state["pilot_vault"]["start_state"]
    }
    
    # Reconstruct state block by block
    print(f"  Reconstructing state block by block...")
    block_states = reconstruct_state_block_by_block(start_state, all_events, start_block, end_block)
    
    # Calculate points for each block
    print(f"  Calculating points...")
    user_points = defaultdict(int)  # {address: total_points}
    
    for block_num in range(start_block, end_block + 1):
        state = block_states.get(block_num, {
            "nft": {},
            "pilot_vault": {}
        })
        
        # Calculate points for each user
        for addr, pilot_vault_balance in state["pilot_vault"].items():
            if pilot_vault_balance <= 0:
                continue
            
            # Check if user has at least one NFT
            nft_count = len(state["nft"].get(addr, []))
            if nft_count > 0:
                # Use NFT multiplier points: 1200 * 142 / 100
                base_points = pilot_vault_balance * POINTS_PER_PILOT_VAULT_TOKEN_FOR_NFT
            else:
                # Base points: 1200 per pilot_vault token
                base_points = pilot_vault_balance * POINTS_PER_PILOT_VAULT_TOKEN
            
            user_points[addr] += base_points
    
    # Convert to regular dict and sort
    points_dict = dict(user_points)
    
    print(f"  Calculated points for {len(points_dict)} users")
    if points_dict:
        total_points = sum(points_dict.values())
        print(f"  Total points: {total_points:,.2f}")
    
    return {
        "day_index": day_index,
        "date": date,
        "start_block": start_block,
        "end_block": end_block,
        "points": points_dict
    }


def calculate_all_points():
    """Calculate points for all daily periods"""
    print("Loading day state files...")
    day_files = get_day_state_files()
    print(f"Found {len(day_files)} day periods")
    
    if not day_files:
        print("No day state files found. Exiting.")
        return
    
    # Create output directory
    output_dir = "data/points"
    os.makedirs(output_dir, exist_ok=True)
    
    # Process each day
    for day_index, _ in day_files:
        result = calculate_points_for_day(day_index)
        
        if result is None:
            continue
        
        # Save points for this day
        output_file = os.path.join(output_dir, f"{day_index}.json")
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"  Saved points to {output_file}")
    
    print(f"\nCompleted! Processed {len(day_files)} day periods")


if __name__ == "__main__":
    calculate_all_points()