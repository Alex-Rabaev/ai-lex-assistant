"""Integration test - verify encryption works with real config from .env"""

import pytest
from app.config import config
from app.modules.connections.security import (
    encrypt_token,
    decrypt_token,
    is_valid_encryption_key,
    TokenEncryptor
)


class TestConfigIntegration:
    """Test that encryption works with real config from .env file."""
    
    def test_encryption_key_loaded_from_config(self):
        """Test that ENCRYPTION_KEY is loaded from .env."""
        # Should be loaded from .env
        assert config.ENCRYPTION_KEY is not None
        assert len(config.ENCRYPTION_KEY) > 0
        
        print(f"\n✓ ENCRYPTION_KEY loaded: {config.ENCRYPTION_KEY[:20]}...")
    
    def test_encryption_key_is_valid(self):
        """Test that the key from config is a valid Fernet key."""
        assert is_valid_encryption_key(config.ENCRYPTION_KEY)
        
        print(f"✓ ENCRYPTION_KEY is valid Fernet key")
    
    def test_encrypt_decrypt_with_real_key(self):
        """Test encryption/decryption with the real key from .env."""
        test_token = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890"
        
        # Encrypt with real key
        encrypted = encrypt_token(test_token, config.ENCRYPTION_KEY)
        
        assert encrypted != test_token
        assert len(encrypted) > 0
        
        print(f"✓ Encrypted successfully: {encrypted[:50]}...")
        
        # Decrypt with real key
        decrypted = decrypt_token(encrypted, config.ENCRYPTION_KEY)
        
        assert decrypted == test_token
        
        print(f"✓ Decrypted successfully: {decrypted}")
    
    def test_token_encryptor_with_real_key(self):
        """Test TokenEncryptor class with real key from .env."""
        encryptor = TokenEncryptor(config.ENCRYPTION_KEY)
        
        test_token = "9876543210:ZYXwvuTSRqponMLKjihGFedcBA9876543210"
        
        # Encrypt
        encrypted = encryptor.encrypt(test_token)
        assert encrypted != test_token
        
        print(f"✓ TokenEncryptor encrypted: {encrypted[:50]}...")
        
        # Decrypt
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == test_token
        
        print(f"✓ TokenEncryptor decrypted: {decrypted}")
    
    def test_webhook_base_url_loaded(self):
        """Test that WEBHOOK_BASE_URL is loaded from .env."""
        assert config.WEBHOOK_BASE_URL is not None
        assert len(config.WEBHOOK_BASE_URL) > 0
        assert config.WEBHOOK_BASE_URL.startswith("http")
        
        print(f"✓ WEBHOOK_BASE_URL loaded: {config.WEBHOOK_BASE_URL}")
    
    def test_full_flow_simulation(self):
        """Simulate full flow: encrypt for storage, then decrypt for use."""
        # Simulate receiving a bot token from user
        incoming_bot_token = "1122334455:AABBccDDeeFFggHHiiJJkkLLmmNNooP1234"
        
        print(f"\n=== Simulating Full Flow ===")
        print(f"1. Incoming bot token: {incoming_bot_token}")
        
        # Encrypt before storing in DB
        encrypted_for_db = encrypt_token(incoming_bot_token, config.ENCRYPTION_KEY)
        print(f"2. Encrypted for DB: {encrypted_for_db[:60]}...")
        
        # Simulate: token is now stored in DB...
        # Later: retrieve from DB and decrypt for use
        
        decrypted_for_use = decrypt_token(encrypted_for_db, config.ENCRYPTION_KEY)
        print(f"3. Decrypted for use: {decrypted_for_use}")
        
        # Verify it matches original
        assert decrypted_for_use == incoming_bot_token
        print(f"✓ Full flow successful - tokens match!")


if __name__ == "__main__":
    """Run integration tests with verbose output."""
    pytest.main([__file__, "-v", "-s"])
