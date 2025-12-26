import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from web3 import Web3
from src.utils.get_rpc import get_rpc

DATA_DIR = Path(__file__).parent.parent / "data"
STATES_DIR = DATA_DIR / "states"


def load_states_sorted():
    files = sorted(STATES_DIR.glob("*.json"), key=lambda f: int(f.stem))
    return [json.loads(f.read_text()) for f in files]


class TestStates:
    """Each file's date is exactly one day after previous file's date"""

    def test_consecutive_days(self):
        states = load_states_sorted()
        for prev, curr in zip(states, states[1:]):
            prev_date = datetime.fromisoformat(prev["date"])
            curr_date = datetime.fromisoformat(curr["date"])
            assert curr_date - prev_date == timedelta(
                days=1
            ), f"Day {prev['day_index']} -> {curr['day_index']} gap != 1 day"

    def test_block_corresponds_to_day(self):
        states = load_states_sorted()
        w3 = Web3(Web3.HTTPProvider(get_rpc()))
        for state in states:
            current_day = datetime.fromisoformat(state["date"]).day
            start_block_day = self._get_block_day(w3, state["start_block"])
            end_block_day = self._get_block_day(w3, state["end_block"])

            assert (
                end_block_day == current_day
            ), f"Day {state['day_index']} end block does not correspond to day {current_day}"
            assert (
                start_block_day == current_day
            ), f"Day {state['day_index']} start block does not correspond to day {current_day}"

    def test_start_block_is_first_of_day(self):
        states = load_states_sorted()
        w3 = Web3(Web3.HTTPProvider(get_rpc()))
        for state in states[1:]:
            current_date = datetime.fromisoformat(state["date"])
            start_block_day = self._get_block_day(w3, state["start_block"] - 1)
            assert (
                start_block_day == (current_date - timedelta(days=1)).day
            ), f"Day {state['day_index']} start block is not the first of the day"

    def test_end_block_is_last_of_day(self):
        states = load_states_sorted()
        w3 = Web3(Web3.HTTPProvider(get_rpc()))
        for state in states:
            current_date = datetime.fromisoformat(state["date"])
            end_block_day = self._get_block_day(w3, state["end_block"] + 1)
            assert (
                end_block_day == (current_date + timedelta(days=1)).day
            ), f"Day {state['day_index']} end block is not the last of the day"

    def _get_block_day(self, w3, block_number):
        return datetime.fromtimestamp(
            w3.eth.get_block(block_number).timestamp, tz=timezone.utc
        ).day
