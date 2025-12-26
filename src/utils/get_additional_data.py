import glob
import json

def get_days_blocks_filename(day_index: int):
    files = glob.glob(f"data/days_blocks/{day_index}_*.json")
    return files[0]


def get_start_block_for_day(day_index: int):
    if day_index == 0:
        with open("data/deployment_blocks.json", "r") as f:
            deployment_blocks = json.load(f)
        return min(
            deployment_blocks["deployments"]["nft"]["block_number"],
            deployment_blocks["deployments"]["pilot_vault"]["block_number"],
        )
    with open(get_days_blocks_filename(day_index - 1), "r") as f:
        day_block_data = json.load(f)
    return day_block_data["first_block_of_next_day"]["number"]


def get_end_block_for_day(day_index: int):
    with open(get_days_blocks_filename(day_index), "r") as f:
        day_block_data = json.load(f)
    return day_block_data["last_block_of_day"]["number"]


def get_day_date(day_index: int):
    with open(get_days_blocks_filename(day_index), "r") as f:
        day_block_data = json.load(f)
    return day_block_data["day"]
