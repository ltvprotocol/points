import json
import os
from web3 import Web3
import pytest
from dotenv import load_dotenv


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
    get_user_data_from_state: callable,
    get_onchain_data: callable,
    validate_data: callable,
):
    load_dotenv()
    rpc_url = os.getenv("RPC_URL")
    if not rpc_url:
        raise ValueError("RPC_URL not found in .env file")
    addresses = load_contract_addresses()

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        pytest.skip("Cannot connect to RPC, check .env file")

    for _ in range(tests_amount):
        state_file = get_state_file()

        with open(state_file, "r") as f:
            state_data = json.load(f)

        # Pick a random user from nft.end_state
        user_data = get_user_data_from_state(state_data)

        if user_data is None:
            pytest.skip(
                f"No users found in {test_type} test for day {state_data['day_index']}"
            )

        onchain_data = get_onchain_data(w3, state_data, user_data, addresses)

        # Pass w3 and addresses to validate_data for cases where additional contract calls are needed
        validate_data(user_data, onchain_data, state_data, w3, addresses)
