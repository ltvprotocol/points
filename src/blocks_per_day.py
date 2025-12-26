#!/usr/bin/env python3
import json
import os
import glob
import re

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


def check_blocks_per_day():
    """Check and print blocks per day"""
    print("Loading day block files...")
    day_files = get_day_block_files()
    print(f"Found {len(day_files)} day periods\n")
    
    if not day_files:
        print("No day block files found. Exiting.")
        return
    
    # Load deployment blocks to get NFT deployment block
    with open("data/deployment_blocks.json", 'r') as f:
        deployment_data = json.load(f)
    
    nft_deployment = deployment_data["deployments"]["nft"]["block_number"]
    
    print(f"{'Day':<6} {'Date':<12} {'Start Block':<15} {'End Block':<15} {'Blocks':<10}")
    print("-" * 70)
    
    total_blocks = 0
    
    for day_index, day_filepath in day_files:
        with open(day_filepath, 'r') as f:
            day_data = json.load(f)
        
        day_date = day_data.get("day", "unknown")
        end_block = day_data["last_block_of_day"]["number"]
        
        # Determine start block
        if day_index == 0:
            start_block = nft_deployment
        else:
            # Get previous day's first_block_of_next_day
            prev_day_filepath = day_files[day_index - 1][1]
            with open(prev_day_filepath, 'r') as f:
                prev_day_data = json.load(f)
            start_block = prev_day_data["first_block_of_next_day"]["number"]
        
        # Calculate blocks in this day (inclusive)
        blocks_count = end_block - start_block + 1
        total_blocks += blocks_count
        
        print(f"{day_index:<6} {day_date:<12} {start_block:<15} {end_block:<15} {blocks_count:<10}")
    
    print("-" * 70)
    print(f"{'Total':<6} {'':<12} {'':<15} {'':<15} {total_blocks:<10}")
    print(f"\nAverage blocks per day: {total_blocks / len(day_files):.2f}")


if __name__ == "__main__":
    check_blocks_per_day()