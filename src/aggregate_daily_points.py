#!/usr/bin/env python3
import json
import os
import glob
import re
from collections import defaultdict

def get_daily_points_files():
    """Get all daily points files sorted by index"""
    points_dir = "data/points"
    if not os.path.exists(points_dir):
        raise ValueError(f"Directory {points_dir} not found")
    
    pattern = os.path.join(points_dir, "*.json")
    files = glob.glob(pattern)
    
    file_data = []
    for filepath in files:
        filename = os.path.basename(filepath)
        match = re.match(r"^(\d+)\.json$", filename)
        if match:
            index = int(match.group(1))
            file_data.append((index, filepath))
    
    file_data.sort(key=lambda x: x[0])
    return file_data


def aggregate_daily_points():
    """Aggregate points from all daily periods, saving cumulative totals"""
    print("Loading daily points files...")
    points_files = get_daily_points_files()
    print(f"Found {len(points_files)} daily points files\n")
    
    if not points_files:
        print("No daily points files found. Exiting.")
        return
    
    # Create output directory
    output_dir = "data/aggregated_points"
    os.makedirs(output_dir, exist_ok=True)
    
    # Running total of aggregated points
    cumulative_points = defaultdict(int)  # {address: cumulative_total_points}
    
    print("Aggregating points and saving cumulative totals...")
    for day_index, filepath in points_files:
        # Load daily points
        with open(filepath, 'r') as f:
            day_data = json.load(f)
        
        day_date = day_data.get("date", "unknown")
        day_points = day_data.get("points", {})
        
        # Build points structure with both day_points and cumulative_points for each user
        user_points = {}
        
        # Process users who earned points today
        for addr, points in day_points.items():
            addr_lower = addr.lower()
            cumulative_points[addr_lower] += points
            user_points[addr_lower] = {
                "day_points": points,
                "cumulative_points": cumulative_points[addr_lower]
            }
        
        # Include users who have cumulative points but didn't earn today
        for addr, cum_points in cumulative_points.items():
            if addr not in user_points:
                user_points[addr] = {
                    "day_points": 0,
                    "cumulative_points": cum_points
                }
        
        # Sort by cumulative points (descending)
        sorted_user_points = dict(sorted(
            user_points.items(), 
            key=lambda x: x[1]["cumulative_points"], 
            reverse=True
        ))
        
        # Calculate statistics
        total_users = len(sorted_user_points)
        total_points_all = sum(p["cumulative_points"] for p in sorted_user_points.values())
        day_total = sum(p["day_points"] for p in sorted_user_points.values())
        
        # Save cumulative aggregated points for this day
        output_data = {
            "day_index": day_index,
            "date": day_date,
            "start_block": day_data.get("start_block"),
            "end_block": day_data.get("end_block"),
            "metadata": {
                "days_included": day_index + 1,
                "total_users": total_users,
                "total_points_all_users": total_points_all,
                "day_points": day_total,
                "day_users_count": len(day_points)
            },
            "points": sorted_user_points
        }
        
        output_file = os.path.join(output_dir, f"{day_index}.json")
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"  Day {day_index} ({day_date}): {len(day_points)} users earned points, {day_total:,} day points | "
              f"Cumulative: {total_users} users, {total_points_all:,} total points")
    
    print(f"\nSaved cumulative aggregated points for all {len(points_files)} days")
    print(f"Output directory: {output_dir}/")
    
    # Print final statistics
    print(f"\n{'='*70}")
    print(f"Final Statistics:")
    print(f"{'='*70}")
    print(f"Total days processed: {len(points_files)}")
    print(f"Total unique users: {len(sorted_user_points)}")
    print(f"Total points (all users): {sum(p['cumulative_points'] for p in sorted_user_points.values()):,}")
    
    if sorted_user_points:
        top_10 = list(sorted_user_points.items())[:10]
        print(f"\nTop 10 users by total points:")
        for i, (addr, points_data) in enumerate(top_10, 1):
            print(f"  {i:2}. {addr}: {points_data['cumulative_points']:,} (day: {points_data['day_points']:,})")


if __name__ == "__main__":
    aggregate_daily_points()