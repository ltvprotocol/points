from collections import defaultdict
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.utils.process_event_above_user_state import (
    process_event_above_user_state,
    process_transfer_event,
    process_nft_event,
    UserState,
    ZERO_ADDRESS,
)
from src.utils.event_type import EventType


class TestProcessTransferEvent:
    def test_transfer_between_users(self):
        """Test transfer from one user to another"""
        user_state = defaultdict(UserState)
        from_addr = "0x1111111111111111111111111111111111111111"
        to_addr = "0x2222222222222222222222222222222222222222"
        
        user_state[from_addr].balance = 1000
        user_state[to_addr].balance = 500
        
        event = {
            "event_type": EventType.TRANSFER,
            "args": {
                "from": from_addr,
                "to": to_addr,
                "value": 200,
            },
            "blockNumber": 12345,
        }
        
        result = process_transfer_event(event, user_state)
        
        assert result[from_addr].balance == 800  # 1000 - 200
        assert result[to_addr].balance == 700  # 500 + 200
        assert result[from_addr].last_negative_balance_update_block == 12345
        assert result[to_addr].last_positive_balance_update_block == 12345

    def test_transfer_from_zero_address_mint(self):
        """Test transfer from zero address (minting)"""
        user_state = defaultdict(UserState)
        to_addr = "0x2222222222222222222222222222222222222222"
        
        user_state[to_addr].balance = 500
        
        event = {
            "event_type": EventType.TRANSFER,
            "args": {
                "from": ZERO_ADDRESS,
                "to": to_addr,
                "value": 300,
            },
            "blockNumber": 12346,
        }
        
        result = process_transfer_event(event, user_state)
        
        # Zero address should not be affected
        assert ZERO_ADDRESS not in result or result[ZERO_ADDRESS].balance == 0
        assert result[to_addr].balance == 800  # 500 + 300
        assert result[to_addr].last_positive_balance_update_block == 12346

    def test_transfer_to_zero_address_burn(self):
        """Test transfer to zero address (burning)"""
        user_state = defaultdict(UserState)
        from_addr = "0x1111111111111111111111111111111111111111"
        
        user_state[from_addr].balance = 1000
        
        event = {
            "event_type": EventType.TRANSFER,
            "args": {
                "from": from_addr,
                "to": ZERO_ADDRESS,
                "value": 400,
            },
            "blockNumber": 12347,
        }
        
        result = process_transfer_event(event, user_state)
        
        assert result[from_addr].balance == 600  # 1000 - 400
        assert result[from_addr].last_negative_balance_update_block == 12347
        # Zero address should not be affected
        assert ZERO_ADDRESS not in result or result[ZERO_ADDRESS].balance == 0

    def test_transfer_address_lowercasing(self):
        """Test that addresses are properly lowercased"""
        user_state = defaultdict(UserState)
        from_addr = "0xABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD"
        to_addr = "0x1234567890123456789012345678901234567890"
        
        user_state[from_addr.lower()].balance = 1000
        user_state[to_addr.lower()].balance = 500
        
        event = {
            "event_type": EventType.TRANSFER,
            "args": {
                "from": from_addr,  # Uppercase
                "to": to_addr,  # Mixed case
                "value": 200,
            },
            "blockNumber": 12348,
        }
        
        result = process_transfer_event(event, user_state)
        
        # Should use lowercase addresses
        assert result[from_addr.lower()].balance == 800
        assert result[to_addr.lower()].balance == 700

    def test_multiple_transfers_same_user(self):
        """Test multiple transfers affecting the same user"""
        user_state = defaultdict(UserState)
        user_addr = "0x1111111111111111111111111111111111111111"
        other_addr = "0x2222222222222222222222222222222222222222"
        
        user_state[user_addr].balance = 1000
        
        # First transfer: user sends 200
        event1 = {
            "event_type": EventType.TRANSFER,
            "args": {
                "from": user_addr,
                "to": other_addr,
                "value": 200,
            },
            "blockNumber": 12350,
        }
        result = process_transfer_event(event1, user_state)
        assert result[user_addr].balance == 800
        assert result[user_addr].last_negative_balance_update_block == 12350
        
        # Second transfer: user receives 100
        event2 = {
            "event_type": EventType.TRANSFER,
            "args": {
                "from": other_addr,
                "to": user_addr,
                "value": 100,
            },
            "blockNumber": 12351,
        }
        result = process_transfer_event(event2, result)
        assert result[user_addr].balance == 900  # 800 + 100
        assert result[user_addr].last_positive_balance_update_block == 12351

    def test_transfer_negative_balance_raises_error(self):
        """Test that transfer resulting in negative balance raises ValueError"""
        user_state = defaultdict(UserState)
        from_addr = "0x1111111111111111111111111111111111111111"
        to_addr = "0x2222222222222222222222222222222222222222"
        
        user_state[from_addr].balance = 100
        
        event = {
            "event_type": EventType.TRANSFER,
            "args": {
                "from": from_addr,
                "to": to_addr,
                "value": 200,  # More than balance
            },
            "blockNumber": 12352,
        }
        
        try:
            process_transfer_event(event, user_state)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Balance" in str(e) and "negative" in str(e)
            assert from_addr.lower() in str(e)


class TestProcessNftEvent:
    def test_nft_transfer_between_users(self):
        """Test NFT transfer from one user to another"""
        user_state = defaultdict(UserState)
        from_addr = "0x1111111111111111111111111111111111111111"
        to_addr = "0x2222222222222222222222222222222222222222"
        
        user_state[from_addr].nft_ids = {1, 2, 3}
        user_state[to_addr].nft_ids = {4}
        
        event = {
            "event_type": EventType.NFT,
            "args": {
                "from": from_addr,
                "to": to_addr,
                "tokenId": 2,
            },
            "blockNumber": 12352,
        }
        
        result = process_nft_event(event, user_state)
        
        assert result[from_addr].nft_ids == {1, 3}  # 2 removed
        assert result[to_addr].nft_ids == {4, 2}  # 2 added

    def test_nft_transfer_from_zero_address_mint(self):
        """Test NFT transfer from zero address (minting)"""
        user_state = defaultdict(UserState)
        to_addr = "0x2222222222222222222222222222222222222222"
        
        user_state[to_addr].nft_ids = {4}
        
        event = {
            "event_type": EventType.NFT,
            "args": {
                "from": ZERO_ADDRESS,
                "to": to_addr,
                "tokenId": 5,
            },
            "blockNumber": 12353,
        }
        
        result = process_nft_event(event, user_state)
        
        # Zero address should not be affected
        assert ZERO_ADDRESS not in result or len(result[ZERO_ADDRESS].nft_ids) == 0
        assert result[to_addr].nft_ids == {4, 5}  # 5 added

    def test_nft_transfer_address_lowercasing(self):
        """Test that addresses are properly lowercased for NFT events"""
        user_state = defaultdict(UserState)
        from_addr = "0xABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD"
        to_addr = "0x1234567890123456789012345678901234567890"
        
        user_state[from_addr.lower()].nft_ids = {1, 2}
        user_state[to_addr.lower()].nft_ids = {3}
        
        event = {
            "event_type": EventType.NFT,
            "args": {
                "from": from_addr,  # Uppercase
                "to": to_addr,  # Mixed case
                "tokenId": 1,
            },
            "blockNumber": 12355,
        }
        
        result = process_nft_event(event, user_state)
        
        # Should use lowercase addresses
        assert result[from_addr.lower()].nft_ids == {2}
        assert result[to_addr.lower()].nft_ids == {3, 1}

    def test_nft_transfer_nonexistent_token_raises_error(self):
        """Test NFT transfer when token doesn't exist in from address raises ValueError"""
        user_state = defaultdict(UserState)
        from_addr = "0x1111111111111111111111111111111111111111"
        to_addr = "0x2222222222222222222222222222222222222222"
        
        user_state[from_addr].nft_ids = {1, 2}
        user_state[to_addr].nft_ids = {3}
        
        event = {
            "event_type": EventType.NFT,
            "args": {
                "from": from_addr,
                "to": to_addr,
                "tokenId": 99,  # Doesn't exist in from_addr
            },
            "blockNumber": 12356,
        }
        
        try:
            process_nft_event(event, user_state)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Token" in str(e) and "not found" in str(e)
            assert "99" in str(e)
            assert from_addr.lower() in str(e)

    def test_nft_transfer_duplicate_token_raises_error(self):
        """Test NFT transfer when token already exists in to address raises ValueError"""
        user_state = defaultdict(UserState)
        from_addr = "0x1111111111111111111111111111111111111111"
        to_addr = "0x2222222222222222222222222222222222222222"
        
        user_state[from_addr].nft_ids = {1, 2}
        user_state[to_addr].nft_ids = {2, 3}  # Token 2 already exists
        
        event = {
            "event_type": EventType.NFT,
            "args": {
                "from": from_addr,
                "to": to_addr,
                "tokenId": 2,  # Already exists in to_addr
            },
            "blockNumber": 12357,
        }
        
        try:
            process_nft_event(event, user_state)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Token" in str(e) and "already exists" in str(e)
            assert "2" in str(e)
            assert to_addr.lower() in str(e)

    def test_multiple_nft_transfers(self):
        """Test multiple NFT transfers"""
        user_state = defaultdict(UserState)
        user_addr = "0x1111111111111111111111111111111111111111"
        other_addr = "0x2222222222222222222222222222222222222222"
        
        user_state[user_addr].nft_ids = {1, 2, 3}
        user_state[other_addr].nft_ids = {4}
        
        # Transfer NFT 2 from user to other
        event1 = {
            "event_type": EventType.NFT,
            "args": {
                "from": user_addr,
                "to": other_addr,
                "tokenId": 2,
            },
            "blockNumber": 12357,
        }
        result = process_nft_event(event1, user_state)
        assert result[user_addr].nft_ids == {1, 3}
        assert result[other_addr].nft_ids == {4, 2}
        
        # Transfer NFT 4 from other to user
        event2 = {
            "event_type": EventType.NFT,
            "args": {
                "from": other_addr,
                "to": user_addr,
                "tokenId": 4,
            },
            "blockNumber": 12358,
        }
        result = process_nft_event(event2, result)
        assert result[user_addr].nft_ids == {1, 3, 4}
        assert result[other_addr].nft_ids == {2}


class TestProcessEventAboveUserState:
    def test_process_transfer_event(self):
        """Test that process_event_above_user_state routes TRANSFER events correctly"""
        user_state = defaultdict(UserState)
        from_addr = "0x1111111111111111111111111111111111111111"
        to_addr = "0x2222222222222222222222222222222222222222"
        
        user_state[from_addr].balance = 1000
        user_state[to_addr].balance = 500
        
        event = {
            "event_type": EventType.TRANSFER,
            "args": {
                "from": from_addr,
                "to": to_addr,
                "value": 200,
            },
            "blockNumber": 12360,
        }
        
        result = process_event_above_user_state(event, user_state)
        
        assert result[from_addr].balance == 800
        assert result[to_addr].balance == 700
        assert result[from_addr].last_negative_balance_update_block == 12360
        assert result[to_addr].last_positive_balance_update_block == 12360

    def test_process_nft_event(self):
        """Test that process_event_above_user_state routes NFT events correctly"""
        user_state = defaultdict(UserState)
        from_addr = "0x1111111111111111111111111111111111111111"
        to_addr = "0x2222222222222222222222222222222222222222"
        
        user_state[from_addr].nft_ids = {1, 2, 3}
        user_state[to_addr].nft_ids = {4}
        
        event = {
            "event_type": EventType.NFT,
            "args": {
                "from": from_addr,
                "to": to_addr,
                "tokenId": 2,
            },
            "blockNumber": 12361,
        }
        
        result = process_event_above_user_state(event, user_state)
        
        assert result[from_addr].nft_ids == {1, 3}
        assert result[to_addr].nft_ids == {4, 2}

    def test_process_invalid_event_type(self):
        """Test that invalid event type raises ValueError"""
        user_state = defaultdict(UserState)
        
        event = {
            "event_type": 999,  # Invalid event type
            "args": {},
            "blockNumber": 12362,
        }
        
        try:
            process_event_above_user_state(event, user_state)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid event type" in str(e)

    def test_process_event_preserves_other_user_states(self):
        """Test that processing an event doesn't affect unrelated user states"""
        user_state = defaultdict(UserState)
        user1 = "0x1111111111111111111111111111111111111111"
        user2 = "0x2222222222222222222222222222222222222222"
        user3 = "0x3333333333333333333333333333333333333333"
        
        user_state[user1].balance = 1000
        user_state[user2].balance = 500
        user_state[user3].balance = 2000
        user_state[user3].nft_ids = {10, 20}
        
        event = {
            "event_type": EventType.TRANSFER,
            "args": {
                "from": user1,
                "to": user2,
                "value": 200,
            },
            "blockNumber": 12363,
        }
        
        result = process_event_above_user_state(event, user_state)
        
        # user3 should be unchanged
        assert result[user3].balance == 2000
        assert result[user3].nft_ids == {10, 20}
        assert result[user3].last_positive_balance_update_block == 0
        assert result[user3].last_negative_balance_update_block == 0

    def test_process_event_combined_transfer_and_nft(self):
        """Test processing both transfer and NFT events in sequence"""
        user_state = defaultdict(UserState)
        user1 = "0x1111111111111111111111111111111111111111"
        user2 = "0x2222222222222222222222222222222222222222"
        
        user_state[user1].balance = 1000
        user_state[user1].nft_ids = {1, 2}
        user_state[user2].balance = 500
        user_state[user2].nft_ids = {3}
        
        # Process transfer event
        transfer_event = {
            "event_type": EventType.TRANSFER,
            "args": {
                "from": user1,
                "to": user2,
                "value": 200,
            },
            "blockNumber": 12364,
        }
        result = process_event_above_user_state(transfer_event, user_state)
        
        assert result[user1].balance == 800
        assert result[user2].balance == 700
        # NFT IDs should be unchanged
        assert result[user1].nft_ids == {1, 2}
        assert result[user2].nft_ids == {3}
        
        # Process NFT event
        nft_event = {
            "event_type": EventType.NFT,
            "args": {
                "from": user1,
                "to": user2,
                "tokenId": 1,
            },
            "blockNumber": 12365,
        }
        result = process_event_above_user_state(nft_event, result)
        
        # Balances should be unchanged
        assert result[user1].balance == 800
        assert result[user2].balance == 700
        # NFT IDs should be updated
        assert result[user1].nft_ids == {2}
        assert result[user2].nft_ids == {3, 1}

    def test_process_transfer_event_negative_balance_raises_error(self):
        """Test that process_event_above_user_state raises error for negative balance"""
        user_state = defaultdict(UserState)
        from_addr = "0x1111111111111111111111111111111111111111"
        to_addr = "0x2222222222222222222222222222222222222222"
        
        user_state[from_addr].balance = 100
        
        event = {
            "event_type": EventType.TRANSFER,
            "args": {
                "from": from_addr,
                "to": to_addr,
                "value": 200,
            },
            "blockNumber": 12366,
        }
        
        try:
            process_event_above_user_state(event, user_state)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Balance" in str(e) and "negative" in str(e)

    def test_process_nft_event_nonexistent_token_raises_error(self):
        """Test that process_event_above_user_state raises error for nonexistent NFT"""
        user_state = defaultdict(UserState)
        from_addr = "0x1111111111111111111111111111111111111111"
        to_addr = "0x2222222222222222222222222222222222222222"
        
        user_state[from_addr].nft_ids = {1, 2}
        user_state[to_addr].nft_ids = {3}
        
        event = {
            "event_type": EventType.NFT,
            "args": {
                "from": from_addr,
                "to": to_addr,
                "tokenId": 99,  # Doesn't exist
            },
            "blockNumber": 12367,
        }
        
        try:
            process_event_above_user_state(event, user_state)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Token" in str(e) and "not found" in str(e)

    def test_process_nft_event_duplicate_token_raises_error(self):
        """Test that process_event_above_user_state raises error for duplicate NFT"""
        user_state = defaultdict(UserState)
        from_addr = "0x1111111111111111111111111111111111111111"
        to_addr = "0x2222222222222222222222222222222222222222"
        
        user_state[from_addr].nft_ids = {1, 2}
        user_state[to_addr].nft_ids = {2, 3}  # Token 2 already exists
        
        event = {
            "event_type": EventType.NFT,
            "args": {
                "from": from_addr,
                "to": to_addr,
                "tokenId": 2,  # Already exists in destination
            },
            "blockNumber": 12368,
        }
        
        try:
            process_event_above_user_state(event, user_state)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Token" in str(e) and "already exists" in str(e)

