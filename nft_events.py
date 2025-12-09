#!/usr/bin/env python3
import json
import os
import glob
import re
from web3 import Web3
from datetime import datetime
import time

# ABI for Transfer event
TRANSFER_EVENT_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": True, "name": "tokenId", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    }
]


def load_rpc_url():
    """Load RPC URL from rpc.json"""
    with open("rpc.json", "r") as f:
        rpc_config = json.load(f)
    rpc_url = rpc_config.get("mainnet")
    if not rpc_url:
        raise ValueError("rpc_url not found in rpc.json")
    return rpc_url


def get_nft_deployment_block():
    """Get NFT block_number from deployment_blocks.json"""
    with open("data/deployment_blocks.json", "r") as f:
        deployment_data = json.load(f)
    
    nft_data = deployment_data.get("deployments", {}).get("nft")
    if not nft_data:
        raise ValueError("NFT deployment not found in deployment_blocks.json")
    
    block_number = nft_data.get("block_number")
    if block_number is None:
        raise ValueError("block_number not found for NFT in deployment_blocks.json")
    
    address = nft_data.get("address")
    return block_number, address


def get_day_block_files():
    """Get all day block files sorted by index"""
    days_blocks_dir = "data/days_blocks"
    if not os.path.exists(days_blocks_dir):
        raise ValueError(f"Directory {days_blocks_dir} not found")
    
    # Get all files matching pattern {index}_*.json
    pattern = os.path.join(days_blocks_dir, "*_*.json")
    files = glob.glob(pattern)
    
    # Extract index and sort
    file_data = []
    for filepath in files:
        filename = os.path.basename(filepath)
        match = re.match(r"^(\d+)_", filename)
        if match:
            index = int(match.group(1))
            file_data.append((index, filepath))
    
    # Sort by index
    file_data.sort(key=lambda x: x[0])
    
    return file_data


def read_events_chunked(contract, start_block, end_block, chunk_size=10000):
    """Read events in chunks to avoid RPC limits"""
    print(f"  Fetching events from block {start_block} to {end_block}...")
    
    event = getattr(contract.events, "Transfer")
    all_logs = []
    current_block = start_block
    
    while current_block <= end_block:
        chunk_end = min(current_block + chunk_size - 1, end_block)
        
        try:
            print(f"    Fetching logs from block {current_block} to {chunk_end}...")
            logs = event().get_logs(from_block=current_block, to_block=chunk_end)
            all_logs.extend(logs)
            print(f"    Found {len(logs)} events in this chunk")
            
            # Small delay to avoid rate limiting
            time.sleep(0.1)
            
        except Exception as e:
            print(f"    Error fetching logs from block {current_block} to {chunk_end}: {e}")
            # Try smaller chunk size if we get an error
            if chunk_size > 1000:
                print(f"    Retrying with smaller chunk size: {chunk_size // 2}")
                return read_events_chunked(contract, start_block, end_block, chunk_size // 2)
            else:
                print("    Skipping this chunk due to persistent error")
        
        current_block = chunk_end + 1
    
    return all_logs


def fetch_and_save_events(w3, contract, contract_address, start_block, end_block, output_file):
    """Fetch transfer events and save to JSON file"""
    try:
        logs = read_events_chunked(contract, start_block, end_block)
        if logs is None:
            logs = []
        
        print(f"  Total Transfer events: {len(logs)}")
        
        # Prepare data for JSON output
        events_data = []
        for log in logs:
            event_data = {
                "blockNumber": log.blockNumber,
                "transactionHash": log.transactionHash.hex(),
                "logIndex": log.logIndex,
                "args": dict(log.args),
                "transactionIndex": log.transactionIndex
            }
            events_data.append(event_data)
        
        # Save to JSON file
        output_data = {
            "metadata": {
                "contractAddress": contract_address,
                "eventName": "Transfer",
                "startBlock": start_block,
                "endBlock": end_block,
                "totalEvents": len(events_data),
                "exportedAt": datetime.now().isoformat()
            },
            "events": events_data
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"  Events saved to {output_file}")
        
    except Exception as e:
        print(f"  Error reading events: {e}")


def main():
    # Load RPC URL
    print("Loading RPC configuration...")
    rpc_url = load_rpc_url()
    
    # Initialize Web3 connection
    print("Connecting to blockchain...")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    is_connected = (
        w3.is_connected() if hasattr(w3, "is_connected") else w3.isConnected()
    )
    if not is_connected:
        raise RuntimeError("Cannot connect to RPC, check rpc.json")
    
    # Get NFT deployment block and address
    print("Reading deployment blocks...")
    deployment_block, nft_address = get_nft_deployment_block()
    print(f"NFT deployment block: {deployment_block}")
    print(f"NFT contract address: {nft_address}")
    
    # Get all day block files
    print("Reading day block files...")
    day_files = get_day_block_files()
    print(f"Found {len(day_files)} day block files")
    
    if not day_files:
        print("No day block files found. Exiting.")
        return
    
    # Setup contract
    print("Setting up contract...")
    contract_address = Web3.to_checksum_address(nft_address)
    contract = w3.eth.contract(address=contract_address, abi=TRANSFER_EVENT_ABI)
    
    # Create output directory
    output_dir = "data/events/nft"
    os.makedirs(output_dir, exist_ok=True)
    
    # Build ranges
    print("\nBuilding block ranges...")
    ranges = []
    
    # First range: (deployment_block, last_block_of_day from file 0)
    if day_files:
        with open(day_files[0][1], 'r') as f:
            day_data_0 = json.load(f)
        last_block_0 = day_data_0["last_block_of_day"]["number"]
        ranges.append((0, deployment_block, last_block_0))
        print(f"Range 0: blocks {deployment_block} to {last_block_0} (inclusive)")
    
    # Subsequent ranges: (first_block_of_next_day from previous file, last_block_of_day from current file)
    for i in range(len(day_files) - 1):
        # Read previous file
        with open(day_files[i][1], 'r') as f:
            prev_day_data = json.load(f)
        first_block_next = prev_day_data["first_block_of_next_day"]["number"]
        
        # Read current file
        with open(day_files[i + 1][1], 'r') as f:
            curr_day_data = json.load(f)
        last_block_curr = curr_day_data["last_block_of_day"]["number"]
        
        ranges.append((i + 1, first_block_next, last_block_curr))
        print(f"Range {i + 1}: blocks {first_block_next} to {last_block_curr} (inclusive)")
    
    # Fetch events for each range
    print(f"\nFetching transfer events for {len(ranges)} ranges...")
    for range_index, start_block, end_block in ranges:
        output_file = os.path.join(output_dir, f"{range_index}.json")
        
        # Skip if file already exists
        if os.path.exists(output_file):
            print(f"\nSkipping range {range_index}: file {output_file} already exists")
            continue
        
        print(f"\nProcessing range {range_index}: blocks {start_block} to {end_block}")
        fetch_and_save_events(w3, contract, contract_address, start_block, end_block, output_file)
    
    print(f"\nCompleted! Processed {len(ranges)} ranges.")


if __name__ == "__main__":
    main()