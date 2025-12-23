from pathlib import Path
import json

DATA_DIR = Path("data")
EVENTS_DIR = DATA_DIR / "events"

def load_events_sorted(folder_name):
    events_dir = EVENTS_DIR / folder_name
    events = sorted(events_dir.glob("*.json"), key=lambda f: int(f.stem))
    events_data = [json.loads(f.read_text()) for f in events]
    events_sorted = sorted(
        [event for data in events_data for event in data["events"]],
        key=lambda x: (x["blockNumber"], x["transactionIndex"], x["logIndex"]),
    )
    return events_sorted
