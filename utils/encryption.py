#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
encryption.py - Encryption helper with Telegram integration
"""

import os
import json
import base64
import hashlib
import secrets
from typing import Optional, Tuple, Union, Dict, Any
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.primitives import serialization

# Import logger
from .logger import get_logger

logger = get_logger()

class EncryptionManager:
    """Manages encryption operations with Telegram notifications"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.keys = self.load_keys()
        self.fernet = None
        self.setup_fernet()
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.notification_chat_id = None
        self.setup_telegram()
    
    def load_keys(self) -> Dict[str, Any]:
        """Load encryption keys from config or generate new ones"""
        keys_file = self.config.get('keys_file', 'encryption_keys.key')
        
        try:
            if os.path.exists(keys_file):
                with open(keys_file, 'r') as f:
                    return json.load(f)
            else:
                logger.warning(f"Keys file {keys_file} not found, generating new keys")
                return self.generate_keys()
        except Exception as e:
            logger.error(f"Error loading keys: {e}", module="encryption")
            return self.generate_keys()
    
    def generate_keys(self) -> Dict[str, Any]:
        """Generate new encryption keys"""
        logger.info("Generating new encryption keys", module="encryption")
        
        keys = {
            'aes_key': base64.b64encode(os.urandom(32)).decode('utf-8'),
            'fernet_key': Fernet.generate_key().decode('utf-8'),
            'hmac_key': base64.b64encode(os.urandom(32)).decode('utf-8'),
            'iv_key': base64.b64encode(os.urandom(16)).decode('utf-8')
        }
        
        # Generate RSA key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        public_key = private_key.public_key()
        
        keys['rsa_private'] = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        keys['rsa_public'] = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        # Save keys
        self.save_keys(keys)
        
        # Send Telegram notification
        self.send_telegram_notification(
            "🔐 New encryption keys generated",
            f"Key generation completed at {os.uname().nodename}"
        )
        
        return keys
    
    def save_keys(self, keys: Dict[str, Any]):
        """Save keys to file"""
        keys_file = self.config.get('keys_file', 'encryption_keys.key')
        
        try:
            with open(keys_file, 'w') as f:
                json.dump(keys, f, indent=2)
            
            # Set restrictive permissions
            os.chmod(keys_file, 0o600)
            logger.info(f"Keys saved to {keys_file}", module="encryption")
        except Exception as e:
            logger.error(f"Error saving keys: {e}", module="encryption")
    
    def setup_fernet(self):
        """Setup Fernet encryption"""
        try:
            fernet_key = self.keys.get('fernet_key')
            if fernet_key:
                self.fernet = Fernet(fernet_key.encode('utf-8'))
            else:
                logger.warning("No Fernet key found, generating new")
                self.fernet = Fernet.generate_key()
                self.keys['fernet_key'] = self.fernet.decode('utf-8')
                self.save_keys(self.keys)
        except Exception as e:
            logger.error(f"Error setting up Fernet: {e}", module="encryption")
    
    def setup_telegram(self):
        """Setup Telegram bot for notifications"""
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        self.notification_chat_id = telegram_config.get('notification_chat_id')
        
        if bot_token and self.notification_chat_id:
            try:
                from telegram import Bot
                self.telegram_bot = Bot(token=bot_token)
                logger.info("Telegram notification bot initialized", module="encryption")
            except ImportError:
                logger.warning("Telegram module not available", module="encryption")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="encryption")
    
    def send_telegram_notification(self, title: str, message: str):
        """Send notification to Telegram"""
        if not self.telegram_bot or not self.notification_chat_id:
            return
        
        try:
            full_message = f"<b>{title}</b>\n\n{message}"
            self.telegram_bot.send_message(
                chat_id=self.notification_chat_id,
                text=full_message,
                parse_mode='HTML'
            )
            logger.debug(f"Telegram notification sent: {title}", module="encryption")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", module="encryption")
    
    def encrypt_aes(self, data: bytes, key: Optional[bytes] = None) -> Tuple[bytes, bytes, bytes]:
        """Encrypt data using AES-256-CBC"""
        try:
            # Use provided key or default
            if key is None:
                key = base64.b64decode(self.keys['aes_key'])
            
            # Generate random IV
            iv = os.urandom(16)
            
            # Pad data
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(data) + padder.finalize()
            
            # Encrypt
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            encryptor = cipher.encryptor()
            encrypted = encryptor.update(padded_data) + encryptor.finalize()
            
            logger.debug(f"AES encrypted {len(data)} bytes", module="encryption")
            return encrypted, iv, key
            
        except Exception as e:
            logger.error(f"AES encryption error: {e}", module="encryption")
            raise
    
    def decrypt_aes(self, encrypted: bytes, iv: bytes, key: Optional[bytes] = None) -> bytes:
        """Decrypt AES-256-CBC encrypted data"""
        try:
            if key is None:
                key = base64.b64decode(self.keys['aes_key'])
            
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(encrypted) + decryptor.finalize()
            
            # Unpad
            unpadder = padding.PKCS7(128).unpadder()
            data = unpadder.update(padded_data) + unpadder.finalize()
            
            logger.debug(f"AES decrypted {len(encrypted)} bytes", module="encryption")
            return data
            
        except Exception as e:
            logger.error(f"AES decryption error: {e}", module="encryption")
            raise
    
    def encrypt_fernet(self, data: bytes) -> bytes:
        """Encrypt data using Fernet (AES-128-CBC with HMAC)"""
        if not self.fernet:
            self.setup_fernet()
        
        try:
            encrypted = self.fernet.encrypt(data)
            logger.debug(f"Fernet encrypted {len(data)} bytes", module="encryption")
            return encrypted
        except Exception as e:
            logger.error(f"Fernet encryption error: {e}", module="encryption")
            raise
    
    def decrypt_fernet(self, encrypted: bytes) -> bytes:
        """Decrypt Fernet encrypted data"""
        if not self.fernet:
            self.setup_fernet()
        
        try:
            decrypted = self.fernet.decrypt(encrypted)
            logger.debug(f"Fernet decrypted {len(encrypted)} bytes", module="encryption")
            return decrypted
        except Exception as e:
            logger.error(f"Fernet decryption error: {e}", module="encryption")
            raise
    
    def encrypt_rsa(self, data: bytes, public_key: Optional[bytes] = None) -> bytes:
        """Encrypt data using RSA"""
        try:
            if public_key is None:
                public_key = self.keys['rsa_public'].encode('utf-8')
            
            key = serialization.load_pem_public_key(public_key)
            
            # RSA can only encrypt small amounts of data
            # For larger data, use hybrid encryption
            if len(data) > 190:  # 2048-bit RSA limit
                logger.warning("Data too large for RSA, using hybrid encryption", module="encryption")
                return self.hybrid_encrypt(data, public_key)
            
            encrypted = key.encrypt(
                data,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            logger.debug(f"RSA encrypted {len(data)} bytes", module="encryption")
            return encrypted
            
        except Exception as e:
            logger.error(f"RSA encryption error: {e}", module="encryption")
            raise
    
    def decrypt_rsa(self, encrypted: bytes) -> bytes:
        """Decrypt RSA encrypted data"""
        try:
            private_key = serialization.load_pem_private_key(
                self.keys['rsa_private'].encode('utf-8'),
                password=None
            )
            
            decrypted = private_key.decrypt(
                encrypted,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            logger.debug(f"RSA decrypted {len(encrypted)} bytes", module="encryption")
            return decrypted
            
        except Exception as e:
            logger.error(f"RSA decryption error: {e}", module="encryption")
            raise
    
    def hybrid_encrypt(self, data: bytes, public_key: Optional[bytes] = None) -> Dict[str, bytes]:
        """Hybrid encryption: AES for data, RSA for AES key"""
        try:
            # Generate random AES key
            aes_key = os.urandom(32)
            
            # Encrypt data with AES
            encrypted_data, iv, _ = self.encrypt_aes(data, aes_key)
            
            # Encrypt AES key with RSA
            encrypted_key = self.encrypt_rsa(aes_key, public_key)
            
            result = {
                'encrypted_data': encrypted_data,
                'encrypted_key': encrypted_key,
                'iv': iv,
                'algorithm': 'AES-256-CBC + RSA-2048'
            }
            
            logger.debug(f"Hybrid encrypted {len(data)} bytes", module="encryption")
            return result
            
        except Exception as e:
            logger.error(f"Hybrid encryption error: {e}", module="encryption")
            raise
    
    def hybrid_decrypt(self, encrypted_package: Dict[str, bytes]) -> bytes:
        """Decrypt hybrid encrypted package"""
        try:
            # Decrypt AES key with RSA
            aes_key = self.decrypt_rsa(encrypted_package['encrypted_key'])
            
            # Decrypt data with AES
            data = self.decrypt_aes(
                encrypted_package['encrypted_data'],
                encrypted_package['iv'],
                aes_key
            )
            
            logger.debug(f"Hybrid decrypted package", module="encryption")
            return data
            
        except Exception as e:
            logger.error(f"Hybrid decryption error: {e}", module="encryption")
            raise
    
    def encrypt_file(self, file_path: str, output_path: Optional[str] = None) -> str:
        """Encrypt a file"""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Read file
            with open(file_path, 'rb') as f:
                data = f.read()
            
            # Encrypt
            encrypted = self.encrypt_fernet(data)
            
            # Determine output path
            if output_path is None:
                output_path = str(file_path) + '.encrypted'
            
            # Write encrypted file
            with open(output_path, 'wb') as f:
                f.write(encrypted)
            
            # Send Telegram notification
            file_size = len(data) / (1024*1024)  # MB
            self.send_telegram_notification(
                "🔒 File Encrypted",
                f"File: {file_path.name}\n"
                f"Size: {file_size:.2f} MB\n"
                f"Output: {output_path}"
            )
            
            logger.info(f"File encrypted: {file_path} -> {output_path}", module="encryption")
            return output_path
            
        except Exception as e:
            logger.error(f"File encryption error: {e}", module="encryption")
            raise
    
    def decrypt_file(self, file_path: str, output_path: Optional[str] = None) -> str:
        """Decrypt a file"""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Read encrypted file
            with open(file_path, 'rb') as f:
                encrypted = f.read()
            
            # Decrypt
            data = self.decrypt_fernet(encrypted)
            
            # Determine output path
            if output_path is None:
                if file_path.suffix == '.encrypted':
                    output_path = str(file_path.with_suffix(''))
                else:
                    output_path = str(file_path) + '.decrypted'
            
            # Write decrypted file
            with open(output_path, 'wb') as f:
                f.write(data)
            
            logger.info(f"File decrypted: {file_path} -> {output_path}", module="encryption")
            return output_path
            
        except Exception as e:
            logger.error(f"File decryption error: {e}", module="encryption")
            raise
    
    def hash_data(self, data: bytes, algorithm: str = 'sha256') -> str:
        """Hash data using specified algorithm"""
        try:
            if algorithm == 'md5':
                hash_obj = hashlib.md5()
            elif algorithm == 'sha1':
                hash_obj = hashlib.sha1()
            elif algorithm == 'sha256':
                hash_obj = hashlib.sha256()
            elif algorithm == 'sha512':
                hash_obj = hashlib.sha512()
            else:
                raise ValueError(f"Unsupported hash algorithm: {algorithm}")
            
            hash_obj.update(data)
            return hash_obj.hexdigest()
            
        except Exception as e:
            logger.error(f"Hashing error: {e}", module="encryption")
            raise
    
    def generate_password(self, length: int = 16, 
                         include_special: bool = True) -> str:
        """Generate a secure password"""
        try:
            chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            if include_special:
                chars += "!@#$%^&*()_+-=[]{}|;>?"
            
            password = ''.join(secrets.choice(chars) for _ in range(length))
            
            logger.debug(f"Generated password of length {length}", module="encryption")
            return password
            
        except Exception as e:
            logger.error(f"Password generation error: {e}", module="encryption")
            raise
    
    def verify_integrity(self, data: bytes, expected_hash: str, 
                        algorithm: str = 'sha256') -> bool:
        """Verify data integrity using hash"""
        try:
            actual_hash = self.hash_data(data, algorithm)
            return actual_hash == expected_hash
            
        except Exception as e:
            logger.error(f"Integrity verification error: {e}", module="encryption")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get encryption manager status"""
        return {
            'keys_loaded': len(self.keys) > 0,
            'key_count': len(self.keys),
            'fernet_available': self.fernet is not None,
            'telegram_available': self.telegram_bot is not None,
            'algorithms': ['AES-256-CBC', 'Fernet', 'RSA-2048', 'Hybrid']
        }

# Global instance
_encryption_manager = None

def get_encryption_manager(config: Dict = None) -> EncryptionManager:
    """Get or create encryption manager instance"""
    global _encryption_manager
    
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager(config)
    
    return _encryption_manager

if __name__ == "__main__":
    # Test the encryption manager
    config = {
        'keys_file': 'test_keys.key',
        'telegram': {
            'bot_token': 'test_token',
            'notification_chat_id': 123456789
        }
    }
    
    manager = get_encryption_manager(config)
    
    # Test data
    test_data = b"Hello, this is a secret message!"
    
    # Test AES encryption
    encrypted_aes, iv, key = manager.encrypt_aes(test_data)
    decrypted_aes = manager.decrypt_aes(encrypted_aes, iv, key)
    print(f"AES Test: {decrypted_aes == test_data}")
    
    # Test Fernet encryption
    encrypted_fernet = manager.encrypt_fernet(test_data)
    decrypted_fernet = manager.decrypt_fernet(encrypted_fernet)
    print(f"Fernet Test: {decrypted_fernet == test_data}")
    
    # Test RSA encryption (small data)
    small_data = b"Small secret"
    encrypted_rsa = manager.encrypt_rsa(small_data)
    decrypted_rsa = manager.decrypt_rsa(encrypted_rsa)
    print(f"RSA Test: {decrypted_rsa == small_data}")
    
    # Test hybrid encryption
    hybrid = manager.hybrid_encrypt(test_data)
    decrypted_hybrid = manager.hybrid_decrypt(hybrid)
    print(f"Hybrid Test: {decrypted_hybrid == test_data}")
    
    # Test hashing
    hash_result = manager.hash_data(test_data, 'sha256')
    print(f"SHA256 Hash: {hash_result[:16]}...")
    
    # Test password generation
    password = manager.generate_password(12)
    print(f"Generated Password: {password}")
    
    # Show status
    status = manager.get_status()
    print(f"\n🔐 Encryption Manager Status: {status}")
    
    print("\n✅ Encryption tests completed!")
