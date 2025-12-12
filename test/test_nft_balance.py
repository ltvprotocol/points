#!/usr/bin/env python3
import json
import random
import glob
from web3 import Web3
from utils.compare_state_and_onchain_data import compare_state_and_onchain_data

USER_BALANCE_TESTS_AMOUNT = 10

use_state_file = ["52.json"]
use_state_file_index = 0

use_users = ["0xeb1050ec6160fcf3db72b2adcd950993a23e48b3"]
picked_users_amount = 0

# ERC721 ABI for balanceOf and ownerOf functions
ERC721_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_tokenId", "type": "uint256"}],
        "name": "ownerOf",
        "outputs": [{"name": "owner", "type": "address"}],
        "type": "function",
    },
]


def state_file_has_nft_users(state_file):
    """Check if a state file has users in nft.end_state"""
    try:
        with open(state_file, "r") as f:
            state_data = json.load(f)
        nft_end_state = state_data.get("nft", {}).get("end_state", {})
        return bool(nft_end_state)
    except Exception:
        return False


def get_random_nft_state_file():
    """Pick a random state file from data/states directory that has NFT users"""
    global use_state_file_index
    state_files = glob.glob("data/states/*.json")
    if not state_files:
        raise ValueError("No state files found in data/states directory")

    if use_state_file_index < len(use_state_file):
        state_file = use_state_file[use_state_file_index]
        use_state_file_index += 1
        return "data/states/" + state_file
    # Filter to only files with NFT users
    files_with_nft_users = [f for f in state_files if state_file_has_nft_users(f)]

    if not files_with_nft_users:
        raise ValueError("No state files found with users in nft.end_state")

    return random.choice(files_with_nft_users)


def get_random_nft_user_from_state(state_data):
    """Pick a random user from nft.end_state and return user address and token IDs"""
    global picked_users_amount
    nft_end_state = state_data.get("nft", {}).get("end_state", {})
    if not nft_end_state:
        return None
    if picked_users_amount < len(use_users):
        user_address = use_users[picked_users_amount]
        picked_users_amount += 1
    else:
        user_address = random.choice(list(nft_end_state.keys()))
    token_ids = nft_end_state[user_address]
    # Return user address, token count (balance), and list of token IDs
    return {"user_address": Web3.to_checksum_address(user_address), "token_ids": token_ids}


def get_onchain_data(w3, state_data, user_data, addresses):
    """Get NFT balance from contract using balanceOf at specific block"""
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(addresses["nft"]), abi=ERC721_ABI
    )
    balance = contract.functions.balanceOf(Web3.to_checksum_address(user_data["user_address"])).call(
        block_identifier=state_data["end_block"]
    )

    owners = []
    for token_id in user_data["token_ids"]:
        owner = contract.functions.ownerOf(token_id).call(
            block_identifier=state_data["end_block"]
        )
        owner_checksum = Web3.to_checksum_address(owner)
        owners.append(owner_checksum)
    
    return {"balance": balance, "owners": owners}


def verify_nft_ownership(token_id, stored_owner, onchain_owner, state_data):
    """Verify that each token ID in state file belongs to the user using ownerOf"""
    assert stored_owner == onchain_owner, (
        f"NFT ownership mismatch for token {token_id} at block {state_data['end_block']} (day {state_data['day_index']}):\n"
        f"  Stored owner: {stored_owner}\n"
        f"  On-chain owner: {onchain_owner}\n"
    )


def validate_nft_balance_and_ownership(user_data, onchain_data, state_data, w3, addresses):
    """Validate both NFT balance and ownership"""
    # user_data format: (user_address, stored_balance_count, token_ids_list)
    # onchain_data: balance from balanceOf
    
    # First check balance
    assert len(user_data["token_ids"]) == onchain_data["balance"], (
        f"NFT balance mismatch for user {user_data["user_address"]} at block {state_data['end_block']} (day {state_data['day_index']}):\n"
        f"  Stored balance (token count): {len(user_data["token_ids"])}\n"
        f"  On-chain balance: {onchain_data["balance"]}\n"
        f"  Difference: {abs(len(user_data["token_ids"]) - onchain_data["balance"])}"
    )
    
    for i in range(len(user_data["token_ids"])):
        verify_nft_ownership(user_data["token_ids"][i], user_data["user_address"], onchain_data["owners"][i], state_data)
    
    print(
        f"✓ Verified NFT balance and ownership for user {user_data["user_address"]} at block {state_data['end_block']} (day {state_data['day_index']}): {user_data["token_ids"]} tokens"
    )


def validate_nft_data(user_data, onchain_data, state_data, w3, addresses):
    """Validation function that handles both balance and ownership checks"""
    balance = onchain_data
    validate_nft_balance_and_ownership(user_data, balance, state_data, w3, addresses)


def test_random_nft_balance():
    """Test that random user's NFT balance matches on-chain balance and all tokens belong to the user"""
    compare_state_and_onchain_data(
        USER_BALANCE_TESTS_AMOUNT,
        "test_random_nft_balance",
        get_random_nft_state_file,
        get_random_nft_user_from_state,
        get_onchain_data,
        validate_nft_data,
    )
