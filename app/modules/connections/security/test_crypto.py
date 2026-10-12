"""Tests for token encryption/decryption utilities."""

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.modules.connections.security.crypto import (
    generate_encryption_key,
    encrypt_token,
    decrypt_token,
    is_valid_encryption_key,
    TokenEncryptor
)


class TestCryptoFunctions:
    """Test encryption/decryption functions."""
    
    def test_generate_encryption_key(self):
        """Test encryption key generation."""
        key = generate_encryption_key()
        
        # Should be a valid base64 string
        assert isinstance(key, str)
        assert len(key) > 0
        
        # Should be a valid Fernet key
        assert is_valid_encryption_key(key)
        
        # Each call should generate a different key
        key2 = generate_encryption_key()
        assert key != key2
    
    def test_encrypt_decrypt_token_success(self):
        """Test successful encryption and decryption."""
        # Generate a key
        key = generate_encryption_key()
        
        # Test token
        original_token = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890"
        
        # Encrypt
        encrypted = encrypt_token(original_token, key)
        
        # Encrypted should be different from original
        assert encrypted != original_token
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0
        
        # Decrypt
        decrypted = decrypt_token(encrypted, key)
        
        # Should match original
        assert decrypted == original_token
    
    def test_encrypt_different_results(self):
        """Test that encryption produces different results each time."""
        key = generate_encryption_key()
        token = "test_token_12345"
        
        encrypted1 = encrypt_token(token, key)
        encrypted2 = encrypt_token(token, key)
        
        # Fernet uses random initialization, so results should differ
        assert encrypted1 != encrypted2
        
        # But both should decrypt to the same value
        assert decrypt_token(encrypted1, key) == token
        assert decrypt_token(encrypted2, key) == token
    
    def test_encrypt_empty_token_error(self):
        """Test encryption with empty token."""
        key = generate_encryption_key()
        
        with pytest.raises(ValueError, match="Token cannot be empty"):
            encrypt_token("", key)
    
    def test_encrypt_empty_key_error(self):
        """Test encryption with empty key."""
        with pytest.raises(ValueError, match="Encryption key cannot be empty"):
            encrypt_token("test_token", "")
    
    def test_encrypt_invalid_key_error(self):
        """Test encryption with invalid key."""
        with pytest.raises(ValueError, match="Encryption failed"):
            encrypt_token("test_token", "invalid_key")
    
    def test_decrypt_empty_token_error(self):
        """Test decryption with empty encrypted token."""
        key = generate_encryption_key()
        
        with pytest.raises(ValueError, match="Encrypted token cannot be empty"):
            decrypt_token("", key)
    
    def test_decrypt_empty_key_error(self):
        """Test decryption with empty key."""
        with pytest.raises(ValueError, match="Encryption key cannot be empty"):
            decrypt_token("encrypted_data", "")
    
    def test_decrypt_wrong_key_error(self):
        """Test decryption with wrong key."""
        key1 = generate_encryption_key()
        key2 = generate_encryption_key()
        
        token = "test_token"
        encrypted = encrypt_token(token, key1)
        
        # Try to decrypt with wrong key
        with pytest.raises(InvalidToken, match="Decryption failed"):
            decrypt_token(encrypted, key2)
    
    def test_decrypt_corrupted_data_error(self):
        """Test decryption with corrupted data."""
        key = generate_encryption_key()
        
        # Invalid base64 or corrupted encrypted data
        with pytest.raises((InvalidToken, ValueError)):
            decrypt_token("corrupted_data_12345", key)
    
    def test_is_valid_encryption_key(self):
        """Test encryption key validation."""
        # Valid key
        valid_key = generate_encryption_key()
        assert is_valid_encryption_key(valid_key) is True
        
        # Invalid keys
        assert is_valid_encryption_key("") is False
        assert is_valid_encryption_key("short") is False
        assert is_valid_encryption_key("not_a_valid_key_123") is False
        assert is_valid_encryption_key(None) is False


class TestTokenEncryptor:
    """Test TokenEncryptor class."""
    
    def test_encryptor_init_valid_key(self):
        """Test TokenEncryptor initialization with valid key."""
        key = generate_encryption_key()
        encryptor = TokenEncryptor(key)
        
        assert encryptor.fernet is not None
    
    def test_encryptor_init_invalid_key(self):
        """Test TokenEncryptor initialization with invalid key."""
        with pytest.raises(ValueError, match="Invalid encryption key format"):
            TokenEncryptor("invalid_key")
    
    def test_encryptor_encrypt_decrypt(self):
        """Test encryption and decryption with TokenEncryptor."""
        key = generate_encryption_key()
        encryptor = TokenEncryptor(key)
        
        token = "test_bot_token_12345"
        
        # Encrypt
        encrypted = encryptor.encrypt(token)
        assert encrypted != token
        assert isinstance(encrypted, str)
        
        # Decrypt
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == token
    
    def test_encryptor_encrypt_empty_token(self):
        """Test TokenEncryptor encryption with empty token."""
        key = generate_encryption_key()
        encryptor = TokenEncryptor(key)
        
        with pytest.raises(ValueError, match="Token cannot be empty"):
            encryptor.encrypt("")
    
    def test_encryptor_decrypt_empty_token(self):
        """Test TokenEncryptor decryption with empty encrypted token."""
        key = generate_encryption_key()
        encryptor = TokenEncryptor(key)
        
        with pytest.raises(ValueError, match="Encrypted token cannot be empty"):
            encryptor.decrypt("")
    
    def test_encryptor_decrypt_wrong_data(self):
        """Test TokenEncryptor decryption with wrong data."""
        key = generate_encryption_key()
        encryptor = TokenEncryptor(key)
        
        with pytest.raises(InvalidToken, match="Decryption failed"):
            encryptor.decrypt("invalid_encrypted_data")
    
    def test_different_encryptors_incompatible(self):
        """Test that different encryptors with different keys are incompatible."""
        key1 = generate_encryption_key()
        key2 = generate_encryption_key()
        
        encryptor1 = TokenEncryptor(key1)
        encryptor2 = TokenEncryptor(key2)
        
        token = "test_token"
        encrypted = encryptor1.encrypt(token)
        
        # Cannot decrypt with different key
        with pytest.raises(InvalidToken):
            encryptor2.decrypt(encrypted)
    
    def test_same_key_different_encryptors_compatible(self):
        """Test that different encryptors with same key are compatible."""
        key = generate_encryption_key()
        
        encryptor1 = TokenEncryptor(key)
        encryptor2 = TokenEncryptor(key)
        
        token = "test_token"
        encrypted = encryptor1.encrypt(token)
        
        # Can decrypt with same key in different instance
        decrypted = encryptor2.decrypt(encrypted)
        assert decrypted == token
