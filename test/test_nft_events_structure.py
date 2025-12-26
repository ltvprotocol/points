from test.utils.load_events_sorted import load_events_sorted
from src.utils.get_rpc import get_rpc
from src.find_deployment_blocks import load_contract_addresses
from collections import defaultdict
from web3 import Web3

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

class TestNftEventsStructure:
    def test_nft_events_structure(self):
        w3 = Web3(Web3.HTTPProvider(get_rpc()))

        events = load_events_sorted("nft")
        token_id_to_owner = defaultdict(str)
        contract = w3.eth.contract(
            address=load_contract_addresses()["nft"], abi=ERC721_ABI
        )
        prev_event_block = events[0]["blockNumber"]
        affected_token_ids = set()
        for event in events:
            event_block = event["blockNumber"]
            self._check_token_id_to_owner_if_needed(token_id_to_owner, contract, prev_event_block, event_block, affected_token_ids)
            prev_event_block = event_block

            token_id_to_owner[event["args"]["tokenId"]] = event["args"]["to"].lower()
            affected_token_ids.add(event["args"]["tokenId"])

        # full state check in the end
        self._check_token_id_to_owner_if_needed(
            token_id_to_owner,
            contract,
            events[-1]["blockNumber"],
            events[-1]["blockNumber"] + 1,
            set(token_id_to_owner.keys()),
        )

    def _check_token_id_to_owner_if_needed(self, token_id_to_owner, contract, prev_event_block, event_block, affected_token_ids):
        if event_block != prev_event_block:
            total_supply = contract.functions.totalSupply().call(
                block_identifier=prev_event_block
            )
            for token_id in affected_token_ids:
                print("Checking token id", token_id)
                owner = contract.functions.ownerOf(token_id).call(block_identifier=prev_event_block)
                assert token_id_to_owner[token_id] == owner.lower(), f"Token {token_id} owner mismatch: {token_id_to_owner[token_id]} != {owner.lower()}"

            expected_total_supply = len(token_id_to_owner.keys())
            assert total_supply == expected_total_supply, f"Total supply mismatch: {total_supply} != {expected_total_supply}"
            affected_token_ids.clear()
