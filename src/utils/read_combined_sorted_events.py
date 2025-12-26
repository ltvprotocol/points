from .read_transfer_events_as_block_number_to_array import read_transfer_events_as_block_number_to_array
from .read_nft_events_as_block_number_to_array import read_nft_events_as_block_number_to_array
from collections import defaultdict

def combine_and_sort_events(block_number_to_transfer_events, block_number_to_nft_events):
    block_number_to_events = defaultdict(list)
    for block_number, transfer_events in block_number_to_transfer_events.items():
        block_number_to_events[block_number].extend(transfer_events)
    for block_number, nft_events in block_number_to_nft_events.items():
        block_number_to_events[block_number].extend(nft_events)

    for block_number, events in block_number_to_events.items():
        block_number_to_events[block_number] = sorted(
            events,
            key=lambda x: (x["blockNumber"], x["transactionIndex"], x["logIndex"]),
        )
    return block_number_to_events


def read_combined_sorted_events(day_index):
    transfer_events_file = f"data/events/pilot_vault/{day_index}.json"
    nft_events_file = f"data/events/nft/{day_index}.json"
    block_number_to_transfer_events = read_transfer_events_as_block_number_to_array(
        transfer_events_file
    )
    block_number_to_nft_events = read_nft_events_as_block_number_to_array(
        nft_events_file
    )
    return combine_and_sort_events(block_number_to_transfer_events, block_number_to_nft_events)
