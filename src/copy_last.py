import os
import shutil
from .utils.get_days_amount import get_days_amount

def copy_last_aggregated_points_file_to_latest_folder():
    if not os.path.exists("data/latest/"):
        os.makedirs("data/latest/", exist_ok=True)
    days_amount = get_days_amount()
    last_aggregated_points_file = f"{days_amount - 1}.json"
    shutil.copy(f"data/aggregated_points/{last_aggregated_points_file}", f"data/latest/today_points.json")

def copy_last_states_file_to_latest_folder():
    if not os.path.exists("data/latest/"):
        os.makedirs("data/latest/", exist_ok=True)
    days_amount = get_days_amount()
    last_states_file = f"{days_amount - 1}.json"
    shutil.copy(f"data/states/{last_states_file}", f"data/latest/today_states.json")

def copy_last():
    copy_last_aggregated_points_file_to_latest_folder()
    copy_last_states_file_to_latest_folder()

if __name__ == "__main__":
    copy_last()