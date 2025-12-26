import json
import sys
import os
from datetime import datetime, timezone
from src.utils.aggregated_w3_request import w3_instances, make_aggregated_call
from web3 import Web3

def load_contract_addresses():
    """Load contract addresses from config.json"""
    try:
        with open('config.json', 'r') as f:
            config_data = json.load(f)
            nft_address = config_data.get('NFT_CONTRACT_ADDRESS')
            pilot_vault_address = config_data.get('PILOT_VAULT_CONTRACT_ADDRESS')
            
            if not nft_address:
                print("Error: NFT_CONTRACT_ADDRESS not found in config.json")
                sys.exit(1)
            if not pilot_vault_address:
                print("Error: PILOT_VAULT_CONTRACT_ADDRESS not found in config.json")
                sys.exit(1)
            
            return {
                'nft': Web3.to_checksum_address(nft_address),
                'pilot_vault': Web3.to_checksum_address(pilot_vault_address)
            }
    except FileNotFoundError:
        print("Error: config.json file not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in config.json: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading config.json: {e}")
        sys.exit(1)


def has_contract_code(address, block_number):
    """Check if contract has code at a specific block"""
    try:
        code = make_aggregated_call(w3_instances, lambda w3: w3.eth.get_code(address, block_number))
        return len(code) > 0
    except Exception as e:
        print(f"Warning: Error checking code at block {block_number}: {e}")
        return False


def find_deployment_block(address, start_block=0, end_block=None):
    """
    Find the deployment block of a contract using binary search.
    
    Args:
        address: Contract address
        start_block: Starting block for search (default: 0)
        end_block: Ending block for search (default: latest block)
    
    Returns:
        Block number where contract was deployed, or None if not found
    """
    if end_block is None:
        end_block = make_aggregated_call(w3_instances, lambda w3: w3.eth.block_number)
    
    print(f"  Searching for deployment block between {start_block} and {end_block}...")
    
    # First, check if contract exists at the end block
    if not has_contract_code(address, end_block):
        print(f"  Error: Contract has no code at block {end_block}. Contract may not be deployed yet.")
        return None
    
    # Binary search to find the first block where contract has code
    left = start_block
    right = end_block
    result = None
    
    while left <= right:
        mid = (left + right) // 2
        
        if has_contract_code(address, mid):
            # Contract exists at this block, search earlier
            result = mid
            right = mid - 1
        else:
            # Contract doesn't exist yet, search later
            left = mid + 1
    
    return result


def get_block_info(block_number):
    """Get block information including timestamp"""
    try:
        block = make_aggregated_call(w3_instances, lambda w3: w3.eth.get_block(block_number))
        return {
            'block_number': block_number,
            'timestamp': block.timestamp,
            'datetime': datetime.fromtimestamp(block.timestamp, tz=timezone.utc).isoformat(),
            'hash': block.hash.hex()
        }
    except Exception as e:
        print(f"Error getting block info for block {block_number}: {e}")
        return None


def main():
    print("=" * 60)
    print("Finding Contract Deployment Blocks")
    print("=" * 60)
    
    addresses = load_contract_addresses()
    print(f"   NFT Contract: {addresses['nft']}")
    print(f"   Pilot Vault Contract: {addresses['pilot_vault']}")
    
    # Initialize Web3 connection
    print("\n2. Connecting to blockchain...")
    # Get latest block
    latest_block = make_aggregated_call(w3_instances, lambda w3: w3.eth.block_number)
    print(f"   Latest block: {latest_block}")
    
    # Find deployment blocks
    results = {}
    
    print("\n3. Finding deployment blocks...")
    
    # Find NFT contract deployment block
    print(f"\n   NFT Contract ({addresses['nft']}):")
    nft_deployment_block = find_deployment_block(addresses['nft'], end_block=latest_block)
    if nft_deployment_block:
        nft_block_info = get_block_info(nft_deployment_block)
        results['nft'] = {
            'address': addresses['nft'],
            'deployment_block': nft_deployment_block,
            **nft_block_info
        }
        print(f"   ✓ Deployment block: {nft_deployment_block}")
        print(f"   ✓ Timestamp: {nft_block_info['datetime']}")
    else:
        print(f"   ✗ Could not find deployment block")
        results['nft'] = {
            'address': addresses['nft'],
            'deployment_block': None,
            'error': 'Could not find deployment block'
        }
    
    # Find Pilot Vault contract deployment block
    print(f"\n   Pilot Vault Contract ({addresses['pilot_vault']}):")
    vault_deployment_block = find_deployment_block(addresses['pilot_vault'], end_block=latest_block)
    if vault_deployment_block:
        vault_block_info = get_block_info(vault_deployment_block)
        results['pilot_vault'] = {
            'address': addresses['pilot_vault'],
            'deployment_block': vault_deployment_block,
            **vault_block_info
        }
        print(f"   ✓ Deployment block: {vault_deployment_block}")
        print(f"   ✓ Timestamp: {vault_block_info['datetime']}")
    else:
        print(f"   ✗ Could not find deployment block")
        results['pilot_vault'] = {
            'address': addresses['pilot_vault'],
            'deployment_block': None,
            'error': 'Could not find deployment block'
        }
    
    # Print summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"{'Contract':<20} {'Address':<45} {'Deployment Block':<20}")
    print("-" * 60)
    for contract_name, data in results.items():
        block_str = str(data.get('deployment_block', 'N/A'))
        address_short = data['address'][:42] + '...' if len(data['address']) > 45 else data['address']
        print(f"{contract_name:<20} {address_short:<45} {block_str:<20}")
    
    # Save results to JSON file
    output_data = {
        'deployments': results
    }
    
    # create data directory if it doesn't exist
    if not os.path.exists('data'):
        os.makedirs('data')

    output_file = 'data/deployment_blocks.json'
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    main()

