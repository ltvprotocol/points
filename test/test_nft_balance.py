#!/usr/bin/env python3
import json
import random
import glob
from web3 import Web3
from utils.compare_state_and_onchain_data import compare_state_and_onchain_data
from collections import defaultdict


use_state_file = ["84.json"]

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
    {
        "constant": True,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "totalSupply", "type": "uint256"}],
        "type": "function",
    },
]


def get_nft_state_file(i):
    return "data/states/" + use_state_file[i]


def get_users_data_from_state(state_data, state_key):
    nft_state = state_data.get("nft", {}).get(state_key, {})
    return nft_state


def get_onchain_data(w3, state_data, users_data, addresses, block_key):
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(addresses["nft"]), abi=ERC721_ABI
    )
    block = state_data[block_key] if block_key == "end_block" else state_data[block_key] - 1
    total_supply = contract.functions.totalSupply().call(
        block_identifier=block
    )

    nft_owners = defaultdict(list)

    for i in range(1, total_supply + 1):
        nft_owner = (
            contract.functions.ownerOf(i)
            .call(block_identifier=block)
            .lower()
        )

        nft_owners[nft_owner].append(i)

    return nft_owners


def validate_nft_balance_and_ownership(
    users_data, onchain_data, state_data, w3, addresses
):
    users_data_items = sorted(list(users_data.items()))
    onchain_data_items = sorted(list(onchain_data.items()))
    assert len(users_data_items) == len(
        onchain_data_items
    ), "Users data and onchain data length mismatch"
    for user_data, onchain_data in zip(users_data_items, onchain_data_items):
        assert (
            user_data[0] == onchain_data[0]
        ), "User data and onchain data user address mismatch"
        assert set(user_data[1]).intersection(onchain_data[1]) == set(
            user_data[1]
        ).union(onchain_data[1]), "User data and onchain data nft ids mismatch"


def validate_nft_data(user_data, onchain_data, state_data, w3, addresses):
    balance = onchain_data
    validate_nft_balance_and_ownership(user_data, balance, state_data, w3, addresses)


def test_nft_balance_end_state():
    compare_state_and_onchain_data(
        len(use_state_file),
        "test_random_nft_balance",
        get_nft_state_file,
        lambda *args: get_users_data_from_state(*args, "end_state"),
        lambda *args: get_onchain_data(*args, "end_block"),
        validate_nft_data,
    )


def test_nft_balance_start_state():
    compare_state_and_onchain_data(
        len(use_state_file),
        "test_random_nft_balance",
        get_nft_state_file,
        lambda *args: get_users_data_from_state(*args, "start_state"),
        lambda *args: get_onchain_data(*args, "start_block"),
        validate_nft_data,
    )
