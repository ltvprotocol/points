#!/usr/bin/env python3
import json
import random
import glob
from web3 import Web3
from utils.compare_state_and_onchain_data import compare_state_and_onchain_data

use_state_file = ["84.json"]
use_state_file_index = 0

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    }
]

def get_state_file(i):
    return "data/states/" + use_state_file[i]


def get_users_data_from_state(state_data, state_key):
    """Pick a random user from pilot_vault.end_state"""
    pilot_vault_state = state_data.get("pilot_vault", {}).get(state_key, {})
    pilot_vault_state = {address: state["balance"] for address, state in pilot_vault_state.items()}
    return pilot_vault_state


def get_onchain_balances(w3, state_data, users_data, addresses, block_key):
    """Get balance from contract using balanceOf at specific block"""
    balances = {}
    block = state_data[block_key] if block_key == "end_block" else state_data[block_key] - 1
    for user, _ in users_data.items():
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(addresses["pilot_vault"]), abi=ERC20_ABI
        )
        balance = contract.functions.balanceOf(Web3.to_checksum_address(user)).call(
            block_identifier=block
        )
        balances[user.lower()] = balance
    return balances


def validate_balances(users_data, onchain_data, state_data, block_key):
    block = state_data[block_key] if block_key == "end_block" else state_data[block_key] - 1
    for user, balance in users_data.items():
        assert balance == onchain_data[user], (
            f"Balance mismatch for user {user} at block {block} (day {state_data['day_index']}):\n"
            f"  Stored balance: {balance}\n"
            f"  On-chain balance: {onchain_data[user]}\n"
            f"  Difference: {abs(balance - onchain_data[user])}"
        )


def test_user_balances_end_state():
    compare_state_and_onchain_data(
        len(use_state_file),
        "test_user_balances_end_state",
        get_state_file,
        lambda *args: get_users_data_from_state(*args, "end_state"),
        lambda *args: get_onchain_balances(*args, "end_block"),
        lambda users_data, onchain_data, state_data, _1, _2: validate_balances(
            users_data, onchain_data, state_data, "end_block"
        ),
    )

def test_user_balances_start_state():
    compare_state_and_onchain_data(
        len(use_state_file),
        "test_user_balances_start_state",
        get_state_file,
        lambda *args: get_users_data_from_state(*args, "start_state"),
        lambda *args: get_onchain_balances(*args, "start_block"),
        lambda users_data, onchain_data, state_data, _1, _2: validate_balances(
            users_data, onchain_data, state_data, "start_block"
        ),
    )
