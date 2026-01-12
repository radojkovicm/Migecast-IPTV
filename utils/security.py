"""Security utilities for encryption and decryption"""
import logging
import os
from pathlib import Path
from cryptography.fernet import Fernet
from dotenv import load_dotenv, set_key

logger = logging.getLogger(__name__)


class SecurityManager:
    """Manages encryption/decryption of sensitive data"""

    def __init__(self):
        self.env_path = Path('data/.env')
        self._ensure_env_file()
        load_dotenv(self.env_path)
        self.cipher = self._get_or_create_cipher()

    def _ensure_env_file(self):
        """Ensure .env file exists"""
        if not self.env_path.exists():
            self.env_path.parent.mkdir(parents=True, exist_ok=True)
            self.env_path.touch()
            logger.info("Created new .env file")

    def _get_or_create_cipher(self) -> Fernet:
        """Get or create encryption cipher"""
        encryption_key = os.getenv('ENCRYPTION_KEY')

        if not encryption_key:
            # Generate new encryption key
            encryption_key = Fernet.generate_key().decode('utf-8')
            set_key(self.env_path, 'ENCRYPTION_KEY', encryption_key)
            logger.info("Generated new encryption key")

        return Fernet(encryption_key.encode('utf-8'))

    def encrypt_password(self, password: str) -> str:
        """
        Encrypt a password

        Args:
            password: Plain text password

        Returns:
            Encrypted password as string
        """
        if not password:
            return ""

        try:
            encrypted = self.cipher.encrypt(password.encode('utf-8'))
            return encrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Password encryption failed: {e}")
            raise

    def decrypt_password(self, encrypted_password: str) -> str:
        """
        Decrypt a password

        Args:
            encrypted_password: Encrypted password

        Returns:
            Plain text password
        """
        if not encrypted_password:
            return ""

        try:
            decrypted = self.cipher.decrypt(encrypted_password.encode('utf-8'))
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Password decryption failed: {e}")
            # Return empty string if decryption fails (backward compatibility)
            return ""

    def is_encrypted(self, value: str) -> bool:
        """
        Check if a value appears to be encrypted

        Args:
            value: String to check

        Returns:
            True if encrypted, False otherwise
        """
        if not value:
            return False

        try:
            # Try to decrypt - if it works, it's encrypted
            self.cipher.decrypt(value.encode('utf-8'))
            return True
        except:
            return False

    def get_tmdb_api_key(self) -> str:
        """
        Get TMDB API key from environment

        Returns:
            API key or default key
        """
        api_key = os.getenv('TMDB_API_KEY')
        if not api_key:
            # Fallback to default key (for backward compatibility)
            logger.warning("TMDB_API_KEY not found in .env, using default")
            return "REMOVED_API_KEY"
        return api_key
