from collections import defaultdict
from typing import Dict, List
import json
from .event_type import EventType


def read_nft_events_as_block_number_to_array(file_path) -> Dict[int, List[dict]]:
    with open(file_path, "r") as f:
        events = json.load(f)
    block_number_to_nft_events = defaultdict(list)

    for event in events["events"]:
        event["event_type"] = EventType.NFT
        block_number_to_nft_events[event["blockNumber"]].append(event)

    for block_number, events in block_number_to_nft_events.items():
        block_number_to_nft_events[block_number] = sorted(
            events,
            key=lambda x: (x["blockNumber"], x["transactionIndex"], x["logIndex"]),
        )
    return block_number_to_nft_events
