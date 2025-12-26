import json
import os
from web3 import Web3
import pytest
from src.utils.get_rpc import get_rpc

def load_contract_addresses():
    """Load contract addresses from config.json"""
    with open("config.json", "r") as f:
        config = json.load(f)
    return {
        "pilot_vault": config.get("PILOT_VAULT_CONTRACT_ADDRESS"),
        "nft": config.get("NFT_CONTRACT_ADDRESS"),
    }


def compare_state_and_onchain_data(
    tests_amount: int,
    test_type: str,
    get_state_file: callable,
    get_users_data_from_state: callable,
    get_onchain_data: callable,
    validate_data: callable,
):
    addresses = load_contract_addresses()

    w3 = Web3(Web3.HTTPProvider(get_rpc()))
    if not w3.is_connected():
        pytest.skip("Cannot connect to RPC")

    for i in range(tests_amount):
        state_file = get_state_file(i)

        with open(state_file, "r") as f:
            state_data = json.load(f)

        # Pick a random user from nft.end_state
        users_data = get_users_data_from_state(state_data)

        if users_data is None:
            pytest.skip(
                f"No users found in {test_type} test for day {state_data['day_index']} in state file {state_file}"
            )

        onchain_data = get_onchain_data(w3, state_data, users_data, addresses)

        validate_data(users_data, onchain_data, state_data, w3, addresses)
