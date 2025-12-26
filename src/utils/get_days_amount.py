import glob


def get_days_amount() -> int:
    return len(glob.glob("data/days_blocks/*.json"))