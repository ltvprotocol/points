from web3 import Web3
from collections import defaultdict
from typing import Optional
import threading

w3_instances = [
    Web3(Web3.HTTPProvider("https://mainnet.gateway.tenderly.co")),
    Web3(Web3.HTTPProvider("https://ethereum-rpc.publicnode.com")),
    Web3(Web3.HTTPProvider("https://eth.drpc.org")),
]

class RequestResult:
    def __init__(self, result, error):
        self.result = result
        self.error: Optional[Exception] = error

    def __eq__(self, other):
        if not isinstance(other, RequestResult):
            return False
        # Deep comparison for dicts and lists, normal for primitives
        if type(self.result) != type(other.result):
            return False
        # Compare content, not just address, via recursive structural equality for dicts/lists
        def deep_equal(a, b):
            if isinstance(a, dict) and isinstance(b, dict):
                if set(a.keys()) != set(b.keys()):
                    return False
                for k in a:
                    if not deep_equal(a[k], b[k]):
                        return False
                return True
            elif isinstance(a, list) and isinstance(b, list):
                if len(a) != len(b):
                    return False
                for x, y in zip(a, b):
                    if not deep_equal(x, y):
                        return False
                return True
            else:
                return a == b

        if not deep_equal(self.result, other.result):
            return False
        return self.error == other.error

    def __hash__(self):
        def deep_hash(obj):
            if isinstance(obj, dict):
                # Hash based only on its content, independent of order
                return hash(frozenset((k, deep_hash(v)) for k, v in obj.items()))
            elif isinstance(obj, list):
                # Hash based on the hashes of its items
                return hash(tuple(deep_hash(x) for x in obj))
            else:
                return hash(obj)
        result_hash = deep_hash(self.result)
        error_hash = hash(self.error)
        return hash((result_hash, error_hash))

def create_contract_instances(w3_instances, address, abi):
    contract_instances = []
    address = Web3.to_checksum_address(address)
    for w3_instance in w3_instances:
        contract_instances.append(w3_instance.eth.contract(address=address, abi=abi))
    return contract_instances

def return_result_or_raise(result_to_amount: dict[RequestResult, int]):
    results_length = len(result_to_amount)
    acceptable_amount = results_length // 2 + results_length % 2
    for result, amount in result_to_amount.items():
        if amount >= acceptable_amount:
            if result.error is not None:
                raise result.error
            return result.result
    
    raise ValueError(f"No result found, results: {result_to_amount}")

def make_call(i, results, instance, function):
    try:
        result = function(instance)
        results[i] = RequestResult(result, None)
    except Exception as e:
        results[i] = RequestResult(None, e)

def make_aggregated_call(instances, function):
    results = [None] * len(instances)
    results_amount = defaultdict(lambda: 0)
    
    threads = [threading.Thread(target=make_call, args=(i, results, instance, function)) for i, instance in enumerate(instances)]
    for thread in threads:
        thread.start()
    for i, thread in enumerate(threads):
        thread.join()
        results_amount[results[i]] += 1
    return return_result_or_raise(results_amount)
