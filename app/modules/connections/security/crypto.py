"""Cryptography utilities for secure token storage."""

import logging
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def generate_encryption_key() -> str:
    """
    Generate a new encryption key for Fernet.
    
    This should be called once to generate a key for the .env file.
    
    Returns:
        Base64-encoded encryption key suitable for Fernet
        
    Example:
        >>> key = generate_encryption_key()
        >>> print(f"ENCRYPTION_KEY={key}")
        ENCRYPTION_KEY=aBC1234...
    """
    return Fernet.generate_key().decode()


def encrypt_token(token: str, encryption_key: str) -> str:
    """
    Encrypt a bot token using Fernet symmetric encryption.
    
    Args:
        token: Plain text bot token to encrypt
        encryption_key: Base64-encoded encryption key
        
    Returns:
        Encrypted token as base64 string
        
    Raises:
        ValueError: If token is empty or key is invalid
    """
    if not token:
        raise ValueError("Token cannot be empty")
    
    if not encryption_key:
        raise ValueError("Encryption key cannot be empty")
    
    try:
        # Create Fernet instance with the key
        fernet = Fernet(encryption_key.encode())
        
        # Encrypt the token
        encrypted = fernet.encrypt(token.encode())
        
        # Return as string for storage
        return encrypted.decode()
        
    except Exception as e:
        logger.error(f"Failed to encrypt token: {e}")
        raise ValueError(f"Encryption failed: {e}")


def decrypt_token(encrypted: str, encryption_key: str) -> str:
    """
    Decrypt an encrypted bot token.
    
    Args:
        encrypted: Encrypted token (base64 string)
        encryption_key: Base64-encoded encryption key
        
    Returns:
        Decrypted plain text token
        
    Raises:
        ValueError: If encrypted token is empty or key is invalid
        InvalidToken: If decryption fails (wrong key or corrupted data)
    """
    if not encrypted:
        raise ValueError("Encrypted token cannot be empty")
    
    if not encryption_key:
        raise ValueError("Encryption key cannot be empty")
    
    try:
        # Create Fernet instance with the key
        fernet = Fernet(encryption_key.encode())
        
        # Decrypt the token
        decrypted = fernet.decrypt(encrypted.encode())
        
        # Return as string
        return decrypted.decode()
        
    except InvalidToken as e:
        logger.error(f"Failed to decrypt token - invalid token or wrong key: {e}")
        raise InvalidToken("Decryption failed - invalid token or wrong encryption key")
    except Exception as e:
        logger.error(f"Failed to decrypt token: {e}")
        raise ValueError(f"Decryption failed: {e}")


def is_valid_encryption_key(key: str) -> bool:
    """
    Check if a string is a valid Fernet encryption key.
    
    Args:
        key: String to validate as encryption key
        
    Returns:
        True if valid Fernet key, False otherwise
    """
    if not key:
        return False
    
    try:
        Fernet(key.encode())
        return True
    except Exception:
        return False


class TokenEncryptor:
    """
    Helper class for token encryption with persistent key.
    
    This class holds the encryption key in memory to avoid
    passing it around constantly.
    """
    
    def __init__(self, encryption_key: str):
        """
        Initialize encryptor with encryption key.
        
        Args:
            encryption_key: Base64-encoded Fernet key
            
        Raises:
            ValueError: If key is invalid
        """
        if not is_valid_encryption_key(encryption_key):
            raise ValueError("Invalid encryption key format")
        
        self.fernet = Fernet(encryption_key.encode())
    
    def encrypt(self, token: str) -> str:
        """Encrypt a token."""
        if not token:
            raise ValueError("Token cannot be empty")
        
        encrypted = self.fernet.encrypt(token.encode())
        return encrypted.decode()
    
    def decrypt(self, encrypted: str) -> str:
        """Decrypt a token."""
        if not encrypted:
            raise ValueError("Encrypted token cannot be empty")
        
        try:
            decrypted = self.fernet.decrypt(encrypted.encode())
            return decrypted.decode()
        except InvalidToken:
            raise InvalidToken("Decryption failed - invalid token or wrong encryption key")
