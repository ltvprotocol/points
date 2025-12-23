from collections import defaultdict
from web3 import Web3
from utils.get_rpc import get_rpc
from find_deployment_blocks import load_contract_addresses
from utils.load_events_sorted import load_events_sorted

ZERO_ADDRESS = "0x" + "0" * 40

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "baseTotalSupply",
        "outputs": [{"name": "baseTotalSupply", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
]


class TestEventsStructure:
    def test_transfer_events_structure(self):
        w3 = Web3(Web3.HTTPProvider(get_rpc()))

        events = load_events_sorted("pilot_vault")
        user_balances = defaultdict(int)
        contract = w3.eth.contract(
            address=load_contract_addresses()["pilot_vault"], abi=ERC20_ABI
        )
        prev_event_block = events[0]["blockNumber"]
        affected_users = set()
        for event in events:
            event_block = event["blockNumber"]
            self._check_transfer_balances_if_needed(
                user_balances, contract, prev_event_block, event_block, affected_users
            )
            prev_event_block = event_block

            if event["args"]["from"] != ZERO_ADDRESS:
                user_balances[event["args"]["from"].lower()] -= event["args"]["value"]
                affected_users.add(event["args"]["from"].lower())
            if event["args"]["to"] != ZERO_ADDRESS:
                user_balances[event["args"]["to"].lower()] += event["args"]["value"]
                affected_users.add(event["args"]["to"].lower())

        # full state check in the end
        self._check_transfer_balances_if_needed(
            user_balances,
            contract,
            events[-1]["blockNumber"],
            events[-1]["blockNumber"] + 1,
            set(user_balances.keys()),
        )

    def _check_transfer_balances_if_needed(
        self, user_balances, contract, prev_event_block, event_block, affected_users
    ):
        if event_block != prev_event_block:
            total_supply = contract.functions.baseTotalSupply().call(
                block_identifier=prev_event_block
            )
            for user in affected_users:
                balance = contract.functions.balanceOf(
                    Web3.to_checksum_address(user)
                ).call(block_identifier=prev_event_block)
                assert (
                    user_balances[user] == balance
                ), f"User {user} balance mismatch: {user_balances[user]} != {total_supply}"
            assert total_supply == sum(
                user_balances.values()
            ), f"Total supply mismatch: {total_supply} != {sum(user_balances.values())}"
            affected_users.clear()
