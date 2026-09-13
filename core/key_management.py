"""
Cryptographic Key Management Module for Madrasati Enterprise.

Provides:
1. Isolated PBKDF2 HMAC-SHA256 Key Derivation for Local Vault Encryption.
2. Key Versioning (v1: Legacy SHA-256 derivation, v2: PBKDF2 HMAC-SHA256 with machine salt).
3. Zero Hardcoded Raw 32-Byte Keys: Uses persistent machine-tied vault keys stored in protected AppData.
4. Seamless Multi-Version Decryption & Graceful Key Rotation.
"""
import os
import sys
import base64
import hashlib
from pathlib import Path
from typing import Optional, Tuple
from django.conf import settings

try:
    from cryptography.fernet import Fernet, MultiFernet
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
except ImportError:
    Fernet = None
    MultiFernet = None
    PBKDF2HMAC = None
    hashes = None


class KeyManager:
    """Enterprise Cryptographic Key Manager supporting versioned keys and secure machine derivation."""

    VERSION_V1 = "v1"
    VERSION_V2 = "v2"
    CURRENT_VERSION = VERSION_V2

    @staticmethod
    def get_secure_storage_dir() -> str:
        """Locates or creates a secure directory in LocalAppData for machine-tied secrets."""
        if sys.platform == 'win32':
            appdata = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA')
            if appdata:
                target = os.path.join(appdata, 'Madrasati', 'vault')
                os.makedirs(target, exist_ok=True)
                return target
        fallback = os.path.join(str(settings.BASE_DIR), '.vault_keys')
        os.makedirs(fallback, exist_ok=True)
        return fallback

    @classmethod
    def get_machine_salt(cls) -> bytes:
        """Retrieves or generates a persistent random 32-byte salt tied to this installation."""
        vault_dir = cls.get_secure_storage_dir()
        salt_file = os.path.join(vault_dir, '.vault_salt')
        if os.path.exists(salt_file):
            try:
                with open(salt_file, 'rb') as f:
                    data = f.read().strip()
                    if len(data) >= 16:
                        return data
            except Exception:
                pass
        # Generate persistent salt
        new_salt = os.urandom(32)
        try:
            with open(salt_file, 'wb') as f:
                f.write(new_salt)
        except Exception:
            pass
        return new_salt

    @classmethod
    def derive_key_v1(cls) -> bytes:
        """Legacy v1 key: Derived directly from Django SECRET_KEY via SHA-256."""
        secret = getattr(settings, 'SECRET_KEY', 'default-madrasati-vault-salt-2026')
        digest = hashlib.sha256(secret.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest)

    @classmethod
    def derive_key_v2(cls) -> bytes:
        """
        Enterprise v2 key: Derived via PBKDF2 HMAC-SHA256 with 100,000 iterations
        using SECRET_KEY and persistent machine-tied salt.
        """
        secret = getattr(settings, 'SECRET_KEY', 'madrasati-enterprise-vault-secret-key-2026')
        salt = cls.get_machine_salt()

        if PBKDF2HMAC is not None and hashes is not None:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100_000,
            )
            key_material = kdf.derive(secret.encode('utf-8'))
        else:
            # Fallback if PBKDF2HMAC primitive is not available
            import hmac
            key_material = hashlib.pbkdf2_hmac('sha256', secret.encode('utf-8'), salt, 100_000, 32)

        return base64.urlsafe_b64encode(key_material)

    @classmethod
    def get_cipher(cls, version: str = CURRENT_VERSION) -> Optional['Fernet']:
        """Returns a Fernet cipher for the requested key version."""
        if Fernet is None:
            return None
        if version == cls.VERSION_V1:
            return Fernet(cls.derive_key_v1())
        return Fernet(cls.derive_key_v2())

    @classmethod
    def get_multi_cipher(cls) -> Optional['MultiFernet']:
        """
        Returns a MultiFernet cipher capable of decrypting data encrypted with v2 or v1 keys,
        while always encrypting with the current v2 key.
        """
        if MultiFernet is None or Fernet is None:
            return None
        ciphers = [
            cls.get_cipher(cls.VERSION_V2),
            cls.get_cipher(cls.VERSION_V1),
        ]
        valid_ciphers = [c for c in ciphers if c is not None]
        return MultiFernet(valid_ciphers)

    @classmethod
    def get_hmac_key(cls, version: str = "v2") -> bytes:
        """Returns HMAC key for tamper-proof document/QR signatures."""
        secret = getattr(settings, 'SECRET_KEY', 'madrasati-hmac-key').encode('utf-8')
        if version == "v1":
            return secret
        # v2 uses machine-salted derivation for HMAC
        salt = cls.get_machine_salt()
        return hashlib.sha256(secret + salt).digest()
